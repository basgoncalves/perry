"""
sfx_window.py — the SFX Lab panel opened from Perry's ring ("♪ SFX Lab").

Pick a video → Auto (whoosh on every cut) or type cues → Render → <name>_sfx.mp4
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog

from perry import sfx

BG, PANEL, CYAN, CYAN_DIM, TEXT, MUTED, AMBER = (
    "#04070d", "#0a1520", "#22d3ee", "#0e7490", "#cfefff", "#5b7a86", "#f59e0b")


class SfxWindow:
    def __init__(self, root: tk.Misc, on_status=None):
        self.on_status = on_status or (lambda s: None)
        self.video = ""
        w = self.win = tk.Toplevel(root)
        w.title("Perry — SFX Lab")
        w.configure(bg=BG)
        w.attributes("-topmost", True)
        btn = dict(bg=PANEL, fg=TEXT, activebackground=CYAN_DIM, activeforeground="#fff",
                   relief="flat", font=("Segoe UI", 10), padx=10, pady=5)

        tk.Label(w, text="SFX LAB", bg=BG, fg=CYAN,
                 font=("Segoe UI Semibold", 13, "bold")).pack(padx=16, pady=(14, 0), anchor="w")
        tk.Label(w, text="sound effects on your video's cuts — test tool", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(padx=16, anchor="w")

        row = tk.Frame(w, bg=BG); row.pack(fill="x", padx=16, pady=(12, 6))
        tk.Button(row, text="Choose video…", command=self.choose, **btn).pack(side="left")
        self.name = tk.Label(row, text="no video yet", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.name.pack(side="left", padx=10)

        tk.Label(w, text="Try an effect:", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(padx=16, anchor="w")
        fx = tk.Frame(w, bg=BG); fx.pack(fill="x", padx=12, pady=(2, 8))
        for i, k in enumerate(sfx.EFFECTS):
            tk.Button(fx, text=k, command=lambda k=k: self._play(k), width=8,
                      **{**btn, "padx": 4, "pady": 3, "font": ("Segoe UI", 9)}
                      ).grid(row=i // 4, column=i % 4, padx=3, pady=3)

        hdr = tk.Frame(w, bg=BG); hdr.pack(fill="x", padx=16)
        tk.Label(hdr, text="Cues  (seconds  effect  [volume])", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self.auto_btn = tk.Button(hdr, text="Auto from cuts", command=self.auto,
                                  **{**btn, "padx": 6, "pady": 2, "font": ("Segoe UI", 9)})
        self.auto_btn.pack(side="right")
        self.cues = tk.Text(w, width=44, height=10, bg=PANEL, fg=TEXT, insertbackground=CYAN,
                            relief="flat", font=("Consolas", 10))
        self.cues.pack(padx=16, pady=6)
        self.cues.insert("1.0", "# e.g.\n0.5 riser 0.5\n1.7 whoosh\n3.0 click\n3.4 typing 0.7\n")

        bar = tk.Frame(w, bg=BG); bar.pack(fill="x", padx=16, pady=(4, 14))
        self.msg = tk.Label(bar, text="", bg=BG, fg=AMBER, font=("Segoe UI", 9),
                            wraplength=230, justify="left")
        self.msg.pack(side="left")
        self.render_btn = tk.Button(bar, text="Render", command=self.render,
                                    **{**btn, "fg": "#fff", "bg": CYAN_DIM})
        self.render_btn.pack(side="right")
        if not sfx.ffmpeg():
            self._say("ffmpeg not found — effects play, but rendering needs it "
                      "(winget install ffmpeg).")

    # ---------------------------------------------------------------- actions
    def _say(self, text: str, colour: str = AMBER) -> None:
        self.win.after(0, lambda: self.msg.config(text=text, fg=colour))

    def _play(self, kind: str) -> None:
        threading.Thread(target=sfx.preview, args=(kind,), daemon=True).start()

    def choose(self) -> None:
        p = filedialog.askopenfilename(parent=self.win, title="Video for SFX",
                                       filetypes=[("Video", "*.mp4 *.mov *.mkv *.webm *.avi"),
                                                  ("All files", "*.*")])
        if p:
            self.video = p
            self.name.config(text=os.path.basename(p), fg=TEXT)
            self._say("")

    def _busy(self, on: bool) -> None:
        state = "disabled" if on else "normal"
        self.win.after(0, lambda: (self.auto_btn.config(state=state),
                                   self.render_btn.config(state=state)))

    def auto(self) -> None:
        if not self.video:
            return self._say("Choose a video first.")
        if not sfx.ffmpeg():
            return self._say("Auto needs ffmpeg (winget install ffmpeg).")
        self._say("Finding cuts…", MUTED); self._busy(True)

        def work():
            try:
                cues = sfx.auto_cues(self.video)
                def fill():
                    self.cues.delete("1.0", "end")
                    self.cues.insert("1.0", sfx.format_cues(cues) + "\n")
                self.win.after(0, fill)
                n = sum(1 for c in cues if c[1] == "whoosh")
                self._say(f"{n} cut(s) found — edit, then Render.", CYAN)
            except Exception as e:
                self._say(f"Auto failed: {e}")
            finally:
                self._busy(False)
        threading.Thread(target=work, daemon=True).start()

    def render(self) -> None:
        if not self.video:
            return self._say("Choose a video first.")
        try:
            cues = sfx.parse_cues(self.cues.get("1.0", "end"))
        except ValueError as e:
            return self._say(str(e))
        if not cues:
            return self._say("Add at least one cue.")
        self._say("Rendering…", MUTED); self._busy(True)

        def work():
            try:
                out = sfx.render(self.video, cues)
                self._say(f"Saved {os.path.basename(out)}", CYAN)
                self.on_status("SFX video ready")
                try:
                    os.startfile(out)  # play it (Windows)
                except Exception:
                    pass
            except Exception as e:
                self._say(f"Render failed: {e}")
            finally:
                self._busy(False)
        threading.Thread(target=work, daemon=True).start()
