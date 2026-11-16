"""
session_manager.py

Captures and restores the user's working "session": the apps and windows that
were open. It records the real, user-facing applications (the ones that own a
visible window) and can relaunch them on wake. Full fidelity restore of browser
tabs and exact window layout is planned but not implemented yet.

Why the "visible window" rule matters:
    A naive snapshot of *every* running process captures ~100 Windows system
    services and drivers (winlogon.exe, MsMpEng.exe, LsaIso.exe, GPU drivers,
    ...). Trying to relaunch those on restore is useless and can spawn errors.
    We instead capture only processes that own a visible top-level window, which
    is exactly the set of apps the user actually has open.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

try:
    import pygetwindow as gw
except ImportError:  # pragma: no cover
    gw = None


# Processes we never want to capture/relaunch even if they own a window
# (system shell, our own interpreter, etc.).
_IGNORE = {
    "explorer.exe", "svchost.exe", "System", "Registry", "smss.exe",
    "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "fontdrvhost.exe",
    "dwm.exe", "python.exe", "pythonw.exe", "RuntimeBroker.exe",
    "SearchHost.exe", "StartMenuExperienceHost.exe", "TextInputHost.exe",
    "ctfmon.exe", "conhost.exe", "SystemSettings.exe", "ApplicationFrameHost.exe",
    "ShellExperienceHost.exe", "ShellHost.exe", "LockApp.exe", "winlogon.exe",
    "WidgetBoard.exe", "WidgetService.exe", "SearchIndexer.exe",
}

# Directories whose executables are OS internals we must never relaunch.
# Used as a safety net on restore and as a fallback filter on capture.
# Written with forward slashes; matching normalizes backslashes so it works
# regardless of the platform the check runs on.
_SYSTEM_DIR_MARKERS = (
    "/windows/system32/",
    "/windows/syswow64/",
    "/windows/systemapps/",
    "/windows/driverstore/",
    "/driverstore/filerepository/",
    "/windows/uus/",
    "/windows defender/",
    "/microsoft onedrive/",
    "/common files/microsoft shared/clicktorun/",
)


def _visible_window_pids():
    """
    Return the set of process IDs that own a real, top-level "application"
    window -- the same set Alt-Tab would show. This deliberately INCLUDES
    minimized apps (a minimized window is still part of your session) but
    excludes tool windows, owned pop-ups and title-less system surfaces.

    Returns None if the Win32 API isn't available (non-Windows or pywin32
    missing), so callers can fall back to a conservative heuristic.
    """
    try:
        import win32gui
        import win32con
        import win32process
    except Exception:
        return None

    pids: set[int] = set()

    def _is_app_window(hwnd) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return False
        title = win32gui.GetWindowText(hwnd)
        if not title or not title.strip():
            return False
        # Top-level only: skip windows owned by another window (pop-ups, dialogs).
        if win32gui.GetWindow(hwnd, win32con.GW_OWNER) != 0:
            return False
        # Skip tool windows (they never appear in Alt-Tab).
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return False
        return True

    def _callback(hwnd, _extra):
        try:
            if not _is_app_window(hwnd):
                return
            _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                pids.add(pid)
        except Exception:
            pass

    try:
        win32gui.EnumWindows(_callback, None)
    except Exception:
        return None
    return pids


def _is_system_exe(exe: str) -> bool:
    if not exe:
        return True
    # Normalize backslashes to forward slashes so markers match on any platform.
    low = exe.lower().replace("\\", "/")
    return any(marker in low for marker in _SYSTEM_DIR_MARKERS)


class SessionManager:
    def __init__(self, session_path: str):
        self.session_path = session_path

    # ---------------------------------------------------------------- capture
    def capture(self) -> dict:
        """Snapshot the current desktop session to a dict and save it."""
        snapshot = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "windows": self._capture_windows(),
            "apps": self._capture_apps(),
        }
        self._save(snapshot)
        return snapshot

    def _capture_windows(self) -> list[dict]:
        if gw is None:
            return []
        windows = []
        for w in gw.getAllWindows():
            title = (w.title or "").strip()
            if not title:
                continue
            # Skip minimized windows parked off-screen by Windows.
            if w.left <= -30000 or w.top <= -30000:
                continue
            windows.append({
                "title": title,
                "left": w.left, "top": w.top,
                "width": w.width, "height": w.height,
            })
        return windows

    def _capture_apps(self) -> list[dict]:
        """
        Capture the user's real applications: processes that own a visible
        window. Falls back to a system-directory filter if the Win32 API isn't
        available, so we never try to relaunch OS services and drivers.
        """
        if psutil is None:
            return []

        visible_pids = _visible_window_pids()  # None => API unavailable
        seen: dict[str, dict] = {}

        for proc in psutil.process_iter(["name", "exe", "pid"]):
            try:
                name = proc.info["name"]
                exe = proc.info["exe"]
                pid = proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if not name or not exe or name in _IGNORE:
                continue

            if visible_pids is not None:
                # Preferred path: only apps that actually own a visible window.
                if pid not in visible_pids:
                    continue
            else:
                # Fallback path: at least exclude obvious OS internals.
                if _is_system_exe(exe):
                    continue

            # Keep one entry per executable.
            if name not in seen:
                seen[name] = {"name": name, "exe": exe}

        return list(seen.values())

    # ---------------------------------------------------------------- restore
    def restore(self) -> dict:
        """Relaunch apps from the last saved session."""
        if not os.path.exists(self.session_path):
            return {"status": "no_session", "launched": [], "message":
                    "No saved session found yet. I'll remember this one."}

        snapshot = self._load()
        launched, failed, skipped = [], [], []
        for app in snapshot.get("apps", []):
            exe = app.get("exe")
            name = app.get("name", exe)
            if not exe or not os.path.exists(exe):
                failed.append(name)
                continue
            # Safety net: never relaunch OS internals, even if an old snapshot
            # (captured before this fix) still lists them.
            if name in _IGNORE or _is_system_exe(exe):
                skipped.append(name)
                continue
            if self._is_running(name):
                continue  # already open, don't duplicate
            try:
                subprocess.Popen([exe])
                launched.append(name)
                time.sleep(0.4)
            except Exception:
                failed.append(name)

        return {
            "status": "restored",
            "saved_at": snapshot.get("saved_at"),
            "launched": launched,
            "failed": failed,
            "skipped": skipped,
            "window_count": len(snapshot.get("windows", [])),
        }

    @staticmethod
    def _is_running(name: str) -> bool:
        if psutil is None:
            return False
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] == name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    # ------------------------------------------------------------------- io
    def _save(self, snapshot: dict) -> None:
        with open(self.session_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

    def _load(self) -> dict:
        with open(self.session_path, "r", encoding="utf-8") as f:
            return json.load(f)
