"""
make_icon.py

Converts your BioScout image into a multi-resolution Windows icon (perry.ico).

Usage:
    python make_icon.py [source_image]

If no source is given, it looks for the first of these in this folder:
    icon_source.png, bioscout.png, perry.png, icon.png, icon_source.jpg
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = ["icon_source.png", "bioscout.png", "perry.png", "icon.png",
              "icon_source.jpg", "icon_source.jpeg"]
SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]


def find_source() -> str | None:
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return sys.argv[1]
    for name in CANDIDATES:
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            return path
    return None


def main() -> int:
    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required. Run:  pip install pillow")
        return 1

    src = find_source()
    if not src:
        print("No source image found. Save your icon image into this folder as "
              "'icon_source.png' and run again.")
        return 1

    img = Image.open(src).convert("RGBA")
    # Make it square (pad transparent) so the icon isn't distorted.
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))

    out = os.path.join(HERE, "perry.ico")
    square.save(out, format="ICO", sizes=SIZES)
    print(f"Created {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
