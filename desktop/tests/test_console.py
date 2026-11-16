"""
The typed console — does Perry understand what you asked for?

Every test here drives the real resolution logic with a fake command that
records instead of launching anything, so the suite never opens a browser,
a dashboard or Task Manager.
"""

from __future__ import annotations

import unittest

from perry import console as console_module
from perry.console import Command, Console, extract_symbols, resolve


def recorder():
    """A command action that just remembers it was called."""
    calls = []

    def run(console, args):
        calls.append(args)
        return 0

    return calls, run


def fake_commands():
    stock_calls, stock_run = recorder()
    port_calls, port_run = recorder()
    sys_calls, sys_run = recorder()
    commands = [
        Command("stocks", ["check stocks", "stocks", "research"], "", stock_run),
        Command("portfolio", ["portfolio", "check my portfolio"], "", port_run),
        Command("system", ["system", "task manager"], "", sys_run),
    ]
    return commands, {"stocks": stock_calls, "portfolio": port_calls,
                      "system": sys_calls}


class ResolutionTests(unittest.TestCase):

    def setUp(self):
        self.commands, self.calls = fake_commands()

    def resolved(self, text):
        command = resolve(text, self.commands)
        return command.name if command else None

    def test_the_exact_phrase_works(self):
        """'check stocks' is the phrase the whole feature is named after"""
        self.assertEqual(self.resolved("check stocks"), "stocks")

    def test_case_and_punctuation_are_ignored(self):
        """Typing is as sloppy as speech, and should be treated the same"""
        for text in ("CHECK STOCKS", "Check Stocks!", "check   stocks",
                     "check-stocks"):
            self.assertEqual(self.resolved(text), "stocks", text)

    def test_addressing_him_by_name_still_works(self):
        """'Perry, check stocks' is how a person actually types it"""
        self.assertEqual(self.resolved("perry, check stocks"), "stocks")
        self.assertEqual(self.resolved("hey perry check the stocks please"), "stocks")

    def test_a_shorter_phrase_still_finds_it(self):
        """One word should be enough once you know the command"""
        self.assertEqual(self.resolved("stocks"), "stocks")

    def test_the_longest_match_wins(self):
        """'check my portfolio' must not be captured by a shorter phrase.

        This is the whole reason resolution scores by length instead of
        taking the first hit — with first-match ordering this returns the
        wrong command and looks like Perry ignoring you.
        """
        self.assertEqual(self.resolved("check my portfolio"), "portfolio")
        self.assertEqual(self.resolved("portfolio"), "portfolio")

    def test_nonsense_resolves_to_nothing(self):
        """Better to admit ignorance than to guess and act"""
        self.assertIsNone(resolve("make me a sandwich", self.commands))

    def test_an_empty_line_resolves_to_nothing(self):
        """Pressing enter shouldn't launch anything"""
        self.assertIsNone(resolve("", self.commands))
        self.assertIsNone(resolve("   ", self.commands))


class SymbolTests(unittest.TestCase):
    """Tickers survive the trip; ordinary words don't."""

    def setUp(self):
        self.command = Command("stocks", ["check stocks", "stocks"], "",
                               lambda c, a: 0)

    def extract(self, text):
        return extract_symbols(text, self.command)

    def test_no_symbols_means_no_symbols(self):
        """Bare 'check stocks' falls back to what you own and watch"""
        self.assertEqual(self.extract("check stocks"), [])

    def test_plain_tickers_come_through_uppercased(self):
        """nvda googl -> NVDA GOOGL"""
        self.assertEqual(self.extract("check stocks nvda googl"),
                         ["NVDA", "GOOGL"])

    def test_a_dotted_exchange_suffix_survives(self):
        """2331.HK must not be flattened into '2331 hk'.

        normalize() strips punctuation, which is right for matching phrases
        and fatal for tickers — so symbols are read off the raw text.
        """
        self.assertEqual(self.extract("check stocks 2331.HK"), ["2331.HK"])
        self.assertEqual(self.extract("stocks BRK-B"), ["BRK-B"])
        self.assertEqual(self.extract("stocks VWCE.DE nvda"), ["VWCE.DE", "NVDA"])

    def test_commas_and_filler_are_dropped(self):
        """'nvda, googl and 2331.HK please' is a list of three"""
        self.assertEqual(
            self.extract("check stocks nvda, googl and 2331.HK please"),
            ["NVDA", "GOOGL", "2331.HK"])

    def test_the_command_words_are_not_mistaken_for_tickers(self):
        """'stocks' is not a company"""
        self.assertNotIn("STOCKS", self.extract("check stocks nvda"))
        self.assertNotIn("CHECK", self.extract("check stocks nvda"))
        self.assertNotIn("PERRY", self.extract("perry check stocks nvda"))


