"""SFX Lab: synthesis, cue parsing, mixing, routing (no ffmpeg needed)."""
import unittest

from perry import sfx, commands


class SfxTests(unittest.TestCase):
    def test_every_effect_is_audible_and_bounded(self):
        for k in sfx.EFFECTS:
            x = sfx.make(k)
            self.assertGreater(len(x), 100, k)
            self.assertLessEqual(abs(x).max(), 1.0, k)
            self.assertGreater(abs(x).max(), 0.5, k)

    def test_parse_roundtrip(self):
        cues = sfx.parse_cues("# hi\n2 whoosh\n0.5 click 0.4\n")
        self.assertEqual(cues, [(0.5, "click", 0.4), (2.0, "whoosh", 1.0)])
        self.assertEqual(sfx.parse_cues(sfx.format_cues(cues)), cues)

    def test_bad_cue_is_reported(self):
        with self.assertRaises(ValueError):
            sfx.parse_cues("1.0 kaboom")

    def test_mix_places_sound_at_time(self):
        out = sfx.mix([(1.0, "click", 1.0)], 2.0)
        before, at = abs(out[:sfx.SR // 2]).max(), abs(out[sfx.SR:sfx.SR + 2000]).max()
        self.assertEqual(before, 0)
        self.assertGreater(at, 0.3)

    def test_voice_routes_to_sfx(self):
        self.assertEqual(commands.respond("Perry, sound effects"), commands.open_sfx())
