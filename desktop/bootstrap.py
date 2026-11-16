"""
bootstrap.py  —  Perry's self-healing launcher.

On every launch it:
  1. Makes sure a local virtual environment (.venv) exists — creates it if not.
  2. Checks every required dependency actually imports inside that venv.
  3. Installs or repairs anything missing or corrupted (with a PyAudio fallback).
  4. Launches Perry using the venv's Python.

Run with your system Python:

    python bootstrap.py                # set up, then launch Perry hidden
    python bootstrap.py --setup-only   # set up only, don't launch

Once the venv exists you can skip this entirely and use the venv directly:

    .venv/Scripts/python .             # launch
    .venv/Scripts/python . --tests     # run the test suite

(The Perry shortcut runs this file for you.)
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(HERE, ".venv")

# (pip install name, module import name used to verify it really works)
REQUIREMENTS = [
    ("keyboard", "keyboard"),
    ("SpeechRecognition", "speech_recognition"),
    ("pyttsx3", "pyttsx3"),
    ("psutil", "psutil"),
    ("pygetwindow", "pygetwindow"),
    ("Pillow", "PIL"),
    ("pywin32", "win32gui"),  # visible-window capture + COM for TTS (Windows)
    ("numpy", "numpy"),       # clap onset detection on every audio chunk
    ("PyAudio", "pyaudio"),  # special-cased: has a Windows fallback
]


def log(msg: str) -> None:
    print(f"[Perry setup] {msg}", flush=True)


def _scripts_dir() -> str:
    return os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin")


def venv_python() -> str:
    exe = "python.exe" if os.name == "nt" else "python"
    return os.path.join(_scripts_dir(), exe)


def venv_pythonw() -> str:
    if os.name == "nt":
        w = os.path.join(_scripts_dir(), "pythonw.exe")
        if os.path.exists(w):
            return w
    return venv_python()


def venv_ok() -> bool:
    """A usable venv has a python that can actually run."""
    py = venv_python()
    if not os.path.exists(py):
        return False
    try:
        subprocess.run([py, "-c", "import sys"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def create_venv() -> None:
    log(f"Creating virtual environment at {VENV_DIR} ...")
    # clear=True rebuilds a corrupted venv from scratch.
    venv.EnvBuilder(with_pip=True, clear=True).create(VENV_DIR)
    log("Virtual environment ready.")


def pip(*args: str) -> int:
    py = venv_python()
    proc = subprocess.run([py, "-m", "pip", *args])
    return proc.returncode


def module_importable(module: str) -> bool:
    py = venv_python()
    try:
        r = subprocess.run([py, "-c", f"import {module}"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def ensure_pyaudio() -> None:
    """PyAudio often fails to build on Windows — fall back to pipwin."""
    if module_importable("pyaudio"):
        return
    log("Installing PyAudio (microphone backend) ...")
    if pip("install", "PyAudio==0.2.14") == 0 and module_importable("pyaudio"):
        return
    log("Direct install failed — trying the pipwin prebuilt wheel ...")
    pip("install", "pipwin")
    subprocess.run([venv_python(), "-m", "pipwin", "install", "pyaudio"])
    if not module_importable("pyaudio"):
        log("WARNING: PyAudio still unavailable. Voice will be disabled until "
            "it's installed. Perry will still run via the hotkey.")


def all_modules_importable() -> bool:
    """One subprocess that imports everything — the fast path at login."""
    py = venv_python()
    code = ";".join(f"import {m}" for _n, m in REQUIREMENTS)
    try:
        r = subprocess.run([py, "-c", code],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def ensure_dependencies() -> None:
    # Perry now starts with Windows, so the common case is "nothing to do".
    # One combined import check keeps login startup near-instant and avoids
    # hitting the network when everything is already healthy.
    if all_modules_importable():
        log("All dependencies healthy.")
        return

    # Something is missing or broken — take the slow, thorough path.
    pip("install", "--upgrade", "pip")

    for name, module in REQUIREMENTS:
        if name == "PyAudio":
            ensure_pyaudio()
            continue
        if module_importable(module):
            continue
        log(f"Installing/repairing {name} ...")
        if pip("install", "--upgrade", name) != 0 or not module_importable(module):
            # One retry with a forced reinstall in case the install is corrupted.
            log(f"Retrying {name} with a clean reinstall ...")
            pip("install", "--force-reinstall", "--no-cache-dir", name)


def launch_perry() -> None:
    log("Launching Perry ...")
    pyw = venv_pythonw()
    # Run the project directory itself — Python executes __main__.py, which is
    # the same thing `python .` does from a shell.
    kwargs = {"cwd": HERE}
    if os.name == "nt":
        # Detach so this console can close without killing Perry.
        DETACHED = 0x00000008
        kwargs["creationflags"] = DETACHED
    subprocess.Popen([pyw, HERE], **kwargs)


def main() -> int:
    log("Checking Perry environment ...")
    if not venv_ok():
        create_venv()
    ensure_dependencies()

    # --setup-only prepares the environment without starting Perry. Useful
    # when you're about to run him yourself and don't want a second, hidden
    # instance fighting over the microphone.
    if "--setup-only" in sys.argv:
        log("Environment ready. From this folder you can now run:")
        log("  .venv/Scripts/python .           launch Perry")
        log("  .venv/Scripts/python . --show    launch with the HUD visible")
        log("  .venv/Scripts/python . --tests   run the test suite")
        return 0

    launch_perry()
    log("Done. Perry is running hidden — clap twice, then say 'Perry wake up'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
