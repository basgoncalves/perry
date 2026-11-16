"""
Perry's entry point.

    cd ~/Desktop/perry/Perry
    python .                 # launch the assistant (hidden, listening)
    python . --show          # launch with the HUD visible
    python . --console       # talk to Perry by typing (see also: the `perry` command)
    python . --phone         # show the address + token to pair the phone app
    python . --scrooge       # open Scrooge, Perry's money brain
    python . --tests         # run the test suite
    python . --mics          # probe every microphone
    python . --meter         # live clap level meter

Once you've run "Add Perry to PATH.bat" in the folder above this one, `perry`
works from any command prompt: `perry` for the console, `perry check stocks`
to do one thing and exit.

You can run this with ANY Python — your system one, Anaconda's, whatever `python`
happens to mean in your shell. Perry's dependencies (PyAudio, numpy, pywin32...)
live in the project's own `.venv`, so if you started him with a different
interpreter he quietly hands off to that one instead of failing with "PyAudio
not installed". If there's no `.venv` yet, bootstrap.py builds it first.

Everything else lives in the `perry` package; the tests live in `tests`.

Abilities — Scrooge and anything after it — live in sibling folders next to
this one and run on their own interpreters. `perry/abilities/` holds the
few lines Perry needs to find and start them.
"""

from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Set on the child process so a re-exec can never loop forever.
_HANDOFF_FLAG = "PERRY_HANDED_OFF"


def venv_dir() -> str:
    return os.path.join(ROOT, ".venv")


def venv_scripts_dir() -> str:
    return os.path.join(venv_dir(), "Scripts" if os.name == "nt" else "bin")


def venv_python() -> str:
    exe = "python.exe" if os.name == "nt" else "python"
    return os.path.join(venv_scripts_dir(), exe)


def running_in_venv(executable: str | None = None) -> bool:
    """
    Are we already on the project's own interpreter?

    Compares directories rather than exact filenames, because Perry is
    legitimately started as both python.exe (from a shell) and pythonw.exe
    (from the Startup shortcut, so no console window flashes up).
    """
    executable = executable or sys.executable
    if not executable:
        return False
    here = os.path.normcase(os.path.abspath(os.path.dirname(executable)))
    target = os.path.normcase(os.path.abspath(venv_scripts_dir()))
    return here == target


def hand_off(args: list[str]) -> int:
    """Re-run this same command on the venv's interpreter."""
    env = dict(os.environ, **{_HANDOFF_FLAG: "1"})
    proc = subprocess.run([venv_python(), ROOT, *args], cwd=ROOT, env=env)
    return proc.returncode


def build_venv() -> bool:
    """No .venv yet — let bootstrap.py create it. Returns True on success."""
    print("[Perry] No virtual environment yet — setting one up. "
          "This takes a minute the first time.\n", flush=True)
    proc = subprocess.run([sys.executable,
                           os.path.join(ROOT, "bootstrap.py"), "--setup-only"],
                          cwd=ROOT)
    return proc.returncode == 0 and os.path.exists(venv_python())


INSTANCE_PORT = 47811  # Perry's "already running?" doorbell, localhost only


def ring_running_perry(show: bool) -> bool:
    """If a Perry is already running, ask it to show itself. Near-instant."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", INSTANCE_PORT), timeout=0.3) as s:
            s.sendall(b"show\n" if show else b"ping\n")
        return True
    except OSError:
        return False


def main() -> int:
    args = sys.argv[1:]
    # The installed Perry.exe: opening it means "show me Perry". The login
    # autostart entry passes --hidden to start him quietly listening instead.
    if getattr(sys, "frozen", False):
        if "--hidden" in args:
            args = [a for a in args if a != "--hidden"]
        elif "--show" not in args and not any(a.startswith("--") for a in args):
            args = args + ["--show"]

    # Fast path: a plain launch while Perry already runs (e.g. from login)
    # just brings the existing one forward instead of booting a second copy.
    if not [a for a in args if a != "--show"] and ring_running_perry("--show" in args):
        return 0

    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0

    # Scrooge runs on its own interpreter with its own dependencies, so it
    # is dispatched BEFORE the venv handoff — there is no reason to build or
    # repair Perry's environment just to open a dashboard that never touches
    # it. Uses stdlib only, so this path works on any Python.
    if "--phone" in args:  # stdlib only, so no venv needed
        from perry import config as config_module
        from perry.phone_link import print_pairing
        return print_pairing(config_module.load(), config_module.save)

    if "--scrooge" in args:
        from perry.abilities.scrooge import main as scrooge_main
        return scrooge_main([a for a in args if a != "--scrooge"])

    # --- make sure we're on the interpreter that has Perry's dependencies ---
    # (the installed Perry.exe carries its own Python: nothing to hand off to)
    if not getattr(sys, "frozen", False) and not running_in_venv() and not os.environ.get(_HANDOFF_FLAG):
        if not os.path.exists(venv_python()) and not build_venv():
            print("[Perry] Couldn't set up the environment. Try running:\n"
                  "  python bootstrap.py", file=sys.stderr)
            return 1
        return hand_off(args)

    # --- from here on we're on the right interpreter ------------------------
    if "--tests" in args:
        from tests.runner import run_in_terminal
        return run_in_terminal()

    if "--console" in args:
        from perry.console import main as console_main
        return console_main([a for a in args if a != "--console"])

    if "--mics" in args:
        from perry.tools.mic_devices import main as mics_main
        return mics_main()

    if "--meter" in args:
        from perry.tools.clap_meter import main as meter_main
        return meter_main()

    return fast_start(args)


def fast_start(args: list[str]) -> int:
    """Paint the HUD first, then load the heavy parts (speech, audio, numpy,
    window tracking) on a thread while the platypus is already animating."""
    import threading
    from perry import config as config_module
    from perry.hud import PerryHUD

    cfg = config_module.load()
    start_hidden = "--show" not in args and cfg.get("start_hidden", True)
    hud = PerryHUD(assistant_name=cfg.get("assistant_name", "Perry"),
                   start_hidden=start_hidden)
    hud.root.update()

    def boot():
        try:
            from perry.app import Perry
            p = Perry(cfg, start_hidden=start_hidden, hud=hud)
            hud.on_close, hud.on_tests = p.shutdown, p.open_tests
            hud.on_office, hud.on_action = p.open_office, p.on_action
            p._serve_instance()
            hud.root.after(0, p._tick)
            p._start_background()
        except Exception as e:  # show it rather than dying silently
            hud.set_status("Startup failed")
            hud.set_heard(str(e))
            hud.show()

    threading.Thread(target=boot, daemon=True, name="perry-boot").start()
    hud.on_close = lambda: hud.root.destroy()   # until boot replaces it
    hud.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
