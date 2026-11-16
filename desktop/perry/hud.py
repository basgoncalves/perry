"""
hud.py

Jarvis-style HUD window for Perry. Dark, frameless, glowing animated orb.

The orb's colour is the state indicator:
    cyan dim   idle      — hidden in the background, listening for claps
    amber      armed     — heard your claps, waiting for the phrase
    cyan       awake     — woken; restoring your session

Runs on the main thread (tkinter's requirement); every other component pushes
updates in through thread-safe .after() calls.
"""

from __future__ import annotations

import math
import os
import sys
import tkinter as tk
from typing import Callable


BG = "#04070d"
CYAN = "#22d3ee"
CYAN_DIM = "#0e7490"
AMBER = "#f59e0b"
AMBER_DIM = "#92400e"
TEXT = "#cfefff"
MUTED = "#5b7a86"

MODES = {
    "idle":  (CYAN, CYAN_DIM),
    "armed": (AMBER, AMBER_DIM),
    "awake": (CYAN, CYAN_DIM),
}


class PerryHUD:
    # Built-in options in the ring shown when you click Perry: (action, glyph, label)
    BUILTIN = [
        ("home",     "⌂", "Restore session"),
        ("vscode",   "</>",    "VS Code"),
        ("script",   "\u25b6", "Run script"),
        ("hands",    "\u261d", "Hand mouse"),
        ("office",   "▦", "Virtual office"),
        ("web",      "◎", "Perry Online"),
        ("sfx",      "♪", "SFX Lab"),
        ("commands", "?",      "Commands"),
        ("taskmgr",  "≡", "Task Manager"),
        ("tests",    "✓", "Run tests"),
        ("hide",     "–", "Hide Perry"),
        ("power",    "⏻", "Turn off Perry"),
    ]
    KEY = "#000001"        # painted pixels in this colour are see-through
    PLATE = "#05090f"      # dark backing behind text and icons: readable on any wallpaper
    RING_R = 142

    def __init__(self, assistant_name: str = "Perry",
                 on_close: Callable[[], None] | None = None,
                 on_tests: Callable[[], None] | None = None,
                 on_office: Callable[[], None] | None = None,
                 on_action: Callable[[str], None] | None = None,
                 start_hidden: bool = True):
        self.on_close = on_close
        self.on_tests = on_tests
        self.on_office = on_office
        self.on_action = on_action
        if sys.platform == "win32":  # own taskbar group, not "Python"
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Basilio.Perry")
            except Exception:
                pass
        self.root = tk.Tk()
        self.root.withdraw()          # stay invisible until fully dressed
        try:
            self.root.attributes("-alpha", 0.0)   # and fully see-through when first mapped
        except tk.TclError:
            pass
        self.root.title(assistant_name)
        ico = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "perry.ico")
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(default=ico)
            except tk.TclError:
                pass
        key = self.KEY
        self.root.configure(bg=key)
        self.root.overrideredirect(True)          # frameless, no shadow
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", key)   # Windows
        except tk.TclError:
            key = BG                                          # elsewhere: dark box
            self.root.configure(bg=key)

        w, h = 640, 520
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{sw - w + 60}+{sh - h - 40}")

        self.canvas = tk.Canvas(self.root, width=w, height=h, bg=key,
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._w, self._h = w, h

        self._press = (0, 0)
        self._moved = False
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)

        self._cx, self._cy = w // 2, 220
        self._phase = 0.0
        self._pulsing = False
        self._accent, self._accent_dim = MODES["idle"]
        self._menu_t, self._menu_target, self._hover = 0.0, 0.0, -1
        self.custom = self._load_custom()

        cx = self._cx
        self._plates = {}
        self.canvas.create_text(cx, 336, text=assistant_name.upper(),
                                fill=CYAN, font=("Consolas", 24, "bold"), tags=("brand", "info"))
        self.status_id = self.canvas.create_text(
            cx, 370, text="Starting...", fill="#ffffff",
            font=("Segoe UI Semibold", 11), tags=("status", "info"))
        self.heard_id = self.canvas.create_text(
            cx, 396, text="click me for options", fill="#b9d7e3",
            font=("Segoe UI", 9), tags=("heard", "info"))
        self.canvas.create_text(cx, 426, text="COMMANDS", fill="#b9d7e3",
                                font=("Segoe UI Semibold", 9), tags=("cmds", "info"))
        for tag in ("brand", "status", "heard", "cmds"):
            self._plate(tag)
        self._bind_hover("cmds", CYAN, "#b9d7e3")

        # Power button just outside the ring (also in the option ring).
        self.canvas.create_oval(cx + 72, self._cy - 96, cx + 98, self._cy - 70,
                                fill=self.PLATE, outline=MUTED, width=1, tags=("quitbg", "quit"))
        self.canvas.create_text(cx + 85, self._cy - 83, text="⏻", fill="#b9d7e3",
                                font=("Segoe UI Symbol", 12), tags=("quiticon", "quit"))
        self.canvas.tag_bind("quit", "<Enter>", lambda _e: self.canvas.itemconfig("quiticon", fill=AMBER))
        self.canvas.tag_bind("quit", "<Leave>", lambda _e: self.canvas.itemconfig("quiticon", fill="#b9d7e3"))
        self.root.bind("<Escape>", lambda _e: self.hide())

        self.visible = not start_hidden
        self._animate()
        self.root.update_idletasks()   # window exists (hidden) -> style it now
        self._taskbar()
        if not start_hidden:
            self._reveal()

    # Map the window fully transparent, let it paint, then fade it in: no ghost frame.
    def _reveal(self) -> None:
        try:
            self.root.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.root.deiconify()
        self.root.update_idletasks()
        self.root.update()
        def fade(a=0.25):
            try:
                self.root.attributes("-alpha", min(1.0, a))
            except tk.TclError:
                return
            if a < 1.0:
                self.root.after(16, fade, a + 0.25)
        self.root.after(30, fade)

    def _plate(self, tag: str) -> None:
        """Dark rounded backing behind a text item, kept in step with its text."""
        bb = self.canvas.bbox(tag)
        if not bb:
            return
        pid = self._plates.get(tag)
        x0, y0, x1, y1 = bb[0] - 8, bb[1] - 2, bb[2] + 8, bb[3] + 2
        if pid is None:
            pid = self.canvas.create_rectangle(x0, y0, x1, y1, fill=self.PLATE,
                                               outline="", tags=("info", "plate"))
            self.canvas.tag_lower(pid, tag)
            self._plates[tag] = pid
        else:
            self.canvas.coords(pid, x0, y0, x1, y1)

    def _bind_hover(self, tag: str, colour: str, normal: str = MUTED) -> None:
        self.canvas.tag_bind(tag, "<Enter>",
                             lambda _e: self.canvas.itemconfig(tag, fill=colour))
        self.canvas.tag_bind(tag, "<Leave>",
                             lambda _e: self.canvas.itemconfig(tag, fill=normal))

    def _quit(self) -> None:
        if self.on_close:
            self.on_close()
        else:
            self.root.destroy()

    # ------------------------------------------------------- custom balloons
    @staticmethod
    def _load_custom() -> list[dict]:
        try:
            from perry import config as cm
            return list(cm.load().get("custom_actions", []))
        except Exception:
            return []

    def _save_custom(self) -> None:
        try:
            from perry import config as cm
            cfg = cm.load()
            cfg["custom_actions"] = self.custom
            cm.save(cfg)
        except Exception as e:
            self.set_heard(f"couldn't save: {e}")

    def items(self) -> list[tuple[str, str, str]]:
        out = list(self.BUILTIN)
        for i, c in enumerate(self.custom):
            name = c.get("name") or "?"
            out.append((f"custom:{i}", name[:2].upper(), name))
        out.append(("add", "+", "Add balloon"))
        return out

    def run_custom(self, i: int) -> None:
        c = self.custom[i]
        target, args = c.get("target", ""), c.get("args", "")
        try:
            if args:
                import subprocess
                subprocess.Popen(f'"{target}" {args}', shell=True,
                                 cwd=os.path.dirname(target) or None)
            else:
                os.startfile(target)          # apps, .bat, files, folders, URLs
            self.set_status(f"Running {c.get('name')}")
        except Exception as e:
            self.set_status("That didn't run")
            self.set_heard(str(e))

    def _add_dialog(self, edit: int | None = None) -> None:
        from tkinter import filedialog
        old = self.custom[edit] if edit is not None else {}
        win = tk.Toplevel(self.root)
        win.title("Perry - new balloon" if edit is None else "Perry - edit balloon")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        lab = dict(bg=BG, fg="#cfefff", font=("Segoe UI", 10))
        ent = dict(bg="#0a1520", fg="#ffffff", insertbackground=CYAN, relief="flat",
                   font=("Segoe UI", 10), width=46)
        tk.Label(win, text="NEW BALLOON" if edit is None else "EDIT BALLOON", bg=BG, fg=CYAN,
                 font=("Consolas", 13, "bold")).grid(row=0, column=0, columnspan=3,
                                                    sticky="w", padx=16, pady=(14, 8))
        v_name, v_target, v_args = (tk.StringVar(value=old.get(k, "")) for k in ("name", "target", "args"))
        rows = [("Name", v_name, "shown on the balloon; say \"Perry, run <name>\""),
                ("Runs", v_target, "an app (.exe), script (.bat/.cmd/.ps1), file, folder or URL"),
                ("Arguments", v_args, "optional")]
        for r, (label, var, hint) in enumerate(rows, start=1):
            tk.Label(win, text=label, **lab).grid(row=2 * r - 1, column=0, sticky="w", padx=16)
            tk.Entry(win, textvariable=var, **ent).grid(row=2 * r - 1, column=1, sticky="we", pady=4)
            tk.Label(win, text=hint, bg=BG, fg=MUTED, font=("Segoe UI", 8)).grid(
                row=2 * r, column=1, sticky="w")

        def browse():
            path = filedialog.askopenfilename(parent=win, title="Pick what the balloon runs")
            if path:
                v_target.set(path.replace("/", "\\"))
                if not v_name.get():
                    v_name.set(os.path.splitext(os.path.basename(path))[0])

        btn = dict(bg="#0a1520", fg=CYAN, activebackground=CYAN_DIM, relief="flat",
                   font=("Segoe UI", 10), padx=12)
        tk.Button(win, text="Browse...", command=browse, **btn).grid(row=3, column=2, padx=(8, 16))

        def save():
            name, target = v_name.get().strip(), v_target.get().strip()
            if not name or not target:
                return
            item = {"name": name, "target": target, "args": v_args.get().strip()}
            if edit is None:
                self.custom.append(item)
            else:
                self.custom[edit] = item
            self._save_custom()
            win.destroy()
            self.set_status(f"Added {name}" if edit is None else f"Updated {name}")

        bar = tk.Frame(win, bg=BG)
        bar.grid(row=8, column=0, columnspan=3, sticky="e", padx=16, pady=14)
        if edit is not None:
            def remove():
                self.custom.pop(edit)
                self._save_custom()
                win.destroy()
            tk.Button(bar, text="Remove", command=remove, **{**btn, "fg": AMBER}).pack(side="left", padx=6)
        tk.Button(bar, text="Cancel", command=win.destroy, **btn).pack(side="left", padx=6)
        tk.Button(bar, text="Save", command=save, **{**btn, "fg": "#ffffff", "bg": CYAN_DIM}).pack(side="left")
        win.update_idletasks()
        win.geometry(f"+{max(10, self.root.winfo_x() - win.winfo_width() + 120)}+{max(10, self.root.winfo_y() + 60)}")

    # ------------------------------------------------------------ run a script
    def prompt_script(self) -> None:
        self.root.after(0, self._prompt_script)

    def _prompt_script(self) -> None:
        old = getattr(self, "_script_win", None)
        if old is not None and old.winfo_exists():
            old.lift(); old.focus_force(); return
        if not self.visible:
            self._show()
        win = tk.Toplevel(self.root)
        self._script_win = win
        win.title("Perry - run script")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        tk.Label(win, text="WHICH SCRIPT?", bg=BG, fg=CYAN,
                 font=("Consolas", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(win, text="Paste the full path (.py, .bat, .cmd, .ps1, .exe...) and press Enter.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        var = tk.StringVar(value=getattr(self, "_last_script", ""))
        e = tk.Entry(win, textvariable=var, bg="#0a1520", fg="#ffffff", insertbackground=CYAN,
                     relief="flat", font=("Consolas", 11), width=60)
        e.pack(fill="x", padx=16, pady=10, ipady=4)
        msg = tk.Label(win, text="", bg=BG, fg=AMBER, font=("Segoe UI", 9))
        msg.pack(anchor="w", padx=16)

        def go(_e=None):
            path = var.get().strip().strip('"').strip("'")
            if not path:
                return
            if not os.path.exists(path):
                msg.config(text="That path doesn't exist."); return
            self._last_script = path
            win.destroy()
            self.run_script(path)

        bar = tk.Frame(win, bg=BG); bar.pack(anchor="e", padx=16, pady=12)
        btn = dict(bg="#0a1520", fg=CYAN, activebackground=CYAN_DIM, relief="flat",
                   font=("Segoe UI", 10), padx=12)
        tk.Button(bar, text="Cancel", command=win.destroy, **btn).pack(side="left", padx=6)
        tk.Button(bar, text="Run", command=go, **{**btn, "fg": "#ffffff", "bg": CYAN_DIM}).pack(side="left")
        e.bind("<Return>", go)
        win.bind("<Escape>", lambda _e: win.destroy())
        win.update_idletasks()
        win.geometry(f"+{max(10, self.root.winfo_x() - win.winfo_width() + 160)}+{max(10, self.root.winfo_y() + 80)}")
        win.focus_force(); e.focus_set(); e.select_range(0, "end")

    def run_script(self, path: str) -> None:
        """Run it in its own console window so you can watch the output."""
        import subprocess
        folder = os.path.dirname(path) or None
        ext = os.path.splitext(path)[1].lower()
        new_console = 0x00000010  # CREATE_NEW_CONSOLE
        try:
            if ext in (".py", ".pyw"):
                subprocess.Popen(["cmd", "/k", "python", path], cwd=folder, creationflags=new_console)
            elif ext in (".bat", ".cmd"):
                subprocess.Popen(["cmd", "/k", path], cwd=folder, creationflags=new_console)
            elif ext == ".ps1":
                subprocess.Popen(["powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", path],
                                 cwd=folder, creationflags=new_console)
            else:
                os.startfile(path)
            self.set_status(f"Running {os.path.basename(path)}")
        except Exception as e:
            self.set_status("That didn't run")
            self.set_heard(str(e))

    # ------------------------------------------------------------- SFX Lab
    def open_sfx(self) -> None:
        try:
            from perry.sfx_window import SfxWindow
            SfxWindow(self.root, on_status=self.set_status)
        except Exception as e:
            self.set_status("SFX Lab didn't open")
            self.set_heard(str(e))

    # ------------------------------------------------------ Perry Online (web)
    def _web_picker(self) -> None:
        """Small panel listing the Perry Online sections; each opens an app window."""
        from perry import web
        win = tk.Toplevel(self.root)
        win.title("Perry Online")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        tk.Label(win, text="PERRY ONLINE", bg=BG, fg=CYAN,
                 font=("Segoe UI Semibold", 12, "bold")).pack(padx=18, pady=(14, 2))
        tk.Label(win, text="finance + biz tools from the web app", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(pady=(0, 10))
        grid = tk.Frame(win, bg=BG)
        grid.pack(padx=14, pady=(0, 14))
        for i, (key, label, glyph) in enumerate(web.SECTIONS):
            def go(k=key):
                self.set_status(web.open_section(k)[:39])
                win.destroy()
            tk.Button(grid, text=f"{glyph}  {label}", command=go, width=14, anchor="w",
                      bg="#0a1520", fg=TEXT, activebackground=CYAN_DIM, activeforeground="#ffffff",
                      relief="flat", font=("Segoe UI", 10), padx=8, pady=6
                      ).grid(row=i // 2, column=i % 2, padx=4, pady=4)
        win.update_idletasks()
        x = self.root.winfo_x() - win.winfo_width() - 10
        y = self.root.winfo_y() + 40
        win.geometry(f"+{max(0, x)}+{max(0, y)}")

    # ------------------------------------------------------------- menu & mouse
    def _menu_pos(self, i: int, t: float, n: int | None = None) -> tuple[float, float]:
        n = n or len(self.items())
        ang = math.radians(90 - i * 360 / n)            # full circle, clockwise from top
        r = self.RING_R * (1 - (1 - t) ** 3)
        return self._cx + r * math.cos(ang), self._cy - r * math.sin(ang)

    def _bubble_at(self, x: float, y: float) -> int:
        if self._menu_t < 0.9:
            return -1
        n = len(self.items())
        for i in range(n):
            bx, by = self._menu_pos(i, 1.0, n)
            if (x - bx) ** 2 + (y - by) ** 2 <= 25 ** 2:
                return i
        return -1

    def _on_press(self, e):
        self._press = (e.x, e.y)
        self._moved = False

    def _on_drag(self, e):
        dx, dy = e.x - self._press[0], e.y - self._press[1]
        if not self._moved and dx * dx + dy * dy < 25:
            return
        self._moved = True
        self.root.geometry(f"+{self.root.winfo_x() + dx}+{self.root.winfo_y() + dy}")

    def _on_release(self, e):
        if self._moved:
            return
        i = self._bubble_at(e.x, e.y)
        if i >= 0:
            self._menu_target = 0.0
            return self._fire(self.items()[i][0])
        item = self.canvas.find_withtag("current")
        tags = self.canvas.gettags(item[0]) if item else ()
        if "quit" in tags and self._menu_t == 0:
            return self._quit()
        if "cmds" in tags and self._menu_t == 0:
            return self._fire("commands")
        if (e.x - self._cx) ** 2 + (e.y - self._cy) ** 2 <= 90 ** 2:
            self._menu_target = 0.0 if self._menu_target else 1.0
        else:
            self._menu_target = 0.0

    def _on_right_click(self, e):
        i = self._bubble_at(e.x, e.y)
        if i >= 0 and self.items()[i][0].startswith("custom:"):
            self._add_dialog(edit=int(self.items()[i][0].split(":")[1]))

    def _on_motion(self, e):
        self._hover = self._bubble_at(e.x, e.y)

    def _fire(self, action: str) -> None:
        if action == "hide":
            return self.hide()
        if action == "power":
            return self._quit()
        if action == "add":
            return self._add_dialog()
        if action == "script":
            return self._prompt_script()
        if action == "web":
            return self._web_picker()
        if action == "sfx":
            return self.open_sfx()
        if action.startswith("custom:"):
            return self.run_custom(int(action.split(":")[1]))
        if action == "tests" and self.on_tests:
            return self.on_tests()
        if action == "office" and self.on_office and not self.on_action:
            return self.on_office()
        if self.on_action:
            self.on_action(action)

    def _draw_menu(self) -> None:
        c = self.canvas
        c.delete("menu")
        step = 0.18 if self._menu_target > self._menu_t else -0.22
        if self._menu_t != self._menu_target:
            self._menu_t = min(1.0, max(0.0, self._menu_t + step))
        t = self._menu_t
        state = "hidden" if t > 0 else "normal"
        c.itemconfigure("quit", state=state)
        c.itemconfigure("info", state=state)
        if t <= 0:
            return
        items = self.items()
        n = len(items)
        for i, (key, glyph, label) in enumerate(items):
            x, y = self._menu_pos(i, t, n)
            r = 23 * (0.4 + 0.6 * t)
            hot = i == self._hover
            ring = AMBER if key == "power" else (CYAN if key == "add" else self._accent)
            # dark halo, then the bubble: crisp edge on any background
            c.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, fill=self.PLATE,
                          outline="", tags="menu")
            c.create_oval(x - r, y - r, x + r, y + r,
                          fill=ring if hot else "#0d1b28", outline=ring,
                          width=2.5, tags="menu")
            c.create_text(x, y, text=glyph, fill=self.PLATE if hot else "#ffffff",
                          font=("Segoe UI Semibold", int(8 + 6 * t), "bold"), tags="menu")
            if t >= 1:
                # label outside the ring, on its own dark plate (like Logi Options)
                ang = math.atan2(self._cy - y, x - self._cx)
                lx = x + math.cos(ang) * (r + 10)
                ly = y - math.sin(ang) * (r + 10)
                cos_a = math.cos(ang)
                anchor = "w" if cos_a > 0.3 else "e" if cos_a < -0.3 else ("s" if ly < self._cy else "n")
                tid = c.create_text(lx, ly, text=label, anchor=anchor,
                                    fill=ring if hot else "#ffffff",
                                    font=("Segoe UI Semibold", 10), tags="menu")
                bx0, by0, bx1, by1 = c.bbox(tid)
                pid = c.create_rectangle(bx0 - 7, by0 - 3, bx1 + 7, by1 + 3, fill=self.PLATE,
                                         outline=ring if hot else "#1f3442", tags="menu")
                c.tag_lower(pid, tid)

    # ----------------------------------------------------------- commands popup
    def show_commands(self, lines: list[tuple[str, str]]) -> None:
        self.root.after(0, lambda: self._show_commands(lines))

    def _show_commands(self, lines) -> None:
        old = getattr(self, "_cmd_win", None)
        if old is not None and old.winfo_exists():
            old.lift(); return
        win = tk.Toplevel(self.root)
        self._cmd_win = win
        win.title("Perry - commands")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        tk.Label(win, text="WHAT PERRY LISTENS FOR", bg=BG, fg=CYAN,
                 font=("Consolas", 13, "bold")).pack(anchor="w", padx=18, pady=(16, 4))
        tk.Label(win, text='Say "Perry" first, e.g. "Perry, open VS Code".', bg=BG,
                 fg=MUTED, font=("Consolas", 9)).pack(anchor="w", padx=18, pady=(0, 10))
        grid = tk.Frame(win, bg=BG)
        grid.pack(fill="both", padx=18, pady=(0, 16))
        for r, (say, does) in enumerate(lines):
            tk.Label(grid, text=say, bg=BG, fg=TEXT, font=("Consolas", 10, "bold"),
                     anchor="w").grid(row=r, column=0, sticky="w", pady=3, padx=(0, 18))
            tk.Label(grid, text=does, bg=BG, fg=MUTED, font=("Consolas", 10),
                     anchor="w").grid(row=r, column=1, sticky="w", pady=3)
        tk.Button(win, text="Close", command=win.destroy, bg="#0a1520", fg=CYAN,
                  activebackground=CYAN_DIM, relief="flat", font=("Consolas", 10),
                  padx=14).pack(pady=(0, 16))
        win.update_idletasks()
        x = self.root.winfo_x() - win.winfo_width() - 10
        win.geometry(f"+{max(10, x)}+{max(10, self.root.winfo_y())}")

    def _tests(self) -> None:
        if self.on_tests:
            self.on_tests()

    # ---------------------------------------------------------------- drawing
    def _draw_orb(self) -> None:
        """HUD rings with a holographic platypus floating in the middle."""
        c = self.canvas
        c.delete("orb")
        cx, cy, ph = self._cx, self._cy, self._phase
        pulse = 6 * math.sin(ph) if self._pulsing else 2 * math.sin(ph)
        # Outer rings + rotating tick arcs (Jarvis vibe).
        for i, r in enumerate((86, 76)):
            rr = r + pulse * (1 - i * 0.4)
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                          outline=self._accent_dim, width=1, tags="orb")
        rot = math.degrees(ph * 0.35)
        for k in range(3):
            c.create_arc(cx - 81, cy - 81, cx + 81, cy + 81, start=rot + k * 120,
                         extent=48, style="arc", outline=self._accent, width=3, tags="orb")
        for k in range(24):
            a = math.radians(k * 15 - rot * 0.5)
            r1, r2 = 66, 70 if k % 3 else 72
            c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                          cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                          fill=self._accent_dim, tags="orb")
        self._draw_platypus(cx, cy + 2 * math.sin(ph * 0.6))

    # Low-poly platypus head, front view (original mesh). Units ~ pixels.
    _P = {
        "T": (0, -58), "TL": (-24, -52), "TR": (24, -52),
        "L1": (-40, -34), "R1": (40, -34), "L2": (-45, -10), "R2": (45, -10),
        "L3": (-37, 8), "R3": (37, 8),
        "C": (0, -30), "CL": (-20, -27), "CR": (20, -27),
        "M": (0, -6), "ML": (-22, -5), "MR": (22, -5),
        "B0L": (-31, 5), "B0R": (31, 5), "BM": (0, 7),
        "B1L": (-42, 27), "B1R": (42, 27), "BP": (0, 30),
        "B2L": (-35, 56), "B2R": (35, 56), "BB": (0, 61),
    }
    _HEAD = [("T","TL","C"),("T","C","TR"),("TL","CL","C"),("TR","C","CR"),
             ("TL","L1","CL"),("TR","CR","R1"),("L1","L2","CL"),("R1","CR","R2"),
             ("CL","L2","ML"),("CR","MR","R2"),("CL","ML","M"),("CL","M","C"),
             ("C","M","CR"),("CR","M","MR"),("L2","L3","ML"),("R2","MR","R3"),
             ("ML","L3","B0L"),("MR","B0R","R3"),("ML","B0L","BM"),("ML","BM","M"),
             ("M","BM","MR"),("MR","BM","B0R")]
    _BILL = [("B0L","B1L","BM"),("BM","B1L","BP"),("BM","BP","B1R"),("BM","B1R","B0R"),
             ("B1L","B2L","BP"),("BP","B2L","BB"),("BP","BB","B2R"),("BP","B2R","B1R")]

    def _draw_platypus(self, x: float, y: float) -> None:
        c, A, D, ph = self.canvas, self._accent, self._accent_dim, self._phase
        gap = (5 + 4 * math.sin(ph * 3)) if self._pulsing else 0.0
        drop = {"B2L": gap, "B2R": gap, "BB": gap, "BP": gap * 0.4}
        k = 1.02

        def pt(n):
            px, py = self._P[n]
            return x + px * k, y + (py + drop.get(n, 0)) * k

        shimmer = (ph * 0.9) % 9.0 - 2.0   # sweeping highlight band, top->bottom
        for tri in self._HEAD + self._BILL:
            pts = [pt(n) for n in tri]
            cy_ = sum(p[1] for p in pts) / 3 - y
            lit = abs(cy_ / 15.0 - shimmer) < 0.6
            flat = []
            for p in pts:
                flat += p
            c.create_polygon(*flat, fill=D if lit else BG, outline=A,
                             width=1.4, tags="orb")
        # Nostrils
        for sx in (-1, 1):
            nx, ny = x + sx * 9 * k, y + (47 + gap * 0.8) * k
            c.create_polygon(nx - 4 * sx, ny, nx, ny - 3, nx + 4 * sx, ny,
                             nx, ny + 2, fill=A, outline=A, tags="orb")
        # Eyes: diamonds that blink
        blink = (ph % 25) < 0.5
        for sx in (-1, 1):
            ex, ey = x + sx * 31 * k, y - 15 * k
            if blink:
                c.create_line(ex - 5, ey, ex + 5, ey, fill=A, width=2, tags="orb")
            else:
                c.create_polygon(ex - 6, ey, ex, ey - 5, ex + 6, ey, ex, ey + 5,
                                 fill=BG, outline=A, width=2, tags="orb")
                c.create_oval(ex - 2, ey - 2, ex + 2, ey + 2, fill=A,
                              outline="", tags="orb")

    def _animate(self) -> None:
        self._phase += 0.18
        self._draw_orb()
        self._draw_menu()
        self.root.after(40, self._animate)

    # --------------------------------------------------------------- controls
    def set_status(self, text: str) -> None:
        def _apply():
            self.canvas.itemconfig(self.status_id, text=text)
            self._plate("status")
        self.root.after(0, _apply)

    def set_heard(self, text: str) -> None:
        show = text if len(text) < 46 else text[:43] + "..."
        def _apply():
            self.canvas.itemconfig(self.heard_id, text=show)
            self._plate("heard")
        self.root.after(0, _apply)

    def set_listening(self, listening: bool) -> None:
        self._pulsing = listening

    def set_mode(self, mode: str) -> None:
        accent, dim = MODES.get(mode, MODES["idle"])

        def _apply():
            self._accent, self._accent_dim = accent, dim
            self.canvas.itemconfig("brand", fill=accent)

        self.root.after(0, _apply)

    def show(self) -> None:
        self.root.after(0, self._show)

    def _show(self) -> None:
        was = self.visible and self.root.state() == "normal"
        self.visible = True
        if not was:
            self._reveal()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self._taskbar()

    def _taskbar(self) -> None:
        """Frameless windows get no taskbar button by default; ask for one."""
        if sys.platform != "win32" or getattr(self, "_tb_done", False):
            return
        try:
            import ctypes
            u = ctypes.windll.user32
            hwnd = u.GetParent(self.root.winfo_id())
            GWL_EXSTYLE, APP, TOOL = -20, 0x00040000, 0x00000080
            style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
            u.SetWindowLongW(hwnd, GWL_EXSTYLE, (style & ~TOOL) | APP)
            self._tb_done = True        # set while hidden: no flash needed
        except Exception:
            pass

    def hide(self) -> None:
        self.visible = False
        self.root.after(0, self.root.withdraw)

    def run(self) -> None:
        if self.on_close:
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
