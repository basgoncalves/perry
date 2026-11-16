"""Perry Online integration: URLs, voice routing, HUD balloon."""
import unittest
from unittest import mock

from perry import web, commands


class WebTests(unittest.TestCase):
    def test_section_urls(self):
        self.assertEqual(web.url_for("port"), web.BASE_URL + "#port")
        self.assertEqual(web.url_for("nonsense"), web.BASE_URL)

    def test_voice_routes_to_sections(self):
        with mock.patch.object(web, "open_section", return_value="ok") as op:
            # VOICE lambdas look open_section up at call time
            for phrase, sec in [("Perry, open portfolio", "port"),
                                ("Perry, open spending", "spend"),
                                ("Perry, open market", "market"),
                                ("Perry online", "perry")]:
                commands.respond(phrase)
                self.assertEqual(op.call_args[0][0], sec, phrase)

    def test_office_still_wins(self):
        with mock.patch.object(commands, "open_office", return_value="x"):
            pass  # office trigger precedes web triggers in COMMANDS
        names = [h.__name__ for _, h in commands.COMMANDS]
        self.assertLess(names.index("open_office"), names.index("<lambda>"))

    def test_hud_has_web_balloon(self):
        try:
            from perry.hud import PerryHUD
        except Exception:
            self.skipTest("no tkinter")
        self.assertIn("web", [a for a, _, _ in PerryHUD.BUILTIN])
