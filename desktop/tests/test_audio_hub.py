"""
Does the shared microphone actually satisfy SpeechRecognition's contract?

The hub exists because two PyAudio input streams on one Windows device is
unreliable, so clap detection and speech recognition have to share. The risky
part is HubSource pretending to be an sr.AudioSource well enough that
Recognizer.listen() is happy. These tests check that against the real library
when it's installed, and check the backpressure behaviour always.
"""

from __future__ import annotations

import threading
import time
import unittest

from perry import audio_hub
from perry.audio_hub import AudioHub, _HubStream
from tests import fakes

try:
    import speech_recognition as sr
except ImportError:
    sr = None


def pcm(level: float, n: int) -> bytes:
    return fakes.to_pcm(fakes.rng(3).normal(0, level, n))


class HubStreamTests(unittest.TestCase):

    def test_read_returns_exactly_what_was_asked_for(self):
        """read(n) always hands back n frames"""
        s = _HubStream()
        for _ in range(10):
            s.feed(pcm(0.01, 512))
        data = s.read(300)
        self.assertEqual(len(data), 300 * audio_hub.SAMPLE_WIDTH)

    def test_reads_can_straddle_chunk_boundaries(self):
        """A read larger than one chunk is stitched together"""
        s = _HubStream()
        for _ in range(4):
            s.feed(pcm(0.01, 512))
        self.assertEqual(len(s.read(1500)), 1500 * audio_hub.SAMPLE_WIDTH)

    def test_a_stalled_consumer_never_blocks_capture(self):
        """Feeding a consumer that never reads must not hang the mic thread"""
        s = _HubStream()
        started = time.monotonic()
        for _ in range(5000):
            s.feed(pcm(0.01, 512))
        self.assertLess(time.monotonic() - started, 5.0)

    def test_a_dead_mic_returns_silence_rather_than_hanging(self):
        """If the device stops, reads fall back to silence"""
        s = _HubStream()
        s.close()
        self.assertEqual(s.read(64), b"\x00" * 64 * audio_hub.SAMPLE_WIDTH)


class HubFanOutTests(unittest.TestCase):

    def test_raw_listeners_and_streams_both_get_the_audio(self):
        """One chunk reaches every consumer"""
        hub = AudioHub()
        hub.available = True
        seen = []
        hub.add_raw_listener(seen.append)
        stream = hub._attach_stream()

        chunk = pcm(0.01, 512)
        for fn in hub._raw_listeners:
            fn(chunk)
        stream.feed(chunk)

        self.assertEqual(len(seen), 1)
        self.assertEqual(len(stream.read(512)), 512 * audio_hub.SAMPLE_WIDTH)

    def test_sources_detach_cleanly(self):
        """Leaving the with-block releases the stream"""
        hub = AudioHub()
        hub.available = True
        with hub.source():
            self.assertEqual(len(hub._streams), 1)
        self.assertEqual(hub._streams, [])


@unittest.skipIf(sr is None, "SpeechRecognition not installed")
class SpeechRecognitionContractTests(unittest.TestCase):

    def test_recognizer_can_listen_to_the_hub(self):
        """Recognizer.listen() accepts HubSource and captures a phrase"""
        hub = AudioHub()
        hub.available = True

        def pump():
            def fan(data):
                for s in list(hub._streams):
                    s.feed(data)
            for _ in range(int(0.8 * fakes.RATE / fakes.CHUNK)):
                fan(pcm(0.002, fakes.CHUNK)); time.sleep(0.003)
            for _ in range(int(1.2 * fakes.RATE / fakes.CHUNK)):
                fan(pcm(0.20, fakes.CHUNK)); time.sleep(0.003)
            for _ in range(int(2.0 * fakes.RATE / fakes.CHUNK)):
                fan(pcm(0.002, fakes.CHUNK)); time.sleep(0.003)

        recognizer = sr.Recognizer()
        with hub.source() as source:
            self.assertIsInstance(source, sr.AudioSource)
            self.assertIsNotNone(source.stream)
            threading.Thread(target=pump, daemon=True).start()
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)

        seconds = len(audio.frame_data) / audio.sample_width / audio.sample_rate
        self.assertGreater(seconds, 0.4)
        self.assertLess(seconds, 5.0)
        self.assertGreater(len(audio.get_wav_data()), 1000)


if __name__ == "__main__":
    unittest.main()
