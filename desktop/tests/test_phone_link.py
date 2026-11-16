"""Phone link: token check, wake and command routing, real HTTP round trip."""

from __future__ import annotations

import json
import time
import unittest
import urllib.error
import urllib.request

from perry import config as config_module
from perry.app import Perry
from perry.phone_link import PhoneLink, ensure_token
from tests import fakes


class PhoneLinkTests(unittest.TestCase):

    def setUp(self):
        cfg = config_module.load()
        cfg["phone_link_enabled"] = False  # we start our own link below
        self.sessions = fakes.FakeSessions()
        self.hud = fakes.FakeHUD()
        self.perry = Perry(
            cfg, start_hidden=True, hud=self.hud, sessions=self.sessions,
            speaker=fakes.FakeSpeaker(), hub=fakes.FakeHub(),
            listener=fakes.FakeListener(), chime_fn=lambda *_a, **_k: None)
        self.link = PhoneLink(self.perry, "secret-token", port=0, host="127.0.0.1")

    def tearDown(self):
        self.link.stop()

    def settle(self):
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not self.sessions.restores:
            time.sleep(0.02)

    def test_token_is_created_once_and_saved(self):
        saved = []
        cfg = {"phone_link_token": ""}
        tok = ensure_token(cfg, saved.append)
        self.assertGreaterEqual(len(tok), 16)
        self.assertEqual(ensure_token(cfg, saved.append), tok)
        self.assertEqual(len(saved), 1)

    def test_rejects_missing_or_wrong_token(self):
        self.assertFalse(self.link.authorized(None))
        self.assertFalse(self.link.authorized("nope"))
        self.assertTrue(self.link.authorized("secret-token"))

    def test_wake_endpoint_restores_session(self):
        code, out = self.link.handle("POST", "/wake", {})
        self.assertEqual(code, 200)
        self.settle()
        self.assertEqual(self.sessions.restores, 1)

    def test_daddys_home_command_wakes(self):
        for phrase in ("Perry, Daddy's home", "perry daddy is home"):
            with self.subTest(phrase=phrase):
                code, out = self.link.handle("POST", "/command", {"text": phrase})
                self.assertEqual(code, 200)
                self.assertIn("Welcome home", out["reply"])
        self.settle()
        self.assertGreaterEqual(self.sessions.restores, 1)

    def test_other_commands_reply_without_restoring(self):
        code, out = self.link.handle("POST", "/command", {"text": "perry blorp"})
        self.assertEqual(code, 200)
        self.assertTrue(out["reply"])
        self.assertEqual(self.sessions.restores, 0)

    def test_empty_command_and_unknown_path(self):
        self.assertEqual(self.link.handle("POST", "/command", {})[0], 400)
        self.assertEqual(self.link.handle("GET", "/nothing", {})[0], 404)

    def test_http_round_trip(self):
        self.assertTrue(self.link.start())
        port = self.link.server.server_address[1]

        def call(path, token, data=None):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}",
                data=json.dumps(data).encode() if data is not None else None,
                headers={"X-Perry-Token": token,
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status, json.loads(r.read())

        status, out = call("/ping", "secret-token")
        self.assertEqual((status, out["ok"]), (200, True))
        with self.assertRaises(urllib.error.HTTPError) as cm:
            call("/ping", "wrong")
        self.assertEqual(cm.exception.code, 401)
        status, _ = call("/wake", "secret-token", {})
        self.assertEqual(status, 200)
        self.settle()
        self.assertEqual(self.sessions.restores, 1)


if __name__ == "__main__":
    unittest.main()
