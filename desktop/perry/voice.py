"""
voice.py

Speech recognition + text-to-speech for Perry.

The listener no longer owns the microphone — it pulls from the shared AudioHub
so the clap detector can hear the same stream. Recognition runs on its own
worker thread, which keeps the listen loop responsive while a round-trip is in
flight. Matching the wake phrase is deliberately *not* done here: perry.py
decides what a phrase means, because the meaning now depends on whether the
claps have armed him.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None

try:
    import pyttsx3
except ImportError:  # pragma: no cover
    pyttsx3 = None


def normalize(text: str) -> str:
    """
    Reduce a phrase to something matchable.

    Lowercase, collapse runs of whitespace, and flatten punctuation — speech
    recognisers punctuate and pad unpredictably, so "Perry, wake up!",
    "perry   wake up" and "Perry-wake-up" all have to land on the same
    "perry wake up".

    Apostrophes are deleted rather than spaced, so "Daddy's" becomes "daddys"
    and stays one word; everything else becomes a space, so a hyphen or comma
    can't glue two words together.
    """
    lowered = "".join(c for c in text.lower() if c not in "'’`")
    spaced = "".join(c if (c.isalnum() or c.isspace()) else " " for c in lowered)
    return " ".join(spaced.split())


def phrase_matches(text: str, phrases: list[str]) -> bool:
    norm = normalize(text)
    return any(p and p in norm for p in phrases)


class Speaker:
    """
    Offline text-to-speech wrapper.

    say() may be called from background threads (voice listener, hotkey thread,
    tkinter). On Windows the SAPI5 voice is a COM object, so the calling thread
    must initialise COM first; we build a fresh engine per call inside an
    initialised-COM scope. That keeps spoken replies reliable across threads
    instead of silently falling back to print().
    """

    def __init__(self, enabled: bool = True, rate: int = 175):
        self.enabled = enabled and pyttsx3 is not None
        self.rate = rate
        self._lock = threading.Lock()

    def _speak_once(self, text: str) -> bool:
        engine = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception:
            return False
        finally:
            try:
                if engine is not None:
                    engine.stop()
            except Exception:
                pass

    def say(self, text: str) -> None:
        if not self.enabled:
            print(f"[Perry says] {text}")
            return

        com_ready = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_ready = True
        except Exception:
            pass

        try:
            with self._lock:
                if not self._speak_once(text):
                    print(f"[Perry says] {text}")
        finally:
            if com_ready:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def say_async(self, text: str) -> None:
        threading.Thread(target=self.say, args=(text,), daemon=True).start()


class VoiceListener:
    """
    Background phrase listener running on the shared audio hub.

    on_phrase:  called with every recognised phrase
    on_status:  called with diagnostics worth showing on the HUD
    gate:       optional () -> bool; when it returns False, audio is still
                captured but not sent for recognition (saves bandwidth and
                keeps the mic off the network until Perry is armed)
    """

    def __init__(
        self,
        hub,
        on_phrase: Callable[[str], None],
        on_status: Callable[[str], None] | None = None,
        listen_timeout: int = 6,
        phrase_time_limit: int = 5,
        gate: Callable[[], bool] | None = None,
    ):
        self.hub = hub
        self.on_phrase = on_phrase
        self.on_status = on_status or (lambda _t: None)
        self.listen_timeout = listen_timeout
        self.phrase_time_limit = phrase_time_limit
        self.gate = gate or (lambda: True)

        self.available = sr is not None and hub.available
        self._thread: threading.Thread | None = None
        self._worker: threading.Thread | None = None
        self._jobs: queue.Queue = queue.Queue(maxsize=4)
        self._running = False

        if sr is not None:
            self._recognizer = sr.Recognizer()
            self._recognizer.dynamic_energy_threshold = True

    def start(self) -> None:
        if not self.available:
            if sr is None:
                self.on_status("voice off: SpeechRecognition not installed")
            else:
                self.on_status("voice off: no microphone — use Ctrl+Alt+P")
            return
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._recognize_loop, daemon=True,
                                        name="perry-recognize")
        self._worker.start()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True,
                                        name="perry-listen")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------ loops
    def _listen_loop(self) -> None:
        try:
            source = self.hub.source()
        except Exception as e:
            self.on_status(f"audio source error: {e}")
            return

        with source as s:
            try:
                self._recognizer.adjust_for_ambient_noise(s, duration=0.8)
            except Exception:
                pass

            while self._running:
                try:
                    audio = self._recognizer.listen(
                        s,
                        timeout=self.listen_timeout,
                        phrase_time_limit=self.phrase_time_limit,
                    )
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    continue

                if not self.gate():
                    continue
                try:
                    self._jobs.put_nowait(audio)
                except queue.Full:
                    pass  # already backed up; this phrase can go

    def _recognize_loop(self) -> None:
        while self._running:
            try:
                audio = self._jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                text = self._recognizer.recognize_google(audio)
            except Exception:
                continue  # unintelligible, or a network hiccup — keep listening
            if text:
                try:
                    self.on_phrase(text)
                except Exception:
                    pass
