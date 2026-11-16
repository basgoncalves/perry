"""
audio_hub.py

One microphone, several consumers.

Perry now needs the mic for two jobs at the same time: spotting claps (raw
amplitude transients) and recognising the wake phrase (SpeechRecognition).
Opening two PyAudio input streams on the same device is flaky on Windows —
one of them usually ends up starved or errors out — so this module opens the
microphone exactly once and fans every chunk out to:

  1. raw frame listeners  ->  ClapDetector
  2. a HubSource          ->  a drop-in sr.AudioSource for Recognizer.listen()

The capture thread never blocks on a consumer. Each recogniser gets its own
bounded queue and simply drops the oldest audio if it ever falls behind (which
happens while a recognition round-trip is in flight).
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

try:
    import pyaudio
except ImportError:  # pragma: no cover
    pyaudio = None

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None


SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2      # 16-bit signed
CHUNK_FRAMES = 512    # 32 ms at 16 kHz — short enough to resolve a clap's attack


class _HubStream:
    """A file-like audio stream fed by the hub, read by SpeechRecognition."""

    def __init__(self, maxsize: int = 240):
        self._q: queue.Queue[bytes] = queue.Queue(maxsize=maxsize)
        self._buf = bytearray()
        self.closed = False

    def feed(self, data: bytes) -> None:
        try:
            self._q.put_nowait(data)
        except queue.Full:
            # Consumer is behind (usually a recognition round-trip). Drop the
            # oldest chunk rather than stalling the capture thread.
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(data)
            except queue.Full:
                pass

    def read(self, size: int, *_args, **_kwargs) -> bytes:
        """Return exactly `size` frames' worth of bytes (blocking)."""
        want = int(size) * SAMPLE_WIDTH
        while len(self._buf) < want:
            if self.closed:
                self._buf.extend(b"\x00" * (want - len(self._buf)))
                break
            try:
                self._buf.extend(self._q.get(timeout=1.0))
            except queue.Empty:
                # Mic stalled — hand back silence so the recogniser's loop
                # keeps turning instead of hanging forever.
                self._buf.extend(b"\x00" * (want - len(self._buf)))
        out = bytes(self._buf[:want])
        del self._buf[:want]
        return out

    def close(self) -> None:
        self.closed = True


_SourceBase = sr.AudioSource if sr is not None else object


class HubSource(_SourceBase):  # type: ignore[misc]
    """
    An sr.AudioSource backed by the hub instead of by its own PyAudio stream.

    Use it exactly like sr.Microphone():

        with hub.source() as source:
            audio = recognizer.listen(source)
    """

    def __init__(self, hub: "AudioHub"):
        self._hub = hub
        self.CHUNK = hub.chunk
        self.SAMPLE_RATE = hub.rate
        self.SAMPLE_WIDTH = SAMPLE_WIDTH
        self.stream: _HubStream | None = None

    def __enter__(self) -> "HubSource":
        self.stream = self._hub._attach_stream()
        return self

    def __exit__(self, *_exc) -> None:
        if self.stream is not None:
            self._hub._detach_stream(self.stream)
            self.stream.close()
        self.stream = None


class AudioHub:
    """Owns the microphone. Start it once, attach as many consumers as you like."""

    def __init__(self, device_index: int | None = None,
                 rate: int = SAMPLE_RATE, chunk: int = CHUNK_FRAMES):
        self.available = pyaudio is not None
        self.device_index = device_index
        self.rate = rate
        self.chunk = chunk
        self.error: str | None = None if self.available else "PyAudio not installed"

        self._raw_listeners: list[Callable[[bytes], None]] = []
        self._streams: list[_HubStream] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._pa = None
        self._stream = None

    # ------------------------------------------------------------- consumers
    def add_raw_listener(self, fn: Callable[[bytes], None]) -> None:
        with self._lock:
            self._raw_listeners.append(fn)

    def source(self) -> HubSource:
        return HubSource(self)

    def _attach_stream(self) -> _HubStream:
        s = _HubStream()
        with self._lock:
            self._streams.append(s)
        return s

    def _detach_stream(self, s: _HubStream) -> None:
        with self._lock:
            if s in self._streams:
                self._streams.remove(s)

    # ------------------------------------------------------------- lifecycle
    def _open(self) -> bool:
        assert pyaudio is not None
        self._pa = pyaudio.PyAudio()
        for rate in (self.rate, None):
            try:
                if rate is None:
                    info = self._pa.get_default_input_device_info()
                    rate = int(info.get("defaultSampleRate", 44100))
                self._stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=int(rate),
                    input=True,
                    frames_per_buffer=self.chunk,
                    input_device_index=self.device_index,
                )
                self.rate = int(rate)
                return True
            except Exception as e:  # try the device's own default rate next
                self.error = f"microphone: {e}"
                self._stream = None
        return False

    def start(self) -> bool:
        if not self.available:
            return False
        if self._running:
            return True
        if not self._open():
            return False
        self.error = None
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="perry-audio-hub")
        self._thread.start()
        return True

    def _loop(self) -> None:
        while self._running:
            try:
                data = self._stream.read(self.chunk, exception_on_overflow=False)
            except Exception as e:
                self.error = f"microphone read failed: {e}"
                break
            with self._lock:
                listeners = list(self._raw_listeners)
                streams = list(self._streams)
            for fn in listeners:
                try:
                    fn(data)
                except Exception:
                    pass  # a bad consumer must never kill the mic
            for s in streams:
                s.feed(data)

    def stop(self) -> None:
        self._running = False
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            if self._pa is not None:
                self._pa.terminate()
        except Exception:
            pass
        self._stream = None
        self._pa = None
