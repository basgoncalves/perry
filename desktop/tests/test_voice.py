"""
Phrase matching — can Perry recognise what a speech recogniser actually returns?

Google's transcriptions are messier than the phrase you configured: stray
punctuation, doubled spaces, inconsistent capitalisation, sometimes a wrong
homophone. Everything here is a shape a recogniser genuinely produces.
"""

from __future__ import annotations

import unittest

from perry.voice import normalize, phrase_matches


class NormalizeTests(unittest.TestCase):

    def test_lowercases(self):
        """Capitalisation is irrelevant"""
        self.assertEqual(normalize("PERRY Wake Up"), "perry wake up")

    def test_drops_punctuation(self):
        """Commas and exclamation marks don't count"""
        self.assertEqual(normalize("Perry, wake up!"), "perry wake up")

    def test_collapses_repeated_spaces(self):
        """Doubled spaces collapse to one"""
        self.assertEqual(normalize("perry   wake  up"), "perry wake up")

    def test_hyphens_become_spaces(self):
        """A hyphen separates words rather than gluing them"""
        self.assertEqual(normalize("Perry-wake-up"), "perry wake up")

    def test_apostrophes_are_deleted_not_spaced(self):
        """Daddy's stays one word"""
        self.assertEqual(normalize("Perry, Daddy's home"), "perry daddys home")

    def test_curly_apostrophes_too(self):
        """A typographic apostrophe behaves like a straight one"""
        self.assertEqual(normalize("Daddy’s"), normalize("Daddy's"))

    def test_trims_the_edges(self):
        """Leading and trailing space is ignored"""
        self.assertEqual(normalize("  perry wake up  "), "perry wake up")


class PhraseMatchTests(unittest.TestCase):

    WAKE = [normalize(p) for p in
            ["perry wake up", "berry wake up", "hey perry wake up"]]
    HOME = [normalize(p) for p in ["perry daddys home", "perry daddy is home"]]

    def test_matches_real_transcriptions(self):
        """Phrases a recogniser actually returns are recognised"""
        for heard in ["Perry wake up", "Perry, wake up!", "PERRY WAKE UP",
                      "perry   wake up", "Berry wake up",
                      "hey perry wake up", "ok so, perry wake up now"]:
            with self.subTest(heard=heard):
                self.assertTrue(phrase_matches(heard, self.WAKE))

    def test_ignores_everything_else(self):
        """Ordinary conversation doesn't match"""
        for heard in ["what time is it", "perry is a nice name",
                      "wake up honey", "carry that up the stairs",
                      "i'll wake up early"]:
            with self.subTest(heard=heard):
                self.assertFalse(phrase_matches(heard, self.WAKE))

    def test_the_apostrophe_phrase_matches(self):
        """'Perry, Daddy's home' matches however it's punctuated"""
        for heard in ["Perry, Daddy's home", "perry daddys home",
                      "Perry Daddy’s home", "Perry daddy is home"]:
            with self.subTest(heard=heard):
                self.assertTrue(phrase_matches(heard, self.HOME))

    def test_an_empty_phrase_list_never_matches(self):
        """No configured phrases means nothing wakes him"""
        self.assertFalse(phrase_matches("perry wake up", []))

    def test_empty_entries_are_ignored(self):
        """A blank alias in config.json can't match everything"""
        self.assertFalse(phrase_matches("hello there", ["", "  "]))


if __name__ == "__main__":
    unittest.main()
