"""
system.py

Small Windows housekeeping Perry does on your behalf.

Right now that is one thing: making sure Task Manager is up on the
Performance page when Perry starts, so the machine's vital signs are always
a click away rather than something you go and find.

Two separate problems, and it's worth being clear which is which:

    "is it running, and start it if not"   -> straightforward
    "make it open on the Performance page" -> not a command-line switch

Task Manager has no argument for choosing a page. It remembers whichever
one you were last on, and since Windows 11 22H2 that preference lives in a
JSON file:

    %LocalAppData%\\Microsoft\\Windows\\TaskManager\\settings.json
    {"DefaultStartPage": 1}      0 Processes  1 Performance  2 App history
                                 3 Startup    4 Users        5 Details
                                 6 Services

So `ensure_running()` sets that preference *before* launching, and the page
sticks for every future launch too — including the ones you do yourself.

Everything here degrades quietly. A missing settings file, a locked
registry, a non-Windows machine: Perry notes it and carries on. None of
this is worth failing a startup over.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

TASK_MANAGER_EXE = "Taskmgr.exe"

PAGES = {
    "processes": 0,
    "performance": 1,
    "app history": 2,
    "startup": 3,
    "startup apps": 3,
    "users": 4,
    "details": 5,
    "services": 6,
}


def is_windows() -> bool:
    return os.name == "nt"


def settings_path() -> str:
    """Where Task Manager keeps its preferences."""
    local = os.environ.get("LOCALAPPDATA", "")
    return os.path.join(local, "Microsoft", "Windows", "TaskManager", "settings.json")


# --- is it running? --------------------------------------------------------

def is_running(exe_name: str = TASK_MANAGER_EXE) -> bool:
    """Is a process with this executable name alive?

    psutil first because it's already a Perry dependency and it's exact.
    `tasklist` as a fallback so this still answers correctly on a machine
    where psutil failed to install — this function returning a confident
    False would spawn a duplicate window every time.
    """
    target = exe_name.lower()

    try:
        import psutil
    except ImportError:
        psutil = None

    if psutil is not None:
        try:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info.get("name") or "").lower()
                if name == target:
                    return True
            return False
        except Exception:
            pass  # fall through to tasklist

    if not is_windows():
        return False

    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        return target in (out.stdout or "").lower()
    except (OSError, subprocess.TimeoutExpired):
        # Unknown is not False. Say we can't tell by claiming it's running,
        # so we don't open a window the user didn't ask for.
        return True


# --- which page does it open on? ------------------------------------------

def read_default_start_page() -> int | None:
    try:
        with open(settings_path(), "r", encoding="utf-8-sig") as f:
            return json.load(f).get("DefaultStartPage")
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def set_default_start_page(page: int | str = "performance") -> bool:
    """Make Task Manager open on a given page from now on.

    Returns True if the preference is now what you asked for — including the
    case where it already was, which is the common one after the first run.

    The file only exists once Task Manager has been opened at least once. We
    create it if it's missing rather than giving up: a fresh Windows install
    would otherwise never get the setting.
    """
    if isinstance(page, str):
        wanted = PAGES.get(page.strip().lower())
        if wanted is None:
            return False
    else:
        wanted = int(page)

    path = settings_path()
    if not path or not os.environ.get("LOCALAPPDATA"):
        return False

    if read_default_start_page() == wanted:
        return True

    settings: dict = {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                settings = loaded
    except (OSError, json.JSONDecodeError, ValueError):
        settings = {}

    settings["DefaultStartPage"] = wanted
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f)
        return True
    except OSError:
        # Task Manager rewrites this file when it closes, so a write can
        # legitimately lose a race. Not worth retrying, not worth a crash.
        return False


# --- launching -------------------------------------------------------------

def launch(exe: str = "taskmgr") -> bool:
    if not is_windows():
        return False
    try:
        subprocess.Popen([exe], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return True
    except OSError:
        # Some group policies block Task Manager outright. That's a real
        # answer, not an error worth propagating.
        return False


def ensure_running(page: int | str = "performance",
                   set_page: bool = True) -> dict:
    """Task Manager up, on the page you want. Safe to call every time.

    Returns a small report rather than a bare bool, so a caller can say
    something useful ("already open", "opened it") instead of guessing.
    """
    report = {"was_running": False, "launched": False,
              "page_set": False, "reason": ""}

    if not is_windows():
        report["reason"] = "not Windows"
        return report

    if set_page:
        report["page_set"] = set_default_start_page(page)

    if is_running():
        report["was_running"] = True
        return report

    report["launched"] = launch()
    if not report["launched"]:
        report["reason"] = "couldn't start Task Manager (blocked by policy?)"
    return report


def describe(report: dict) -> str:
    """One line a human can read."""
    if report.get("reason") and not report.get("launched"):
        return f"Task Manager: {report['reason']}"
    if report.get("was_running"):
        return "Task Manager was already open"
    if report.get("launched"):
        page = "the Performance page" if report.get("page_set") else "its last page"
        return f"Opened Task Manager on {page}"
    return "Task Manager: nothing to do"


if __name__ == "__main__":  # pragma: no cover
    print(describe(ensure_running()))
    sys.exit(0)