class DispatchTests(unittest.TestCase):
    """handle() routes a line to the right action with the right arguments."""

    def setUp(self):
        self.commands, self.calls = fake_commands()
        self.output = []
        self.console = Console(config={}, commands=self.commands,
                               out=self.output.append)

    def test_a_line_reaches_its_command(self):
        """The stocks command runs, and nothing else does"""
        self.console.handle("check stocks")
        self.assertEqual(len(self.calls["stocks"]), 1)
        self.assertEqual(self.calls["portfolio"], [])

    def test_symbols_are_handed_to_the_command(self):
        """What you typed after the phrase arrives as a list"""
        self.console.handle("check stocks nvda 2331.HK")
        self.assertEqual(self.calls["stocks"][0], ["NVDA", "2331.HK"])

    def test_an_unknown_line_says_so_and_runs_nothing(self):
        """Perry admits it instead of picking the nearest command"""
        code = self.console.handle("frobnicate the widgets")
        self.assertEqual(code, 1)
        self.assertEqual(self.calls["stocks"], [])
        self.assertTrue(any("don't know" in line for line in self.output))

    def test_a_near_miss_gets_a_suggestion(self):
        """A typo should point at the command you meant"""
        self.console.handle("stcks")
        self.assertTrue(any("Did you mean" in line for line in self.output),
                        self.output)

    def test_a_blank_line_does_nothing_quietly(self):
        """Pressing enter is not an error"""
        self.assertEqual(self.console.handle(""), 0)
        self.assertEqual(self.output, [])

    def test_quit_stops_the_loop(self):
        """'quit' leaves the console without killing the assistant"""
        real = Console(config={}, out=self.output.append)
        self.assertTrue(real.running)
        real.handle("quit")
        self.assertFalse(real.running)


class StartupNoiseTests(unittest.TestCase):
    """Starting the console shouldn't print anything you'd learn to ignore."""

    def setUp(self):
        from perry import system

        self.system = system
        self._real = system.ensure_running
        self.addCleanup(lambda: setattr(system, "ensure_running", self._real))

    def run_main(self, report):
        self.system.ensure_running = lambda page="performance": report
        from perry import config as config_module
        real_load = config_module.load
        config_module.load = lambda *a, **k: {**real_load(*a, **k), "task_manager_on_start": True}
        self.addCleanup(lambda: setattr(config_module, "load", real_load))
        out = []
        real_console = console_module.Console
        console_module.Console = lambda *a, **k: real_console(
            *a, **{**k, "out": out.append})
        self.addCleanup(lambda: setattr(console_module, "Console", real_console))
        # "quit" rather than "help": the help text mentions Task Manager
        # itself, which would match the very thing we're asserting is absent.
        console_module.main(["quit"])
        return out

    def test_an_already_open_task_manager_is_silent(self):
        """The common case says nothing"""
        out = self.run_main({"was_running": True, "launched": False,
                             "page_set": True, "reason": ""})
        self.assertFalse(any("Task Manager" in line for line in out), out)

    def test_launching_it_is_announced(self):
        """Opening a window unprompted should be explained"""
        out = self.run_main({"was_running": False, "launched": True,
                             "page_set": True, "reason": ""})
        self.assertTrue(any("Task Manager" in line for line in out), out)

    def test_running_off_windows_is_silent(self):
        """Not-Windows is a non-event, not a warning"""
        out = self.run_main({"was_running": False, "launched": False,
                             "page_set": False, "reason": "not Windows"})
        self.assertFalse(any("Task Manager" in line for line in out), out)

    def test_a_real_failure_is_announced(self):
        """Blocked by policy is worth saying once"""
        out = self.run_main({"was_running": False, "launched": False,
                             "page_set": False, "reason": "blocked by policy"})
        self.assertTrue(any("blocked by policy" in line for line in out), out)


