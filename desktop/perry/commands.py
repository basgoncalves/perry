"""
commands.py — what Perry does with a phrase that isn't a wake phrase.

Perry listens all the time, so he only answers when he's addressed: the
phrase mentions his name, or his HUD is open (you're talking to him).
Each command is (trigger words, handler). Handlers return what he says.
"""

from __future__ import annotations

import datetime as _dt
import os
import random
import shutil
import subprocess
import sys

from perry.voice import normalize

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _vscode_exe() -> list[str] | None:
    code = shutil.which("code") or shutil.which("code.cmd")
    if code:
        return [code]
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")):
        for sub in (r"Programs\Microsoft VS Code\Code.exe", r"Microsoft VS Code\Code.exe"):
            p = os.path.join(base, sub)
            if base and os.path.exists(p):
                return [p]
    return None


def open_vscode(_text: str) -> str:
    exe = _vscode_exe()
    if not exe:
        return "I can't find VS Code on this machine."
    subprocess.Popen(exe + ["--new-window"], creationflags=_NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "Opening a fresh VS Code window."


LAUNCHER_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def open_office(_text: str = "") -> str:
    """Start the virtual office (sibling folder ../office); it opens the browser."""
    office = os.path.join(LAUNCHER_ROOT, "office")
    if not os.path.isfile(os.path.join(office, "__main__.py")):
        return "I can't find the office folder."
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(w):
        exe = w
    subprocess.Popen([exe, office], cwd=office, creationflags=_NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "Opening the virtual office."


def open_task_manager(_text: str = "") -> str:
    from perry import system
    system.ensure_running("performance")
    return "Task Manager is up."


_hands_proc = None


def start_hands(_text: str = "") -> str:
    """Webcam hand tracking -> mouse. Lives in ../hands with its own venv."""
    global _hands_proc
    if _hands_proc is not None and _hands_proc.poll() is None:
        return "Hand control is already on."
    hands = os.path.join(LAUNCHER_ROOT, "hands")
    pyw = os.path.join(hands, ".venv", "Scripts", "pythonw.exe")
    if os.path.exists(pyw):
        _hands_proc = subprocess.Popen([pyw, hands], cwd=hands)
        return "Hand control on. Point to move, pinch to click."
    setup = os.path.join(LAUNCHER_ROOT, "hands.cmd")
    if not os.path.exists(setup):
        return "I can't find the hands folder."
    subprocess.Popen(["cmd", "/c", setup], cwd=LAUNCHER_ROOT,
                     creationflags=0x00000010)  # visible console for the one-time install
    return "Setting up hand tracking. This takes a few minutes the first time."


def stop_hands(_text: str = "") -> str:
    global _hands_proc
    if _hands_proc is not None and _hands_proc.poll() is None:
        _hands_proc.terminate()
        _hands_proc = None
        return "Hand control off."
    return "Hand control isn't on. Close its camera window if it's open."


def toggle_hands(_text: str = "") -> str:
    if _hands_proc is not None and _hands_proc.poll() is None:
        return stop_hands()
    return start_hands()


def tell_time(_text: str) -> str:
    return "It's " + _dt.datetime.now().strftime("%H:%M") + "."


def greet(_text: str) -> str:
    return random.choice(["Hello, boss.", "Hey there. Perry, reporting for duty.",
                          "At your service."])


def doing(_text: str) -> str:
    return random.choice(["Listening for you, and keeping an eye on things.",
                          "Floating in my rings, waiting for orders.",
                          "Standing by. Say open VS Code, or ask me the time."])


def how_are_you(_text: str) -> str:
    return "All systems nominal. Tail at full paddle."


def thanks(_text: str) -> str:
    return random.choice(["Anytime.", "My pleasure.", "That's what platypuses are for."])


def help_(_text: str) -> str:
    return ("I can open VS Code, the virtual office or Task Manager, your Perry Online finance pages, tell the time, and restore your session "
            "when you say Perry, Daddy's home.")


def open_sfx(_text: str = "") -> str:
    """Handled by the HUD (needs the Tk thread); app.py routes it."""
    return "Opening the SFX Lab."


# Order matters: first match wins.
COMMANDS = [
    (("open vs code", "open vscode", "open visual studio code", "open code",
      "new vs code", "launch vs code", "open v s code"), open_vscode),
    (("open virtual office", "open the virtual office", "open office",
      "open the office", "virtual office", "show the office"), open_office),
    (("stop hand control", "stop hand mouse", "hands off", "stop hands",
      "turn off hand control", "stop the camera"), stop_hands),
    (("hand control", "hand mouse", "use my hands", "hand tracking",
      "start hands", "open the camera", "open camera"), start_hands),
    (("sfx lab", "sound effects", "open sfx", "add sound effects", "sound design"), open_sfx),
    (("open task manager", "task manager", "show performance"), open_task_manager),
    (("what time", "the time"), tell_time),
    (("what are you doing", "what you doing", "whats up", "what up"), doing),
    (("how are you",), how_are_you),
    (("thank you", "thanks"), thanks),
    *__import__("perry.web", fromlist=["VOICE"]).VOICE,
    (("what can you do", "help"), help_),
    (("hello", "hi perry", "hey perry", "good morning", "good evening"), greet),
]


def respond(text: str) -> str | None:
    """Run the matching command; None if nothing matched."""
    norm = " " + normalize(text) + " "
    for triggers, handler in COMMANDS:
        if any(" " + t + " " in norm for t in triggers):
            try:
                return handler(text)
            except Exception as e:  # never let a command kill the listener
                return f"That didn't work: {e}"
    return None


# Shown in the HUD's Commands window.
HELP = [
    ("Perry, run script",       "asks for a script path; paste it and press Run"),
    ("Perry, open VS Code",     "open a new VS Code window"),
    ("Perry, open virtual office", "Claude tasks + Python jobs in VS Code"),
    ("Perry, hand control",     "webcam hand tracking moves the mouse"),
    ("Perry, stop hand control", "turn it off (or Esc in its camera window)"),
    ("Perry, open Task Manager", "Task Manager on the Performance page"),
    ("Perry, open portfolio / spending / market / goals / invest", "Perry Online sections in an app window"),
    ("Perry, Perry Online",     "open the web app (chat, finance, biz)"),
    ("Perry, sound effects",    "SFX Lab: whooshes/clicks on a video's cuts"),
    ("Perry, what time is it",  "tell the time"),
    ("Perry, what are you doing", "small talk (also: hello, how are you, thanks)"),
    ("Perry, what can you do",  "list what he can do"),
    ("Ctrl + Alt + P",          "summon Perry by keyboard"),
    ("Perry, run <balloon name>", "run a balloon you added with +"),
    ("Click Perry",             "ring of options; drag to move him"),
    ("Right-click a balloon",   "edit or remove a balloon you added"),
]
