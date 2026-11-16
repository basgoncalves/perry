"""
fakes.py — stand-ins for everything that would otherwise need real hardware.

Perry takes all of his collaborators through the constructor, so the tests can
drive the real wake logic with these in place of a display, a microphone and
your actual open applications.
"""

from __future__ import annotations

import numpy as np

RATE = 16000
CHUNK = 512


class FakeHUD:
    """Records what Perry would have displayed."""

    class _Root:
        @staticmethod
        def after(*_a, **_k):
            return None

        @staticmethod
        def destroy():
            return None

    def __init__(self, **_kw):
        self.root = self._Root()
        self.shown = False
        self.mode = "idle"
        self.status = ""
        self.heard = ""
        self.listening = False

    def set_status(self, text): self.status = text
    def set_heard(self, text): self.heard = text
    def set_listening(self, on): self.listening = on
    def set_mode(self, mode): self.mode = mode
    def show(self): self.shown = True
    def hide(self): self.shown = False
    def run(self): pass


class FakeSessions:
    """A session store that counts restores instead of launching apps."""

    def __init__(self, result=None):
        self.captures = 0
        self.restores = 0
        self.result = result or {"status": "restored",
                                 "launched": ["chrome.exe", "code.exe"]}

    def capture(self): self.captures += 1

    def restore(self):
        self.restores += 1
        return self.result


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text): self.said.append(text)
    def say_async(self, text): self.said.append(text)


class FakeHub:
    """An AudioHub that never opens a device."""

    def __init__(self, **_kw):
        self.available = True
        self.rate = RATE
        self.error = None
        self.started = False
        self.raw_listeners = []
        self.streams = []

    def start(self):
        self.started = True
        return True

    def add_raw_listener(self, fn): self.raw_listeners.append(fn)
    def stop(self): self.started = False


class FakeListener:
    def __init__(self, **_kw):
        self.running = False

    def start(self): self.running = True
    def stop(self): self.running = False


# --------------------------------------------------------------------- audio
# Synthetic sound, so the clap tests run identically everywhere.

def rng(seed: int = 7):
    return np.random.default_rng(seed)


def room(n: int, level: float = 0.004, gain: float = 1.0, r=None):
    """Quiet room tone."""
    r = r or rng()
    return r.normal(0, level * gain, n)


def add_clap(buf, at_seconds: float, amp: float = 0.75,
             gain: float = 1.0, tau: float = 0.022, r=None):
    """A clap: instant attack, ~20ms exponential decay, broadband."""
    r = r or rng()
    at = int(at_seconds * RATE)
    dur = int(0.09 * RATE)
    t = np.arange(dur) / RATE
    buf[at:at + dur] += amp * gain * np.exp(-t / tau) * r.normal(0, 1, dur)


def add_speech(buf, at_seconds: float, duration: float = 1.4,
               amp: float = 0.16, gain: float = 1.0):
    """Sustained, syllable-modulated energy — the classic false positive."""
    at = int(at_seconds * RATE)
    n = int(duration * RATE)
    t = np.arange(n) / RATE
    env = 0.6 + 0.4 * np.sin(2 * np.pi * 4.5 * t) ** 2
    carrier = np.sin(2 * np.pi * 190 * t) + 0.5 * np.sin(2 * np.pi * 430 * t)
    buf[at:at + n] += amp * gain * env * carrier


def add_typing(buf, at_seconds: float, keys: int = 14,
               amp: float = 0.30, gain: float = 1.0, r=None):
    """Keystrokes: same sharp attack as a clap, but over in ~6ms."""
    r = r or rng()
    for k in range(keys):
        at = int((at_seconds + k * 0.13) * RATE)
        dur = int(0.012 * RATE)
        t = np.arange(dur) / RATE
        buf[at:at + dur] += amp * gain * np.exp(-t / 0.004) * r.normal(0, 1, dur)


def to_pcm(buf) -> bytes:
    return (np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes()


def feed(detector, buf) -> None:
    """Push a whole buffer through a detector in realistic chunks."""
    ints = (np.clip(buf, -1, 1) * 32767).astype(np.int16)
    for i in range(0, len(ints) - CHUNK, CHUNK):
        detector.feed(ints[i:i + CHUNK].tobytes())