class RealCommandTests(unittest.TestCase):
    """The shipped command table, not a fake one."""

    def setUp(self):
        self.commands = console_module.build_commands()

    def resolved(self, text):
        command = resolve(text, self.commands)
        return command.name if command else None

    def test_the_phrases_a_person_would_actually_type(self):
        """Each of these has to land somewhere sensible"""
        expected = {
            "check stocks": "stocks",
            "perry check the stocks": "stocks",
            "stocks": "stocks",
            "how am i doing": "portfolio",
            "check my portfolio": "portfolio",
            "watchlist": "watchlist",
            "dividends": "income",
            "task manager": "system",
            "system": "system",
            "open scrooge": "scrooge",
            "help": "help",
            "exit": "quit",
        }
        for text, name in expected.items():
            with self.subTest(text=text):
                self.assertEqual(self.resolved(text), name)

    def test_every_command_has_help_and_phrases(self):
        """An undocumented command is an invisible one"""
        for command in self.commands:
            self.assertTrue(command.phrases, command.name)
            self.assertTrue(command.help.strip(), command.name)

    def test_no_two_commands_share_a_phrase(self):
        """A duplicated phrase makes resolution a coin toss"""
        seen = {}
        for command in self.commands:
            for phrase in command.phrases:
                self.assertNotIn(
                    phrase, seen,
                    f"'{phrase}' is on both {seen.get(phrase)} and {command.name}")
                seen[phrase] = command.name

    def test_help_lists_everything(self):
        """The help output names every command"""
        output = []
        console = Console(config={}, out=output.append)
        console.handle("help")
        text = "\n".join(output)
        for command in console.commands:
            self.assertIn(command.name, text)


class ScroogeHandoffTests(unittest.TestCase):
    """What actually gets handed to Scrooge when you ask for stocks.

    Stubs the launcher, so this checks the arguments without starting a
    dashboard. These strings are the contract between the two programs; if
    Scrooge renames --page, this is what should go red.
    """

    def setUp(self):
        from perry.abilities import scrooge

        self.scrooge = scrooge
        self.calls = []
        self._real = (scrooge.launch, scrooge.is_available)
        scrooge.is_available = lambda cfg=None: True
        scrooge.launch = lambda cfg=None, args=(), wait=True: (
            self.calls.append({"args": list(args), "wait": wait}) or 0)
        self.addCleanup(self.restore)

        self.output = []
        self.console = Console(config={}, out=self.output.append)

    def restore(self):
        self.scrooge.launch, self.scrooge.is_available = self._real

    def test_check_stocks_opens_the_research_page(self):
        """The headline behaviour: 'check stocks' lands on Research"""
        self.console.handle("check stocks")
        self.assertEqual(self.calls[0]["args"], ["--page", "Research"])

    def test_typed_tickers_are_passed_along(self):
        """'check stocks nvda 2331.HK' pre-loads those two"""
        self.console.handle("check stocks nvda 2331.HK")
        self.assertEqual(self.calls[0]["args"],
                         ["--page", "Research", "--symbols", "NVDA,2331.HK"])

    def test_the_portfolio_command_opens_the_front_page(self):
        """No --page means Scrooge's own first page"""
        self.console.handle("how am i doing")
        self.assertEqual(self.calls[0]["args"], [])

    def test_other_pages_are_reachable(self):
        """Each page command names its page exactly as the file does"""
        for text, page in (("watchlist", "Watchlist"), ("dividends", "Income")):
            self.calls.clear()
            self.console.handle(text)
            self.assertEqual(self.calls[0]["args"], ["--page", page], text)

    def test_scrooge_is_launched_detached(self):
        """Blocking here would freeze the console until you shut the browser"""
        self.console.handle("check stocks")
        self.assertFalse(self.calls[0]["wait"])

    def test_a_missing_scrooge_is_reported_not_launched(self):
        """Deleting the folder gives a sentence, not a traceback"""
        self.scrooge.is_available = lambda cfg=None: False
        code = self.console.handle("check stocks")
        self.assertEqual(code, 1)
        self.assertEqual(self.calls, [])
        self.assertTrue(any("No Scrooge" in line for line in self.output))


if __name__ == "__main__":
    unittest.main()
