"""
mic_devices.py  —  find out which microphone actually works.

Windows machines usually have several input devices: the real mic, a webcam
mic that's switched off, "Stereo Mix", a virtual cable from some app. PyAudio's
default pick is often the wrong one, and a wrong pick returns pure silence
rather than an error — which is what a level of 0.000 in clap_test.py means.

Run it and talk/clap while it probes:

    python . --mics

It lists every input device, records ~1.5s from each, and reports the level it
heard. Then put the index of the one that lit up into config.json:

    "mic_device_index": 3

Set it back to null to go with the Windows default.
"""

from __future__ import annotations

import sys

try:
    import numpy as np
except ImportError:
    print("numpy is missing. Run:  python bootstrap.py --setup-only")
    raise SystemExit(1)

try:
    import pyaudio
except ImportError:
    print("PyAudio is missing. Run:  python bootstrap.py --setup-only")
    raise SystemExit(1)

from perry import config as config_module
PROBE_SECONDS = 1.5
CHUNK = 512


def probe(pa: "pyaudio.PyAudio", index: int, rate: int) -> tuple[float, float, str]:
    """Record briefly from one device. Returns (peak, rms, error)."""
    stream = None
    try:
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=rate,
                         input=True, frames_per_buffer=CHUNK,
                         input_device_index=index)
        peak = rms_sum = 0.0
        n = 0
        for _ in range(int(PROBE_SECONDS * rate / CHUNK)):
            raw = stream.read(CHUNK, exception_on_overflow=False)
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if x.size == 0:
                continue
            peak = max(peak, float(np.max(np.abs(x))))
            rms_sum += float(np.sqrt(np.mean(x * x)))
            n += 1
        return peak, (rms_sum / n if n else 0.0), ""
    except Exception as e:
        return 0.0, 0.0, str(e)[:60]
    finally:
        try:
            if stream is not None:
                stream.stop_stream()
                stream.close()
        except Exception:
            pass


def main() -> int:
    pa = pyaudio.PyAudio()

    try:
        default_index = pa.get_default_input_device_info()["index"]
    except Exception:
        default_index = None

    inputs = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if int(info.get("maxInputChannels", 0)) > 0:
            inputs.append((i, info))

    if not inputs:
        print("No input devices at all. Windows may be blocking microphone "
              "access — check Settings > Privacy & security > Microphone.")
        pa.terminate()
        return 1

    print(f"Found {len(inputs)} input device(s). "
          f"Windows default is index {default_index}.")
    print(f"Recording {PROBE_SECONDS}s from each — "
          f"CLAP AND TALK CONTINUOUSLY while this runs.\n")
    print(f"{'idx':>4}  {'peak':>6}  {'rms':>6}  {'':2} device")
    print("-" * 76)

    results = []
    for i, info in inputs:
        rate = int(info.get("defaultSampleRate", 44100))
        peak, rms, err = probe(pa, i, rate)
        name = str(info.get("name", "?"))[:44]
        mark = "<-- default" if i == default_index else ""
        if err:
            print(f"{i:>4}  {'--':>6}  {'--':>6}     {name}   [{err}]")
        else:
            flag = "OK" if peak > 0.02 else "  "
            print(f"{i:>4}  {peak:>6.3f}  {rms:>6.3f}  {flag}  {name} {mark}")
            results.append((peak, i, name))
    pa.terminate()

    live = sorted((r for r in results if r[0] > 0.02), reverse=True)
    print()
    if not live:
        print("Every device read silence. That's almost always one of:")
        print("  1. Windows is blocking mic access for desktop apps.")
        print("     Settings > Privacy & security > Microphone ->")
        print("     turn ON 'Microphone access' AND")
        print("     'Let desktop apps access your microphone'.")
        print("  2. The mic is muted in the Windows volume mixer.")
        print("  3. You weren't making noise while it probed. Try again, loudly.")
        return 1

    best_peak, best_index, best_name = live[0]
    print(f"Loudest device: index {best_index} — {best_name} (peak {best_peak:.3f})")
    print("\nTo lock Perry onto it, set this in config.json:")
    print(f'    "mic_device_index": {best_index}')

    if "--set" in sys.argv:
        cfg = config_module.load()
        cfg["mic_device_index"] = best_index
        config_module.save(cfg)
        print(f"\nDone — config.json now uses device {best_index}.")
    else:
        print("Or re-run this with --set to write it for you:")
        print("    python . --mics --set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
