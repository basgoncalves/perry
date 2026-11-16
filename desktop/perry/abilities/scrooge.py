"""
scrooge.py — the bridge to Perry's money brain.

Scrooge is a sibling of the Perry folder, not a module inside it:

    perry/
    ├── Perry/          <- you are here
    └── scrooge/        <- portfolio, research, watchlist, income

This file's whole job is to find that folder and start it. It deliberately
does not import anything from Scrooge — Scrooge runs on its own interpreter
with its own dependencies (Streamlit, pandas, plotly, yfinance), and Perry's
`.venv` has none of them. Handing a path to a subprocess is the entire
integration, which is why it can't break Perry.

If the folder isn't there, `is_available()` says so and Perry carries on.
An ability that has been deleted is not an error.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Sequence

# Perry/perry/abilities/scrooge.py -> Perry/ -> perry/ (the launcher folder)
PERRY_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LAUNCHER_ROOT = os.path.dirname(PERRY_ROOT)

DEFAULT_PATH = "../scrooge"


def scrooge_dir(cfg: dict | None = None) -> str:
    """Absolute path to the Scrooge folder.

    A relative `scrooge_path` is resolved against the Perry folder, so the
    default "../scrooge" lands on the sibling directory wherever the whole
    thing has been copied to. An absolute path is used as given.
    """
    cfg = cfg or {}
    configured = cfg.get("scrooge_path") or DEFAULT_PATH
    if os.path.isabs(configured):
        return os.path.normpath(configured)
    return os.path.normpath(os.path.join(PERRY_ROOT, configured))


def is_available(cfg: dict | None = None) -> bool:
    """Is there actually a runnable Scrooge at that path?

    Checks for `__main__.py` rather than just the directory: an empty folder
    left behind by a half-finished move should read as 'not installed', not
    as 'installed and broken'.
    """
    return os.path.isfile(os.path.join(scrooge_dir(cfg), "__main__.py"))


def is_enabled(cfg: dict | None = None) -> bool:
    cfg = cfg or {}
    return bool(cfg.get("scrooge_enabled", True)) and is_available(cfg)


def launch(cfg: dict | None = None, args: Sequence[str] = (),
           wait: bool = True) -> int:
    """Start Scrooge.

    wait=True   run it in the foreground; Ctrl-C stops the server. This is
                what `python . --scrooge` wants.
    wait=False  start it detached and return immediately, leaving Perry's
                event loop free. This is what a HUD button would want.

    Returns the exit code when waiting, or 0 once launched when not.

    Note there is no port argument here on purpose. Scrooge's own
    config.json owns the port; duplicating it in Perry's config would mean
    two places to change it and one of them being wrong.
    """
    target = scrooge_dir(cfg)
    if not is_available(cfg):
        print(f"[Perry] No Scrooge found at {target}", file=sys.stderr)
        return 1

    cmd = [sys.executable, target, *args]

    if wait:
        try:
            return subprocess.call(cmd, cwd=target)
        except KeyboardInterrupt:
            return 0

    # Detached: no console window on Windows, and don't die with Perry.
    kwargs: dict = {"cwd": target}
    if os.name == "nt":
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                   | getattr(subprocess, "DETACHED_PROCESS", 0))
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)
    return 0


def main(args: Sequence[str] = ()) -> int:
    """`python . --scrooge` lands here."""
    from perry import config as config_module

    cfg = config_module.load()
    if not cfg.get("scrooge_enabled", True):
        print("[Perry] Scrooge is switched off in config.json "
              '("scrooge_enabled": false).', file=sys.stderr)
        return 1
    print(f"[Perry] Opening Scrooge from {scrooge_dir(cfg)} ...", flush=True)
    return launch(cfg, args, wait=True)
