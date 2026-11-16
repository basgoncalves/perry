"""
Task Manager housekeeping.

Nothing here launches Task Manager or writes to your real settings file —
the settings path is redirected at a temporary folder, and the launch and
process-check functions are stubbed. A test suite that opened a window every
time you ran it is a test suite you'd stop running.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from perry import system


class PageNameTests(unittest.TestCase):

    def test_performance_is_page_one(self):
        """The page in the screenshot — second in the list, index 1"""
        self.assertEqual(system.PAGES["performance"], 1)

    def test_the_page_names_match_task_managers_own(self):
        """If Microsoft renumbers these, the mapping is where to look"""
        self.assertEqual(system.PAGES["processes"], 0)
        self.assertEqual(system.PAGES["services"], 6)


class SettingsFileTests(unittest.TestCase):
    """set_default_start_page writes the one key and leaves the rest alone."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "settings.json")
        self._real_path = system.settings_path
        self._real_env = os.environ.get("LOCALAPPDATA")
        system.settings_path = lambda: self.path
        os.environ["LOCALAPPDATA"] = self.tmp.name
        self.addCleanup(self.restore)

    def restore(self):
        system.settings_path = self._real_path
        if self._real_env is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self._real_env

    def read(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def test_it_creates_the_file_if_it_is_missing(self):
        """A machine where Task Manager has never run still gets the setting"""
        self.assertFalse(os.path.exists(self.path))
        self.assertTrue(system.set_default_start_page("performance"))
        self.assertEqual(self.read()["DefaultStartPage"], 1)

    def test_it_keeps_your_other_task_manager_settings(self):
        """Setting the start page must not reset everything else"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"DefaultStartPage": 0, "UpdateSpeed": 2,
                       "AlwaysOnTop": True}, f)
        system.set_default_start_page("performance")
        saved = self.read()
        self.assertEqual(saved["DefaultStartPage"], 1)
        self.assertEqual(saved["UpdateSpeed"], 2)
        self.assertIs(saved["AlwaysOnTop"], True)

    def test_a_corrupt_settings_file_is_replaced_not_obeyed(self):
        """Half-written JSON shouldn't stop Perry setting the page"""
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ not json at all")
        self.assertTrue(system.set_default_start_page("performance"))
        self.assertEqual(self.read()["DefaultStartPage"], 1)

    def test_setting_it_twice_is_a_no_op(self):
        """Already correct means don't touch the file"""
        system.set_default_start_page("performance")
        before = os.path.getmtime(self.path)
        self.assertTrue(system.set_default_start_page("performance"))
        self.assertEqual(os.path.getmtime(self.path), before)

    def test_an_unknown_page_name_is_refused(self):
        """A typo shouldn't silently write a nonsense page number"""
        self.assertFalse(system.set_default_start_page("perfromance"))

    def test_a_number_works_too(self):
        """Callers may pass the index directly"""
        self.assertTrue(system.set_default_start_page(5))
        self.assertEqual(self.read()["DefaultStartPage"], 5)

    def test_reading_back_what_was_written(self):
        """read_default_start_page is the inverse of setting it"""
        system.set_default_start_page("services")
        self.assertEqual(system.read_default_start_page(), 6)


class EnsureRunningTests(unittest.TestCase):
    """The decision: launch, or leave it alone?"""

    def setUp(self):
        self.launched = []
        self._real = (system.is_running, system.launch,
                      system.set_default_start_page, system.is_windows)
        system.is_windows = lambda: True
        system.set_default_start_page = lambda page=1: True
        system.launch = lambda exe="taskmgr": (self.launched.append(exe) or True)
        self.addCleanup(self.restore)

    def restore(self):
        (system.is_running, system.launch,
         system.set_default_start_page, system.is_windows) = self._real

    def test_it_does_not_open_a_second_window(self):
        """Task Manager already up means nothing to do"""
        system.is_running = lambda exe=None: True
        report = system.ensure_running()
        self.assertTrue(report["was_running"])
        self.assertFalse(report["launched"])
        self.assertEqual(self.launched, [])

    def test_it_launches_when_nothing_is_running(self):
        """The case in the request: not open, so open it"""
        system.is_running = lambda exe=None: False
        report = system.ensure_running()
        self.assertFalse(report["was_running"])
        self.assertTrue(report["launched"])
        self.assertEqual(self.launched, ["taskmgr"])

    def test_it_sets_the_page_before_launching(self):
        """The preference has to be written first or it won't take effect"""
        order = []
        system.is_running = lambda exe=None: False
        system.set_default_start_page = lambda page=1: (order.append("page") or True)
        system.launch = lambda exe="taskmgr": (order.append("launch") or True)
        system.ensure_running("performance")
        self.assertEqual(order, ["page", "launch"])

    def test_a_blocked_task_manager_is_reported_not_raised(self):
        """Group policy can forbid it; that's an answer, not a crash"""
        system.is_running = lambda exe=None: False
        system.launch = lambda exe="taskmgr": False
        report = system.ensure_running()
        self.assertFalse(report["launched"])
        self.assertTrue(report["reason"])
        self.assertIn("Task Manager", system.describe(report))

    def test_nothing_happens_off_windows(self):
        """Developing on a Mac shouldn't try to run taskmgr"""
        system.is_windows = lambda: False
        report = system.ensure_running()
        self.assertFalse(report["launched"])
        self.assertEqual(report["reason"], "not Windows")

    def test_describe_says_something_a_person_can_read(self):
        """Every branch produces a sentence, not a dict"""
        system.is_running = lambda exe=None: True
        self.assertIn("already open", system.describe(system.ensure_running()))
        system.is_running = lambda exe=None: False
        self.assertIn("Opened", system.describe(system.ensure_running()))


class ConfigTests(unittest.TestCase):

    def test_the_settings_have_defaults(self):
        """Deleting the keys from config.json can't break startup"""
        from perry import config as config_module

        cfg = config_module.load("/nonexistent/config.json")
        self.assertIn("task_manager_on_start", cfg)
        self.assertEqual(cfg["task_manager_page"], "performance")


if __name__ == "__main__":
    unittest.main()
