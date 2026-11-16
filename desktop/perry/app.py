"""
app.py — the Perry class: everything wired together.

How Perry wakes up
------------------
He sits hidden in the background from the moment Windows starts, listening.

    👏👏  two claps          ->  arms him: the orb appears, glowing amber
    "Perry wake up"          ->  (within ~8s of the claps) he wakes and
                                 restores your last session
    "Perry, Daddy's home"    ->  the original phrase; works any time
    Ctrl+Alt+P               ->  summon him by hand, no voice needed

The two-step clap-then-phrase design is deliberate. A clap alone gets
triggered by a slammed door; a phrase alone gets triggered by anyone saying
"Perry" on a podcast. Requiring both makes a false wake essentially impossible,
and a false *arm* costs nothing — the orb just fades after the window closes.

Every collaborator can be injected through the constructor. That's what lets
the tests exercise the real wake logic without a microphone, a display or a
session to restore.
"""

from __future__ import annotations

import sys
import threading
import time

from perry import config as config_module
from perry.audio_hub import AudioHub
from perry.clap_detector import ClapDetector
from perry.session_manager import SessionManager
from perry.voice import Speaker, VoiceListener, phrase_matches, normalize

try:
    import keyboard
except ImportError:
    keyboard = None


def chime(pattern: str = "arm") -> None:
    """A short non-verbal cue. Speech is far too slow for an arming signal."""
    def _play():
        try:
            import winsound
            notes = {"arm": ((880, 70), (1245, 70)),
                     "wake": ((1245, 80), (1660, 120)),
                     "cancel": ((660, 70),)}
            for freq, ms in notes.get(pattern, notes["arm"]):
                winsound.Beep(freq, ms)
        except Exception:
            pass
    threading.Thread(target=_play, daemon=True).start()


