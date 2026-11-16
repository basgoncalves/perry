"""
web.py — Perry Online (https://basgoncalves.github.io/perry/) inside desktop Perry.

Each section of the web app opens in its own chromeless app window (Edge or
Chrome --app mode), so it looks like part of Perry rather than a browser tab.
Your finance data stays in that browser profile's localStorage, exactly as on
the website. Falls back to the default browser if neither is found.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser

BASE_URL = "https://basgoncalves.github.io/perry/"

# (hash, label, glyph) — hash matches the web app's tab names
SECTIONS = [
    ("perry",  "Perry chat", "◎"),
    ("spend",  "Spending",   "€"),
    ("port",   "Portfolio",  "▲"),
    ("market", "Market",     "▦"),
    ("goals",  "Goals",      "◆"),
    ("invest", "Invest",     "%"),
    ("biz",    "Biz",        "✚"),
    ("set",    "Settings",   "⚙"),
]
_LABEL = {k: l for k, l, _ in SECTIONS}
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def url_for(section: str = "perry") -> str:
    return BASE_URL + ("#" + section if section in _LABEL else "")


def _app_browser() -> str | None:
    for name in ("msedge", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    roots = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    for r in roots:
        for sub in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            p = os.path.join(r, sub)
            if r and os.path.exists(p):
                return p
    return None


def open_section(section: str = "perry") -> str:
    url = url_for(section)
    exe = _app_browser()
    try:
        if exe:
            subprocess.Popen([exe, f"--app={url}", "--window-size=460,860"],
                             creationflags=_NO_WINDOW,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            webbrowser.open(url)
    except Exception:
        webbrowser.open(url)
    return f"Opening Perry Online — {_LABEL.get(section, 'home')}."


def _opener(section):
    return lambda _text="": open_section(section)   # looked up at call time


# Voice triggers (normalized text). Added to commands.COMMANDS.
VOICE = [
    (("perry online", "open online", "open the website", "open web perry"), _opener("perry")),
    (("open spending", "my spending", "open spend", "open budget", "show spending"), _opener("spend")),
    (("open portfolio", "my portfolio", "show portfolio", "open stocks"), _opener("port")),
    (("open market", "show the market", "market heatmap", "how is the market"), _opener("market")),
    (("open goals", "savings goals", "my goals"), _opener("goals")),
    (("open invest", "investment options", "open investments"), _opener("invest")),
    (("open biz", "open business", "open bookings"), _opener("biz")),
]
