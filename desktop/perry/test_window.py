"""
test_window.py

The TESTS button on the HUD opens this: Perry's own test suite, running in a
window, in the same style as the rest of him.

The suite runs on a background thread and streams each result back through
`root.after`, so the window paints as it goes instead of freezing until
everything finishes. Nothing here needs a microphone or a network connection —
see tests/__init__.py for why that matters.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont

BG = "#04070d"
PANEL = "#080d16"
CYAN = "#22d3ee"
CYAN_DIM = "#0e7490"
GREEN = "#34d399"
RED = "#f87171"
AMBER = "#f59e0b"
TEXT = "#cfefff"
MUTED = "#5b7a86"


class TestWindow:
    def __init__(self, parent: tk.Misc):
        self.root = tk.Toplevel(parent)
        self.root.title("Perry — self test")
        self.root.configure(bg=BG)
        self.root.geometry("640x520")
        self.root.attributes("-topmost", True)

        mono = tkfont.Font(family="Consolas", size=10)
        mono_small = tkfont.Font(family="Consolas", size=9)

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(header, text="PERRY SELF-TEST", bg=BG, fg=CYAN,
                 font=("Consolas", 14, "bold")).pack(side="left")
        self.count_label = tk.Label(header, text="", bg=BG, fg=MUTED,
                                    font=mono_small)
        self.count_label.pack(side="right")

        body = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                        highlightbackground=CYAN_DIM)
        body.pack(fill="both", expand=True, padx=16, pady=4)

        self.text = tk.Text(body, bg=PANEL, fg=TEXT, font=mono, bd=0,
                            padx=12, pady=10, wrap="word",
                            insertbackground=CYAN, highlightthickness=0)
        scroll = tk.Scrollbar(body, command=self.text.yview, bg=PANEL,
                              troughcolor=PANEL, bd=0, highlightthickness=0)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_configure("pass", foreground=GREEN)
        self.text.tag_configure("fail", foreground=RED)
        self.text.tag_configure("error", foreground=RED)
        self.text.tag_configure("skip", foreground=AMBER)
        self.text.tag_configure("why", foreground=MUTED)
        self.text.tag_configure("trace", foreground=MUTED, lmargin1=40, lmargin2=40)
        self.text.tag_configure("head", foreground=CYAN)

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=16, pady=(6, 14))
        self.summary = tk.Label(footer, text="Starting...", bg=BG, fg=MUTED,
                                font=mono, anchor="w")
        self.summary.pack(side="left", fill="x", expand=True)
        self.run_button = tk.Button(
            footer, text="RUN AGAIN", command=self.run, bg=PANEL, fg=CYAN,
            activebackground=CYAN_DIM, activeforeground=BG, bd=0, padx=14,
            pady=4, font=mono_small, cursor="hand2")
        self.run_button.pack(side="right", padx=(8, 0))
        tk.Button(footer, text="CLOSE", command=self.root.destroy, bg=PANEL,
                  fg=MUTED, activebackground=CYAN_DIM, activeforeground=BG,
                  bd=0, padx=14, pady=4, font=mono_small,
                  cursor="hand2").pack(side="right")

        self.root.bind("<Escape>", lambda _e: self.root.destroy())
        self._running = False
        self.run()

    # ------------------------------------------------------------------ output
    def _write(self, text: str, tag: str = "") -> None:
        self.text.configure(state="normal")
        self.text.insert("end", text, tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def _clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    # --------------------------------------------------------------- the suite
    def run(self) -> None:
        if self._running:
            return
        self._running = True
        self.run_button.configure(state="disabled", fg=MUTED)
        self._clear()
        self.summary.configure(text="Running...", fg=MUTED)
        threading.Thread(target=self._run_suite, daemon=True).start()

    def _run_suite(self) -> None:
        try:
            from tests.runner import run
            run(self._emit)
        except Exception as e:  # importing the suite itself failed
            # Bind via a default arg: `e` is deleted when the except block
            # ends, and this lambda runs later on the GUI thread.
            self.root.after(0, lambda err=e: self._fatal(err))

    def _fatal(self, err: Exception) -> None:
        self._write(f"Could not run the suite:\n{err}\n", "fail")
        self.summary.configure(text="Suite failed to load", fg=RED)
        self._running = False
        self.run_button.configure(state="normal", fg=CYAN)

    def _emit(self, event: str, payload: dict) -> None:
        """Called from the worker thread — hop back to the GUI thread."""
        self.root.after(0, lambda: self._handle(event, payload))

    def _handle(self, event: str, payload: dict) -> None:
        if event == "start":
            self.count_label.configure(text=f"{payload['total']} tests")
            self._write("Running Perry's test suite — no microphone needed.\n\n",
                        "head")

        elif event == "result":
            marks = {"pass": "  ✓  ", "fail": "  ✗  ",
                     "error": "  ✗  ", "skip": "  –  "}
            status = payload["status"]
            self._write(marks[status], status)
            self._write(f"{payload['name']}\n")
            if payload["why"]:
                self._write(f"       {payload['why']}\n", "why")
            if status in ("fail", "error") and payload["message"]:
                for line in payload["message"].rstrip().splitlines():
                    self._write(f"{line}\n", "trace")
            elif status == "skip":
                self._write(f"       skipped: {payload['message']}\n", "why")

        elif event == "done":
            ok = payload["ok"]
            bits = [f"{payload['passed']} passed"]
            if payload["failed"]:
                bits.append(f"{payload['failed']} failed")
            if payload["skipped"]:
                bits.append(f"{payload['skipped']} skipped")
            text = f"{', '.join(bits)} in {payload['seconds']:.2f}s"
            self.summary.configure(text=text, fg=GREEN if ok else RED)
            self._write(f"\n{text}\n", "pass" if ok else "fail")
            self._running = False
            self.run_button.configure(state="normal", fg=CYAN)