class Perry:
    def __init__(self, cfg: dict, start_hidden: bool = True, *,
                 hud=None, sessions=None, hub=None, speaker=None,
                 claps=None, listener=None, chime_fn=None):
        self.config = cfg
        self.name = cfg.get("assistant_name", "Perry")
        self.chime = chime_fn if chime_fn is not None else chime

        self.sessions = sessions or SessionManager(config_module.session_path(cfg))
        self.speaker = speaker or Speaker(enabled=cfg.get("tts_enabled", True),
                                          rate=cfg.get("tts_rate", 175))
        # Imported here rather than at module scope so the tests can build a
        # Perry with a fake HUD on a machine with no tkinter at all.
        if hud is None:
            from perry.hud import PerryHUD
            hud = PerryHUD(assistant_name=self.name, on_close=self.shutdown,
                           on_tests=self.open_tests,
                           on_office=self.open_office, on_action=self.on_action,
                           start_hidden=start_hidden)
        self.hud = hud

        # --- what counts as a wake phrase -----------------------------------
        # armed_phrases only work once the claps have armed him;
        # always_on_phrases work at any time.
        self.armed_phrases = [normalize(p) for p in (
            [cfg.get("wake_phrase", "perry wake up")]
            + cfg.get("wake_phrase_aliases", []))]
        self.always_on_phrases = [normalize(p)
                                  for p in cfg.get("always_on_phrases", [])]
        self.arm_window = float(cfg.get("arm_window_seconds", 8))
        self.require_claps = bool(cfg.get("require_claps", True))
        self._armed_until = 0.0

        # --- ears -----------------------------------------------------------
        # mic_device_index=None lets Windows pick. If that picks a dead device
        # (a switched-off webcam mic, Stereo Mix), `python . --mics` finds the
        # live one and writes its index into config.json.
        self.hub = hub or AudioHub(device_index=cfg.get("mic_device_index"))
        self.claps = claps or ClapDetector(
            on_claps=self.on_claps,
            on_clap=self.on_single_clap,
            claps_required=cfg.get("claps_required", 2),
            rate=self.hub.rate,
            sensitivity=cfg.get("clap_sensitivity", 5.0),
            abs_floor=cfg.get("clap_min_level", 0.012),
            min_width_ms=cfg.get("clap_min_width_ms", 12),
            min_gap_ms=cfg.get("clap_min_gap_ms", 80),
            max_gap_ms=cfg.get("clap_max_gap_ms", 900),
        )
        self.listener = listener or VoiceListener(
            hub=self.hub,
            on_phrase=self.on_phrase,
            on_status=self.hud.set_heard,
            listen_timeout=cfg.get("listen_timeout_seconds", 6),
            phrase_time_limit=cfg.get("phrase_time_limit_seconds", 5),
            gate=self._recognition_gate,
        )

    # ------------------------------------------------------------------ arming
    def is_armed(self) -> bool:
        return time.monotonic() < self._armed_until

    def _recognition_gate(self) -> bool:
        """Should this phrase be sent off for recognition?"""
        if self.config.get("recognize_only_when_armed", False):
            return self.is_armed()
        return True

    def on_single_clap(self, count: int) -> None:
        if count == 1 and self.config.get("claps_required", 2) > 1:
            self.hud.set_heard("clap detected — one more")

    def on_claps(self) -> None:
        """Two claps heard. Arm Perry and wait for the phrase."""
        self._armed_until = time.monotonic() + self.arm_window
        self.chime("arm")
        self.hud.show()
        self.hud.set_mode("armed")
        phrase = self.config.get("wake_phrase", "perry wake up")
        self.hud.set_status(f'Listening — say "{phrase}"')
        self.hud.set_heard(f"armed for {int(self.arm_window)}s")

    def disarm(self) -> None:
        self._armed_until = 0.0
        self.claps.reset()
        self.chime("cancel")
        self.hud.set_mode("idle")
        self.hud.set_status("Standing by")
        self.hud.hide()

    def _tick(self) -> None:
        """Runs on the tkinter thread; retires the arm window when it expires."""
        if self._armed_until and not self.is_armed():
            self.disarm()
        self.hud.root.after(400, self._tick)

    # ------------------------------------------------------------------ hotkey
    def register_hotkey(self) -> None:
        combo = self.config.get("hotkey", "ctrl+alt+p")
        if keyboard is None:
            self.hud.set_heard("install 'keyboard' for the hotkey")
            return
        try:
            keyboard.add_hotkey(combo, self.summon)
        except Exception as e:
            self.hud.set_heard(f"hotkey failed: {e}")

    def summon(self) -> None:
        """Bring Perry to the foreground by hand and arm him."""
        self._armed_until = time.monotonic() + self.arm_window
        self.hud.show()
        self.hud.set_mode("armed")
        self.hud.set_status("At your service.")
        self.speaker.say_async(f"{self.name} online.")

    # ------------------------------------------------------------------- voice
    def on_phrase(self, text: str) -> None:
        self.hud.set_heard(f"heard: {text}")

        if phrase_matches(text, self.always_on_phrases):
            self.wake()
            return

        if phrase_matches(text, self.armed_phrases):
            if self.is_armed() or not self.require_claps:
                self.wake()
            else:
                self.hud.set_heard("clap twice first, then say it")
            return

        self.handle_command(text)

    def handle_command(self, text: str) -> None:
        """Answer anything that isn't a wake phrase — only when addressed."""
        from perry import commands
        addressed = "perry" in normalize(text) or getattr(self.hud, "visible", False)
        if not addressed:
            return
        n = " " + normalize(text) + " "
        if any(k in n for k in (" run script ", " run a script ", " run the script ",
                                " run my script ", " execute script ")):
            self.hud.prompt_script()
            self.speaker.say_async("Which script? Paste the path.")
            return
        reply = commands.respond(text)
        if reply == commands.open_sfx():
            self.hud.root.after(0, self.hud.open_sfx)
        if reply is None:  # a balloon you added with "+": "Perry, run <name>"
            norm = " " + normalize(text) + " "
            for i, c in enumerate(getattr(self.hud, "custom", [])):
                name = normalize(c.get("name", ""))
                if name and f" {name} " in norm:
                    self.hud.root.after(0, lambda i=i: self.hud.run_custom(i))
                    reply = f"Running {c.get('name')}."
                    break
        if reply is None:
            if "perry" not in normalize(text):
                return
            reply = "Sorry, I didn't get that. Ask me what I can do."
        self.hud.show()
        self.hud.set_status(reply if len(reply) < 40 else reply[:37] + "...")
        self.speaker.say_async(reply)

    def wake(self) -> None:
        self._armed_until = 0.0
        self.claps.reset()
        self.chime("wake")
        self.hud.show()
        self.hud.set_mode("awake")
        self.hud.set_status("Welcome home. Restoring your session...")
        self.speaker.say_async("Welcome home. Restoring your session.")
        threading.Thread(target=self._do_restore, daemon=True).start()

    def _do_restore(self) -> None:
        try:
            result = self.sessions.restore()
        except Exception as e:
            self.hud.set_status(f"Restore failed: {e}")
            return
        self.report_restore(result)

    def report_restore(self, result: dict) -> None:
        if result.get("status") == "no_session":
            self.hud.set_status("No saved session yet — I'll remember this one.")
            self.speaker.say_async("No saved session yet. I'll remember this one.")
            self.safe_capture()
            return
        launched = result.get("launched", [])
        msg = (f"Restored {len(launched)} app(s)." if launched
               else "Everything was already open.")
        self.hud.set_status(msg)
        self.speaker.say_async(msg)

    # ------------------------------------------------------------------- tests
    def on_action(self, action: str) -> None:
        """A click in the HUD's option ring or Commands button."""
        from perry import commands
        if action == "commands":
            return self.hud.show_commands(commands.HELP)
        if action == "home":
            return self.wake()
        if action == "office":
            return self.open_office()
        fn = {"vscode": commands.open_vscode,
              "taskmgr": commands.open_task_manager,
              "hands": commands.toggle_hands}.get(action)
        if fn:
            def run():
                reply = fn("")
                self.hud.set_status(reply if len(reply) < 40 else reply[:37] + "...")
            threading.Thread(target=run, daemon=True).start()

    def open_office(self) -> None:
        from perry import commands
        reply = commands.open_office()
        self.hud.set_status(reply)
        self.speaker.say_async(reply)

    def open_tests(self) -> None:
        """The HUD's TESTS button — run the suite in a window, inside Perry."""
        try:
            from perry.test_window import TestWindow
            TestWindow(self.hud.root)
        except Exception as e:
            self.hud.set_heard(f"tests unavailable: {e}")

    # --------------------------------------------------------------- lifecycle
    def open_task_manager(self) -> None:
        """Bring the machine's vital signs up, if they aren't already.

        Wrapped in its own method so the tests can override it, and guarded
        so a blocked or missing Task Manager can never stop Perry starting.
        """
        if not self.config.get("task_manager_on_start", True):
            return
        try:
            from perry import system
            report = system.ensure_running(
                self.config.get("task_manager_page", "performance"))
            if report.get("launched"):
                self.hud.set_heard(system.describe(report))
        except Exception:
            pass

    def start(self) -> None:
        # The window comes up first; everything slow (hotkey hook, opening the
        # microphone, Task Manager, session snapshot) happens on threads.
        self._serve_instance()
        threading.Thread(target=self._start_background, daemon=True,
                         name="perry-startup").start()
        self._tick()
        self.hud.run()  # blocks on the tkinter main loop

    def _start_background(self) -> None:
        self.register_hotkey()
        threading.Thread(target=self.open_task_manager, daemon=True).start()

        if self.config.get("voice_enabled", True):
            self.hud.set_status("Warming up...")
            if self.hub.start():
                # Keep the detector's clock in step with the rate the device
                # actually gave us (it isn't always the 16 kHz we asked for).
                self.claps.rate = self.hub.rate
                if self.config.get("clap_enabled", True) and self.claps.available:
                    self.hub.add_raw_listener(self.claps.feed)
                self.listener.start()
                self.hud.set_listening(True)
                self.hud.set_status("Standing by")
            else:
                self.hud.set_status("No microphone — use Ctrl+Alt+P")
                self.hud.set_heard(self.hub.error or "audio unavailable")
                self.hud.show()
        else:
            self.hud.set_status("Voice disabled. Use the hotkey.")
            self.hud.show()

        self.start_phone_link()

        # Capture an initial snapshot so a restore has something to work with.
        self.safe_capture()

    def start_phone_link(self) -> None:
        """Let Perry on the phone wake this PC and send it commands."""
        if not self.config.get("phone_link_enabled", True):
            return
        try:
            from perry.phone_link import PhoneLink, ensure_token
            tok = ensure_token(self.config, config_module.save)
            self.phone_link = PhoneLink(
                self, tok, int(self.config.get("phone_link_port", 47812)))
            if not self.phone_link.start():
                self.hud.set_heard(self.phone_link.error)
        except Exception as e:
            self.hud.set_heard(f"phone link off: {e}")

    def phone_command(self, text: str) -> str:
        """A phrase typed or spoken on the phone. Returns what to say back."""
        from perry import commands
        self.hud.set_heard(f"phone: {text}")
        n = normalize(text)
        if (phrase_matches(text, self.always_on_phrases + self.armed_phrases)
                or ("daddy" in n and "home" in n)):
            self.wake()
            return "Welcome home. Restoring your session."
        reply = commands.respond(text)
        if reply is None:
            reply = "Sorry, I didn't get that. Ask me what I can do."
        self.hud.set_status(reply if len(reply) < 40 else reply[:37] + "...")
        return reply

    def _serve_instance(self) -> None:
        """Answer later launches ("show") so they don't start a second Perry."""
        import socket
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.bind(("127.0.0.1", int(self.config.get("instance_port", 47811))))
            srv.listen(4)
        except OSError:
            return

        def loop():
            while True:
                try:
                    conn, _ = srv.accept()
                    with conn:
                        if conn.recv(16).startswith(b"show"):
                            self.hud.show()
                except OSError:
                    return

        threading.Thread(target=loop, daemon=True, name="perry-instance").start()

    def safe_capture(self) -> None:
        try:
            self.sessions.capture()
        except Exception:
            pass

    def shutdown(self) -> None:
        self.listener.stop()
        self.hub.stop()
        self.safe_capture()  # save on exit so "home" restores it next time
        try:
            self.hud.root.destroy()
        except Exception:
            pass
        sys.exit(0)


def main(args: list[str] | None = None) -> int:
    args = args if args is not None else sys.argv[1:]
    cfg = config_module.load()
    start_hidden = "--show" not in args and cfg.get("start_hidden", True)
    Perry(cfg, start_hidden=start_hidden).start()
    return 0
