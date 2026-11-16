"""Draws perry.ico — the low-poly platypus head from the HUD, in a glowing ring.
Usage: python make_platypus_icon.py   (needs Pillow)"""
import math, os, sys, types
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024
CY, DIM, BG = (34, 211, 238), (14, 116, 144), (4, 7, 13)

sys.modules.setdefault("tkinter", types.ModuleType("tkinter"))
src = open(os.path.join(HERE, "perry", "hud.py"), encoding="utf-8").read()
ns = {}; exec(src.replace("import tkinter as tk", ""), ns)
H = ns["PerryHUD"]

def render():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2
    d.ellipse((24, 24, S - 24, S - 24), fill=BG + (255,))
    for k in range(3):  # tick arcs
        d.arc((70, 70, S - 70, S - 70), -100 + k * 120, -40 + k * 120, fill=CY, width=30)
    d.ellipse((120, 120, S - 120, S - 120), outline=DIM, width=10)
    k = 6.2
    P = H._P
    def pt(n): return (c + P[n][0] * k, c + 10 + P[n][1] * k)
    for i, tri in enumerate(H._HEAD + H._BILL):
        pts = [pt(n) for n in tri]
        d.polygon(pts, fill=DIM if i % 5 == 0 else BG, outline=CY, width=12)
    for sx in (-1, 1):  # eyes
        ex, ey = c + sx * 31 * k, c + 10 - 15 * k
        d.polygon([(ex - 40, ey), (ex, ey - 32), (ex + 40, ey), (ex, ey + 32)], fill=BG, outline=CY, width=12)
        d.ellipse((ex - 14, ey - 14, ex + 14, ey + 14), fill=CY)
        nx, ny = c + sx * 9 * k, c + 10 + 47 * k
        d.polygon([(nx - 24 * sx, ny), (nx, ny - 18), (nx + 24 * sx, ny), (nx, ny + 12)], fill=CY)
    glow = img.filter(ImageFilter.GaussianBlur(14))
    return Image.alpha_composite(glow, img)

big = render()
big.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "perry_icon.png"))
big.save(os.path.join(HERE, "perry.ico"), format="ICO",
         sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)])
print("Created perry.ico")
