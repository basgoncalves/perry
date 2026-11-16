"""
Does Perry wake for the right things, and only the right things?

This drives the real Perry class with fake collaborators, so the arm-window
state machine, the phrase matching and the restore call are all genuinely
exercised — nothing here is a mock of Perry himself.
"""

from __future__ import annotations

import time
import unittest

from perry import config as config_module
from perry.app import Perry
from tests import fakes


class WakeRoutingTests(unittest.TestCase):

    def setUp(self):
        cfg = config_module.load()
        cfg["require_claps"] = True  # these tests cover clap mode
        for k in ("wake_phrase", "wake_phrase_aliases", "always_on_phrases"):
            cfg[k] = config_module.DEFAULTS[k]  # your config.json may have them off
        self.hud = fakes.FakeHUD()
        self.sessions = fakes.FakeSessions()
        self.speaker = fakes.FakeSpeaker()
        self.perry = Perry(
            cfg, start_hidden=True,
            hud=self.hud, sessions=self.sessions, speaker=self.speaker,
            hub=fakes.FakeHub(), listener=fakes.FakeListener(),
            chime_fn=lambda *_a, **_k: None,
        )

    def settle(self, seconds: float = 0.5):
        """wake() restores on a background thread; give it a moment."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.sessions.restores:
                return
            time.sleep(0.01)

    def wake_via_claps(self, phrase: str = "perry wake up"):
        self.perry.on_claps()
        self.perry.on_phrase(phrase)
        self.settle()

    # ------------------------------------------------------------- the gate
    def test_phrase_alone_does_not_wake(self):
        """Saying the phrase without clapping is ignored"""
        self.perry.on_phrase("Perry wake up")
        self.settle(0.2)
        self.assertEqual(self.sessions.restores, 0)
        self.assertIn("clap twice", self.hud.heard)

    def test_claps_alone_do_not_wake(self):
        """Clapping alone arms him but restores nothing"""
        self.perry.on_claps()
        self.settle(0.2)
        self.assertTrue(self.perry.is_armed())
        self.assertEqual(self.hud.mode, "armed")
        self.assertTrue(self.hud.shown)
        self.assertEqual(self.sessions.restores, 0)

    def test_claps_then_phrase_wakes(self):
        """Two claps then the phrase restores the session"""
        self.wake_via_claps()
        self.assertEqual(self.sessions.restores, 1)
        self.assertEqual(self.hud.mode, "awake")

    def test_waking_disarms(self):
        """He doesn't stay armed after waking"""
        self.wake_via_claps()
        self.assertFalse(self.perry.is_armed())

    def test_arm_window_expires(self):
        """Saying the phrase too late does nothing"""
        self.perry.on_claps()
        self.perry._armed_until = time.monotonic() - 1
        self.assertFalse(self.perry.is_armed())
        self.perry.on_phrase("perry wake up")
        self.settle(0.2)
        self.assertEqual(self.sessions.restores, 0)

    def test_disarm_hides_the_hud(self):
        """When the window lapses the orb goes away"""
        self.perry.on_claps()
        self.perry.disarm()
        self.assertFalse(self.hud.shown)
        self.assertEqual(self.hud.mode, "idle")

    # --------------------------------------------------------- what he hears
    def test_messy_transcriptions_still_work(self):
        """Real Google transcriptions of the phrase are recognised"""
        for heard in ["Perry, wake up!", "Berry wake up", "hey perry wake up",
                      "PERRY WAKE UP", "perry   wake up"]:
            with self.subTest(heard=heard):
                self.setUp()
                self.wake_via_claps(heard)
                self.assertEqual(self.sessions.restores, 1)

    def test_chatter_while_armed_is_ignored(self):
        """Unrelated talk while armed doesn't wake him"""
        self.perry.on_claps()
        for junk in ["what time is it", "perry is a nice name",
                     "wake up honey", "carry that up the stairs"]:
            self.perry.on_phrase(junk)
        self.settle(0.2)
        self.assertEqual(self.sessions.restores, 0)

    def test_always_on_phrase_needs_no_claps(self):
        """'Perry, Daddy's home' still works on its own"""
        self.perry.on_phrase("Perry, Daddy's home")
        self.settle()
        self.assertEqual(self.sessions.restores, 1)

    # -------------------------------------------------------------- reporting
    def test_first_ever_wake_captures_instead(self):
        """With no saved session he snapshots the current one"""
        self.perry.report_restore({"status": "no_session"})
        self.assertEqual(self.sessions.captures, 1)
        self.assertIn("No saved session", self.hud.status)

    def test_restore_reports_the_count(self):
        """He says how many apps came back"""
        self.perry.report_restore({"status": "restored",
                                   "launched": ["a.exe", "b.exe", "c.exe"]})
        self.assertIn("3", self.hud.status)

    def test_restore_failure_is_survivable(self):
        """A crash inside restore() doesn't take Perry down"""
        def boom():
            raise RuntimeError("disk on fire")
        self.perry.sessions.restore = boom
        self.perry._do_restore()
        self.assertIn("disk on fire", self.hud.status)

    # ----------------------------------------------------------------- gating
    def test_recognition_gate_follows_the_setting(self):
        """recognize_only_when_armed keeps audio offline until you clap"""
        self.perry.config["recognize_only_when_armed"] = True
        self.assertFalse(self.perry._recognition_gate())
        self.perry.on_claps()
        self.assertTrue(self.perry._recognition_gate())


if __name__ == "__main__":
    unittest.main()
