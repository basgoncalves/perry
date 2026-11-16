"""
runner.py

Runs Perry's test suite and reports results as they happen.

There's one runner behind both front-ends — `python . --tests` in a terminal
and the TESTS button on the HUD — so what you see in the app is exactly what
CI-style command line output would show. `run()` takes an `emit` callback and
streams events to it rather than printing, which is what lets the GUI update
live instead of freezing until the whole suite finishes.
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from typing import Callable

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _short(test: unittest.TestCase) -> str:
    """'test_two_claps_arm (tests.test_wake.WakeTests)' -> 'wake: two claps arm'."""
    method = test._testMethodName.removeprefix("test_").replace("_", " ")
    module = type(test).__module__.split(".")[-1].removeprefix("test_")
    return f"{module}: {method}"


def _why(test: unittest.TestCase) -> str:
    doc = (test._testMethodDoc or "").strip().splitlines()
    return doc[0] if doc else ""


class _StreamingResult(unittest.TestResult):
    """A TestResult that reports each outcome the moment it's known."""

    def __init__(self, emit: Callable[[str, dict], None]):
        super().__init__()
        self.emit = emit
        self.records: list[dict] = []

    def _record(self, test, status: str, message: str = "",
                name: str | None = None) -> None:
        rec = {"name": name or _short(test), "why": _why(test),
               "status": status, "message": message}
        self.records.append(rec)
        self.emit("result", rec)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "fail", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skip", reason)

    def addSubTest(self, test, subtest, err):
        """
        Report failing subtests.

        unittest routes subtest outcomes here and NOT through addFailure, so a
        result class that doesn't override this loses them completely — the
        parent test simply disappears from the report rather than failing.
        Successes stay quiet; the parent's addSuccess already covers those.
        """
        super().addSubTest(test, subtest, err)
        if err is None:
            return
        params = ", ".join(f"{k}={v!r}" for k, v in subtest.params.items())
        status = "fail" if issubclass(err[0], test.failureException) else "error"
        self._record(test, status, self._exc_info_to_string(err, test),
                     name=f"{_short(test)}  [{params}]")


def build_suite() -> unittest.TestSuite:
    return unittest.defaultTestLoader.discover(
        start_dir=TESTS_DIR, pattern="test_*.py", top_level_dir=ROOT)


def run(emit: Callable[[str, dict], None] | None = None) -> dict:
    """
    Run every test. Returns a summary dict.

    emit is called with:
        ("start",  {"total": n})
        ("result", {"name", "why", "status", "message"})
        ("done",   summary)
    """
    emit = emit or (lambda _e, _p: None)

    suite = build_suite()
    emit("start", {"total": suite.countTestCases()})

    result = _StreamingResult(emit)
    started = time.monotonic()
    suite.run(result)
    elapsed = time.monotonic() - started

    counts = {"pass": 0, "fail": 0, "error": 0, "skip": 0}
    for rec in result.records:
        counts[rec["status"]] += 1

    summary = {
        "total": len(result.records),
        "passed": counts["pass"],
        "failed": counts["fail"] + counts["error"],
        "skipped": counts["skip"],
        "seconds": elapsed,
        "ok": counts["fail"] == 0 and counts["error"] == 0,
        "records": result.records,
    }
    emit("done", summary)
    return summary


def run_in_terminal() -> int:
    """`python . --tests`"""
    marks = {"pass": "ok  ", "fail": "FAIL", "error": "ERR ", "skip": "skip"}

    def emit(event, payload):
        if event == "start":
            print(f"Running {payload['total']} tests...\n")
        elif event == "result":
            print(f"  {marks[payload['status']]}  {payload['name']}")
            if payload["message"] and payload["status"] in ("fail", "error"):
                for line in payload["message"].rstrip().splitlines():
                    print(f"        {line}")

    summary = run(emit)
    print(f"\n{summary['passed']} passed, {summary['failed']} failed, "
          f"{summary['skipped']} skipped in {summary['seconds']:.2f}s")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(run_in_terminal())
