"""
Abilities — Perry finding the programs that live beside him.

Stdlib only, deliberately. These run inside Perry's `.venv`, which has no
pandas and no Streamlit, so nothing here may import a line of Scrooge. That
restriction is the whole design being enforced: if a test in Perry's suite
ever needed Scrooge's dependencies, the boundary would already be broken.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from perry import config as config_module
from perry.abilities import scrooge


class PathResolutionTests(unittest.TestCase):

    def test_the_default_path_is_a_sibling_of_the_perry_folder(self):
        """../scrooge means next to Perry, not inside it"""
        resolved = scrooge.scrooge_dir({})
        self.assertEqual(os.path.basename(resolved), "scrooge")
        self.assertEqual(os.path.dirname(resolved), scrooge.LAUNCHER_ROOT)
        self.assertNotEqual(resolved, scrooge.PERRY_ROOT)

    def test_a_relative_path_is_resolved_against_the_perry_folder(self):
        """Moving the whole folder somewhere else keeps the link intact"""
        resolved = scrooge.scrooge_dir({"scrooge_path": "../elsewhere"})
        self.assertEqual(
            resolved, os.path.normpath(
                os.path.join(scrooge.PERRY_ROOT, "../elsewhere")))

    def test_an_absolute_path_is_used_as_given(self):
        """Point it at a drive somewhere else and it goes there"""
        target = os.path.abspath(os.sep + os.path.join("somewhere", "scrooge"))
        self.assertEqual(scrooge.scrooge_dir({"scrooge_path": target}),
                         os.path.normpath(target))


class AvailabilityTests(unittest.TestCase):

    def test_a_missing_folder_is_not_an_error(self):
        """A deleted ability reads as absent, not broken"""
        self.assertFalse(
            scrooge.is_available({"scrooge_path": "/nonexistent/scrooge"}))

    def test_an_empty_folder_does_not_count_as_installed(self):
        """A half-finished move shouldn't look like a working install"""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(scrooge.is_available({"scrooge_path": tmp}))
            with open(os.path.join(tmp, "__main__.py"), "w") as f:
                f.write("")
            self.assertTrue(scrooge.is_available({"scrooge_path": tmp}))

    def test_disabling_it_in_config_switches_it_off(self):
        """scrooge_enabled: false wins even when the folder is there"""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "__main__.py"), "w") as f:
                f.write("")
            cfg = {"scrooge_path": tmp, "scrooge_enabled": False}
            self.assertTrue(scrooge.is_available(cfg))
            self.assertFalse(scrooge.is_enabled(cfg))

    def test_launching_a_missing_ability_fails_instead_of_raising(self):
        """A wrong path gives a non-zero return, not a traceback"""
        self.assertEqual(
            scrooge.launch({"scrooge_path": "/nonexistent/scrooge"}), 1)


class InstalledScroogeTests(unittest.TestCase):
    """The integration check: is the real Scrooge actually where Perry looks?"""

    def setUp(self):
        self.cfg = config_module.load()
        if not self.cfg.get("scrooge_enabled", True):
            self.skipTest("Scrooge is switched off in config.json")

    def test_scrooge_is_where_perry_expects_it(self):
        """The shipped folder is found at the configured path"""
        self.assertTrue(
            scrooge.is_available(self.cfg),
            f"No Scrooge at {scrooge.scrooge_dir(self.cfg)} — move it there, "
            'fix "scrooge_path", or set "scrooge_enabled": false')

    def test_scrooge_has_the_pieces_perry_relies_on(self):
        """__main__.py and bootstrap.py are both present"""
        target = scrooge.scrooge_dir(self.cfg)
        for name in ("__main__.py", "bootstrap.py", "requirements.txt"):
            self.assertTrue(os.path.isfile(os.path.join(target, name)),
                            f"scrooge/{name} is missing")


class ConfigTests(unittest.TestCase):

    def test_the_ability_settings_have_defaults(self):
        """Deleting the keys from config.json can't break the launch"""
        cfg = config_module.load("/nonexistent/config.json")
        self.assertIn("scrooge_enabled", cfg)
        self.assertEqual(cfg["scrooge_path"], "../scrooge")


if __name__ == "__main__":
    unittest.main()
