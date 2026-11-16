"""
Config loading — a hand-edited config.json should never stop Perry starting.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from perry import config as config_module


class ConfigTests(unittest.TestCase):

    def write(self, text: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(os.unlink, path)
        return path

    def test_a_missing_file_gives_defaults(self):
        """No config.json still starts"""
        cfg = config_module.load("/nonexistent/config.json")
        self.assertEqual(cfg["wake_phrase"], "perry wake up")

    def test_broken_json_gives_defaults(self):
        """A half-edited config falls back instead of crashing"""
        cfg = config_module.load(self.write("{ oops not json"))
        self.assertEqual(cfg["claps_required"], 2)

    def test_a_partial_file_keeps_the_other_defaults(self):
        """Setting one key doesn't wipe the rest"""
        cfg = config_module.load(self.write('{"clap_min_level": 0.05}'))
        self.assertEqual(cfg["clap_min_level"], 0.05)
        self.assertEqual(cfg["arm_window_seconds"], 8)

    def test_the_shipped_config_parses(self):
        """The real config.json is valid and complete"""
        with open(config_module.CONFIG_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        unknown = set(raw) - set(config_module.DEFAULTS)
        self.assertEqual(unknown, set(), f"config.json has unknown keys: {unknown}")

    def test_round_trip(self):
        """Saving then loading gives back what you saved"""
        path = self.write("{}")
        cfg = config_module.load(path)
        cfg["clap_min_level"] = 0.033
        config_module.save(cfg, path)
        self.assertEqual(config_module.load(path)["clap_min_level"], 0.033)


if __name__ == "__main__":
    unittest.main()
