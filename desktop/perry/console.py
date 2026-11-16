"""
console.py — Perry at a command prompt.

    C:\\> perry
    Perry. Type what you want, or 'help'.
    > check stocks
    Opening Scrooge on Research with GOOGL, NVDA, 2331.HK ...

The same assistant, reached by typing instead of clapping. Useful when you
already have a terminal open, when the mic is muted, or when you want to say
something with a ticker in it that no speech recogniser will ever get right.

Phrase matching is shared with the voice path — `normalize` and the same
substring test from voice.py — so "check stocks", "Perry, check the stocks"
and "CHECK STOCKS!" all land in the same place, exactly as they would if you
said them out loud. One vocabulary, two front ends. Teaching Perry a new
phrase should never mean teaching him twice.

Resolution picks the command with the LONGEST matching phrase, not the first
one that matches. Without that, "check my portfolio" would be caught by the
stocks command the moment anyone added "check" as a shortcut, and the bug
would look like Perry ignoring you.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, Sequence

from perry.voice import normalize

PROMPT = "> "

# Words that are never part of a ticker, so they can't survive into a symbol
# list when you type "check stocks for nvidia and google please".
FILLER = {
    "perry", "please", "the", "my", "our", "and", "for", "of", "on", "in",
    "me", "us", "a", "an", "to", "with", "some", "all", "hey", "ok", "okay",
}


@dataclass
class Command:
    name: str
    phrases: Sequence[str]
    help: str
    run: Callable[["Console", list[str]], int]
    words: set = field(default_factory=set)

    def __post_init__(self):
        self.phrases = [normalize(p) for p in self.phrases]
        self.words = {w for p in self.phrases for w in p.split()}

    def match_length(self, text: str) -> int:
        """Length of the longest phrase of ours contained in `text`, else 0."""
        norm = normalize(text)
        return max((len(p) for p in self.phrases if p and p in norm), default=0)


def resolve(text: str, commands: Sequence[Command]) -> Command | None:
    """Which command did the user mean? Longest match wins."""
    best, best_len = None, 0
    for command in commands:
        length = command.match_length(text)
        if length > best_len:
            best, best_len = command, length
    return best


def extract_symbols(text: str, command: Command) -> list[str]:
    """Tickers typed after the command, e.g. 'check stocks NVDA 2331.HK'.

    Works on the RAW text on purpose. normalize() flattens punctuation, which
    is right for matching phrases and very wrong for symbols — it would turn
    2331.HK into "2331 hk" and BRK-B into "brk b". So we only normalise each
    token far enough to decide whether to keep it.
    """
    out = []
    for token in text.replace(",", " ").split():
        cleaned = token.strip(".,;:!?").strip()
        if not cleaned:
            continue
        flat = normalize(cleaned).replace(" ", "")
        if not flat or flat in FILLER or flat in command.words:
            continue
        if len(cleaned) > 12 or not any(c.isalnum() for c in cleaned):
            continue
        out.append(cleaned.upper())
    return out


# --- what the commands actually do ----------------------------------------

def _open_scrooge(console: "Console", args: list[str], page: str | None,
                  symbols: list[str] | None = None) -> int:
    from perry.abilities import scrooge

    if not scrooge.is_available(console.config):
        console.say(f"No Scrooge at {scrooge.scrooge_dir(console.config)}.")
        return 1

    extra = []
    if page:
        extra += ["--page", page]
    if symbols:
        extra += ["--symbols", ",".join(symbols)]

    where = page or "Portfolio"
    detail = f" with {', '.join(symbols)}" if symbols else ""
    console.say(f"Opening Scrooge on {where}{detail} ...")
    console.say("(first run builds its environment — give it a minute)")
    # Detached: the dashboard is a long-running server, and blocking here
    # would make the console useless until you closed your browser.
    return scrooge.launch(console.config, extra, wait=False)


def cmd_stocks(console: "Console", args: list[str]) -> int:
    """No symbols typed means 'everything I own or watch' — the Research
    page already defaults to exactly that, so we pass nothing and let it."""
    return _open_scrooge(console, args, "Research", args or None)


def cmd_market(console: "Console", args: list[str]) -> int:
    return _open_scrooge(console, args, "Market_Map")


def cmd_portfolio(console: "Console", args: list[str]) -> int:
    return _open_scrooge(console, args, None)


def cmd_scrooge(console: "Console", args: list[str]) -> int:
    return _open_scrooge(console, args, None)


def cmd_watchlist(console: "Console", args: list[str]) -> int:
    return _open_scrooge(console, args, "Watchlist")


def cmd_income(console: "Console", args: list[str]) -> int:
    return _open_scrooge(console, args, "Income")


def cmd_system(console: "Console", args: list[str]) -> int:
    from perry import system

    report = system.ensure_running(
        console.config.get("task_manager_page", "performance"))
    console.say(system.describe(report))
    return 0


def cmd_tests(console: "Console", args: list[str]) -> int:
    from tests.runner import run_in_terminal
    return run_in_terminal()


def cmd_help(console: "Console", args: list[str]) -> int:
    console.say("")
    width = max(len(c.name) for c in console.commands)
    for command in console.commands:
        console.say(f"  {command.name.ljust(width)}   {command.help}")
    console.say("")
    console.say("  Phrasing is loose — 'check the stocks' and 'stocks' both work.")
    console.say("  Add tickers to look at something specific: check stocks NVDA 2331.HK")
    console.say("")
    return 0


def cmd_quit(console: "Console", args: list[str]) -> int:
    console.running = False
    console.say("Standing by.")
    return 0


def build_commands() -> list[Command]:
    return [
        Command("market",
                ["market map", "show the market", "how is the market",
                 "hows the market", "market today", "heatmap", "heat map",
                 "is it over"],
                "Open Scrooge's market heatmap and total-market timeline",
                cmd_market),
        Command("stocks",
                ["check stocks", "check the stocks", "check my stocks",
                 "stocks", "shares", "how are my stocks", "research"],
                "Open Scrooge's Research page for what you own and watch",
                cmd_stocks),
        Command("portfolio",
                ["portfolio", "check my portfolio", "how am i doing",
                 "how is my portfolio", "holdings"],
                "Open Scrooge's portfolio overview",
                cmd_portfolio),
        Command("watchlist",
                ["watchlist", "watch list", "alerts", "targets"],
                "Open Scrooge's watchlist and alerts",
                cmd_watchlist),
        Command("income",
                ["income", "dividends", "passive income"],
                "Open Scrooge's dividend and income projection",
                cmd_income),
        Command("scrooge",
                ["scrooge", "open scrooge", "money", "dashboard"],
                "Open Scrooge at the front page",
                cmd_scrooge),
        Command("system",
                ["system", "task manager", "taskmgr", "performance",
                 "how is the machine", "resources"],
                "Bring up Task Manager on the Performance page",
                cmd_system),
        Command("tests",
                ["tests", "run tests", "test suite", "run the tests"],
                "Run Perry's test suite here in the terminal",
                cmd_tests),
        Command("help",
                ["help", "commands", "what can you do", "options"],
                "This list",
                cmd_help),
        Command("quit",
                ["quit", "exit", "bye", "goodbye", "close"],
                "Leave the console (Perry keeps running in the background)",
                cmd_quit),
    ]


# --- the console itself ----------------------------------------------------

class Console:
    def __init__(self, config: dict | None = None, commands=None,
                 out: Callable[[str], None] = print):
        if config is None:
            from perry import config as config_module
            config = config_module.load()
        self.config = config
        self.commands = commands if commands is not None else build_commands()
        self.out = out
        self.running = True
        self.name = config.get("assistant_name", "Perry")

    def say(self, text: str = "") -> None:
        self.out(text)

    def handle(self, text: str) -> int:
        """Run one line. Returns the command's exit code, or 0 for a no-op."""
        text = (text or "").strip()
        if not text:
            return 0

        command = resolve(text, self.commands)
        if command is None:
            self.say(f"I don't know '{text}'. Type 'help' for what I do know.")
            suggestion = self.closest(text)
            if suggestion:
                self.say(f"Did you mean '{suggestion}'?")
            return 1

        return command.run(self, extract_symbols(text, command))

    def closest(self, text: str) -> str | None:
        import difflib

        names = [c.name for c in self.commands]
        matches = difflib.get_close_matches(normalize(text), names, n=1, cutoff=0.5)
        return matches[0] if matches else None

    def greet(self) -> None:
        self.say(f"{self.name}. Type what you want, or 'help'.")

    def loop(self) -> int:
        self.greet()
        while self.running:
            try:
                line = input(PROMPT)
            except (EOFError, KeyboardInterrupt):
                self.say("")
                return 0
            try:
                self.handle(line)
            except Exception as exc:  # a bad command must not kill the console
                self.say(f"That went wrong: {exc}")
        return 0


def main(args: Sequence[str] = ()) -> int:
    from perry import config as config_module
    from perry import system

    cfg = config_module.load()
    console = Console(cfg)

    if cfg.get("task_manager_on_start", True):
        report = system.ensure_running(cfg.get("task_manager_page", "performance"))
        # Only speak up when something happened or something went wrong.
        # "already open" and "not Windows" are both non-events, and a line of
        # noise on every single launch is how people learn to ignore output.
        interesting = report.get("launched") or (
            report.get("reason") and report["reason"] != "not Windows")
        if interesting:
            console.say(system.describe(report))

    args = [a for a in args if not a.startswith("--")]
    if args:
        # One-shot: `perry check stocks` does the thing and exits.
        return console.handle(" ".join(args))

    return console.loop()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
