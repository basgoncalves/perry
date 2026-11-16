"""
clap_meter.py  —  tune Perry's clap detection.

Run it, clap a few times, and watch the meter:

    python . --meter

Each line shows the live level, the loudest thing heard so far, and the
threshold a sound has to beat. "CLAP" appears for every confirmed single clap;
"*** DOUBLE CLAP ***" when a pair lands close enough together to arm Perry.

On exit it tells you which number in config.json to change. Ctrl+C to stop.
"""

from __future__ import annotations

import sys
import time

from perry import config as config_module
from perry.audio_hub import AudioHub
from perry.clap_detector import ClapDetector


def main() -> int:
    cfg = config_module.load()

    device = cfg.get("mic_device_index")
    if "--device" in sys.argv:
        device = int(sys.argv[sys.argv.index("--device") + 1])

    hits = {"single": 0, "double": 0}

    def on_clap(n):
        hits["single"] += 1
        print(f"\n   CLAP  (#{n} in this group)")

    def on_claps():
        hits["double"] += 1
        print("\n   *** DOUBLE CLAP — Perry would arm here ***")

    hub = AudioHub(device_index=device)
    det = ClapDetector(
        on_claps=on_claps,
        on_clap=on_clap,
        claps_required=cfg.get("claps_required", 2),
        rate=hub.rate,
        sensitivity=cfg.get("clap_sensitivity", 5.0),
        abs_floor=cfg.get("clap_min_level", 0.012),
        min_width_ms=cfg.get("clap_min_width_ms", 12),
        min_gap_ms=cfg.get("clap_min_gap_ms", 80),
        max_gap_ms=cfg.get("clap_max_gap_ms", 900),
    )

    if not det.available:
        print("numpy is missing. Run:  python bootstrap.py --setup-only")
        return 1
    if not hub.start():
        print(f"Microphone unavailable: {hub.error}")
        print("Find one that works:  python . --mics")
        return 1

    det.rate = hub.rate
    hub.add_raw_listener(det.feed)
    label = "Windows default" if device is None else f"device {device}"
    print(f"Listening at {hub.rate} Hz on the {label}. "
          f"Clap twice. Ctrl+C to stop.\n")

    loudest = 0.0
    try:
        while True:
            time.sleep(0.1)
            level, threshold = det.last_level, det.last_threshold
            loudest = max(loudest, level)
            bar = "#" * min(40, int(level * 120))
            print(f"\rlevel {level:0.3f}  peak so far {loudest:0.3f}  "
                  f"threshold {threshold:0.3f}  |{bar:<40}|",
                  end="", flush=True)
    except KeyboardInterrupt:
        gate = cfg.get("clap_min_level", 0.012)
        print(f"\n\nClaps detected: {hits['single']}   "
              f"Double claps: {hits['double']}   Loudest level: {loudest:0.3f}")
        if loudest < 0.005:
            print("\nThat's silence — this microphone isn't delivering audio.")
            print("Find one that works:  python . --mics")
        elif loudest < gate:
            print(f"\nYour claps peaked at {loudest:0.3f}, under the {gate} gate.")
            print(f'Set "clap_min_level" in config.json to about '
                  f'{max(0.004, loudest * 0.6):0.3f} and try again.')
        elif hits["double"] == 0 and hits["single"] >= 2:
            print("\nSingle claps registered but never paired up. Try clapping "
                  "closer together, or widen \"clap_max_gap_ms\".")
    finally:
        hub.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
