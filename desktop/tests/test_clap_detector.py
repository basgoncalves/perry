"""
Does the clap detector fire on claps and stay quiet on everything else?

Every case runs twice: once at full volume, and once at 0.25x to emulate a
quiet microphone. The quiet pass is the one that matters — it's the setup that
forced the loudness gate down to 0.012, which in turn is why the pulse-width
gate exists at all.
"""

from __future__ import annotations

import unittest

from perry.clap_detector import ClapDetector
from tests import fakes

QUIET_MIC = 0.25   # this machine's mic: a clap peaks around 0.02 RMS


class ClapDetectorTests(unittest.TestCase):

    def detect(self, buf, **overrides) -> int:
        """Run a buffer through a detector; return how many times it fired."""
        fired = []
        settings = dict(claps_required=2, rate=fakes.RATE, sensitivity=5.0,
                        abs_floor=0.012, min_width_ms=12,
                        min_gap_ms=80, max_gap_ms=900)
        settings.update(overrides)
        det = ClapDetector(on_claps=lambda: fired.append(1), **settings)
        fakes.feed(det, buf)
        return len(fired)

    # ------------------------------------------------------------ should fire
    def test_two_claps_wakes(self):
        """Two claps 300ms apart trigger"""
        for gain in (1.0, QUIET_MIC):
            with self.subTest(gain=gain):
                buf = fakes.room(fakes.RATE * 5, gain=gain)
                fakes.add_clap(buf, 1.5, gain=gain)
                fakes.add_clap(buf, 1.8, gain=gain)
                self.assertEqual(self.detect(buf), 1)

    def test_slower_claps_wake(self):
        """Two claps 600ms apart still trigger"""
        buf = fakes.room(fakes.RATE * 5)
        fakes.add_clap(buf, 1.5)
        fakes.add_clap(buf, 2.1)
        self.assertEqual(self.detect(buf), 1)

    def test_distant_claps_wake(self):
        """Quiet claps from across the room trigger"""
        buf = fakes.room(fakes.RATE * 5, gain=QUIET_MIC)
        fakes.add_clap(buf, 1.5, amp=0.22, gain=QUIET_MIC)
        fakes.add_clap(buf, 1.85, amp=0.22, gain=QUIET_MIC)
        self.assertEqual(self.detect(buf), 1)

    def test_claps_over_speech_wake(self):
        """Clapping mid-sentence still triggers"""
        for gain in (1.0, QUIET_MIC):
            with self.subTest(gain=gain):
                buf = fakes.room(fakes.RATE * 6, gain=gain)
                fakes.add_speech(buf, 0.5, duration=4.0, gain=gain)
                fakes.add_clap(buf, 2.0, gain=gain)
                fakes.add_clap(buf, 2.32, gain=gain)
                self.assertEqual(self.detect(buf), 1)

    # -------------------------------------------------------- should NOT fire
    def test_single_clap_does_nothing(self):
        """One clap is not enough"""
        buf = fakes.room(fakes.RATE * 5)
        fakes.add_clap(buf, 1.5)
        self.assertEqual(self.detect(buf), 0)

    def test_claps_too_far_apart_do_nothing(self):
        """Claps 2.5s apart are separate events, not a double"""
        buf = fakes.room(fakes.RATE * 7)
        fakes.add_clap(buf, 1.5)
        fakes.add_clap(buf, 4.0)
        self.assertEqual(self.detect(buf), 0)

    def test_speech_does_not_wake(self):
        """Talking never triggers"""
        for gain in (1.0, QUIET_MIC):
            with self.subTest(gain=gain):
                buf = fakes.room(fakes.RATE * 6, gain=gain)
                fakes.add_speech(buf, 1.0, gain=gain)
                fakes.add_speech(buf, 3.0, gain=gain)
                self.assertEqual(self.detect(buf), 0)

    def test_typing_does_not_wake(self):
        """Keystrokes are too short to be claps"""
        for gain in (1.0, QUIET_MIC):
            with self.subTest(gain=gain):
                buf = fakes.room(fakes.RATE * 6, gain=gain)
                fakes.add_typing(buf, 1.0, gain=gain)
                self.assertEqual(self.detect(buf), 0)

    def test_steady_noise_does_not_wake(self):
        """A fan or loud room never triggers"""
        buf = fakes.room(fakes.RATE * 6, level=0.09)
        self.assertEqual(self.detect(buf), 0)

    # ------------------------------------------------------------------ knobs
    def test_width_gate_is_what_rejects_typing(self):
        """Dropping the width gate is what lets typing through"""
        buf = fakes.room(fakes.RATE * 6, gain=QUIET_MIC)
        fakes.add_typing(buf, 1.0, gain=QUIET_MIC)
        self.assertEqual(self.detect(buf), 0)
        self.assertGreater(self.detect(buf, min_width_ms=0), 0,
                           "typing should slip through once the width gate is off — "
                           "if it doesn't, this test no longer proves anything")

    def test_reset_clears_a_pending_clap(self):
        """reset() forgets a half-finished double clap"""
        fired = []
        det = ClapDetector(on_claps=lambda: fired.append(1), claps_required=2,
                           rate=fakes.RATE, abs_floor=0.012)
        buf = fakes.room(fakes.RATE * 3)
        fakes.add_clap(buf, 1.0)
        fakes.feed(det, buf)
        det.reset()
        buf2 = fakes.room(fakes.RATE * 3)
        fakes.add_clap(buf2, 1.0)
        fakes.feed(det, buf2)
        self.assertEqual(len(fired), 0)


if __name__ == "__main__":
    unittest.main()
