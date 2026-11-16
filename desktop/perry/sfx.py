"""
sfx.py — Perry's SFX Lab (test tool).

Adds sound effects to a video, the way an editor does in a sound-design pass:
    1. find the moments that need a sound (scene cuts, via ffmpeg), or type them
    2. pick an effect for each moment (whoosh, click, pop, typing, ding, ...)
    3. mix the effects under the original audio and write <name>_sfx.mp4

The effects are synthesised here with numpy, so it works offline with no
account. Cue format, one per line:   <seconds> <effect> [gain]
e.g.   1.20 whoosh      3.5 click 0.6      7 riser
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import wave

import numpy as np

SR = 44100
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# ----------------------------------------------------------------- synthesis
def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def _noise(n: int, rng) -> np.ndarray:
    return rng.standard_normal(n)


def _lowpass(x: np.ndarray, alpha) -> np.ndarray:
    """One-pole low-pass; alpha may be an array (a sweeping filter)."""
    alpha = np.broadcast_to(alpha, x.shape)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha[i] * (x[i] - acc)
        y[i] = acc
    return y


def whoosh(rng, dur=0.6):
    n = int(SR * dur)
    t = np.linspace(0, 1, n)
    sweep = 0.02 + 0.35 * np.sin(np.pi * t) ** 2          # filter opens then closes
    x = _lowpass(_noise(n, rng), sweep)
    return x * np.sin(np.pi * t) ** 1.5


def riser(rng, dur=1.2):
    n = int(SR * dur)
    t = np.linspace(0, 1, n)
    x = _lowpass(_noise(n, rng), 0.01 + 0.4 * t ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * t ** 2) / SR) * 0.3
    return (x + tone) * t ** 2 * (1 - np.clip((t - 0.95) * 20, 0, 1))


def click(rng, dur=0.03):
    n = int(SR * dur)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 3200 * t) * 0.6 + _noise(n, rng) * 0.4) * _env(n, 0.0005, 0.004)


def pop(rng, dur=0.12):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 30) + 180
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.001, 0.03)


def typing(rng, dur=0.9):
    n = int(SR * dur)
    out = np.zeros(n)
    pos = 0
    while pos < n - 2000:
        k = click(rng, 0.025) * rng.uniform(0.4, 1.0)
        out[pos:pos + len(k)] += k
        pos += int(SR * rng.uniform(0.06, 0.14))
    return out


def ding(rng, dur=1.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1320 * t) + 0.4 * np.sin(2 * np.pi * 2640 * t)
            + 0.2 * np.sin(2 * np.pi * 3960 * t)) * _env(n, 0.002, 0.25) * 0.6


def thud(rng, dur=0.35):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = 120 * np.exp(-t * 8) + 45
    body = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return (body + _lowpass(_noise(n, rng), 0.05) * 0.5) * _env(n, 0.001, 0.08)


def swipe(rng, dur=0.25):
    return whoosh(rng, dur) * 0.8


EFFECTS = {"whoosh": whoosh, "riser": riser, "click": click, "pop": pop,
           "typing": typing, "ding": ding, "thud": thud, "swipe": swipe}


def make(kind: str, seed: int = 0) -> np.ndarray:
    fn = EFFECTS.get(kind)
    if fn is None:
        raise ValueError(f"unknown effect '{kind}' — try: {', '.join(EFFECTS)}")
    x = fn(np.random.default_rng(seed))
    peak = np.max(np.abs(x)) or 1.0
    return (x / peak * 0.8).astype(np.float32)


# ----------------------------------------------------------------------- cues
_CUE = re.compile(r"^\s*([\d.]+)\s*s?\s+([a-z]+)(?:\s+([\d.]+))?\s*$", re.I)


def parse_cues(text: str) -> list[tuple[float, str, float]]:
    cues, bad = [], []
    for line in text.splitlines():
        line = line.split("#")[0]
        if not line.strip():
            continue
        m = _CUE.match(line)
        if not m or m.group(2).lower() not in EFFECTS:
            bad.append(line.strip())
            continue
        cues.append((float(m.group(1)), m.group(2).lower(), float(m.group(3) or 1.0)))
    if bad:
        raise ValueError("can't read: " + "; ".join(bad[:3]))
    return sorted(cues)


def format_cues(cues) -> str:
    return "\n".join(f"{t:.2f} {k}" + ("" if g == 1.0 else f" {g:g}") for t, k, g in cues)


def mix(cues, length_s: float) -> np.ndarray:
    out = np.zeros(int(SR * max(length_s, 0.1)) + SR, dtype=np.float32)
    for i, (t, kind, gain) in enumerate(cues):
        x = make(kind, seed=i) * gain
        start = int(t * SR) - (len(x) // 2 if kind in ("whoosh", "swipe") else 0)  # centre whooshes on the cut
        start = max(0, start)
        end = min(len(out), start + len(x))
        out[start:end] += x[:end - start]
    return np.clip(out, -1, 1)


def write_wav(path: str, x: np.ndarray) -> str:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return path


# --------------------------------------------------------------------- ffmpeg
def ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _run(args) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, creationflags=_NO_WINDOW)


def duration(video: str) -> float:
    probe = shutil.which("ffprobe")
    if probe:
        r = _run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video])
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    r = _run([ffmpeg(), "-i", video])
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def has_audio(video: str) -> bool:
    return bool(re.search(r"Stream #.*Audio", _run([ffmpeg(), "-i", video]).stderr))


def detect_cuts(video: str, threshold: float = 0.3, min_gap: float = 0.5) -> list[float]:
    """Scene-change times in seconds (ffmpeg's scene score)."""
    r = _run([ffmpeg(), "-hide_banner", "-i", video, "-an",
              "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"])
    times, last = [], -9.0
    for m in re.finditer(r"pts_time:([\d.]+)", r.stderr):
        t = float(m.group(1))
        if t - last >= min_gap:
            times.append(t)
            last = t
    return times


def auto_cues(video: str, threshold: float = 0.3) -> list[tuple[float, str, float]]:
    """Whoosh on every cut, a riser into the first one, a ding at the end."""
    cuts = detect_cuts(video, threshold)
    dur = duration(video)
    cues = [(t, "whoosh", 1.0) for t in cuts]
    if cuts and cuts[0] > 1.4:
        cues.append((cuts[0] - 1.2, "riser", 0.5))
    if dur > 1.5:
        cues.append((max(0.0, dur - 1.0), "ding", 0.6))
    return sorted(cues)


def render(video: str, cues, out: str | None = None, sfx_gain: float = 1.0) -> str:
    """Write <video>_sfx.mp4 with the effects mixed under the original sound."""
    if not ffmpeg():
        raise RuntimeError("ffmpeg not found — install it (winget install ffmpeg) and restart Perry")
    base, _ = os.path.splitext(video)
    out = out or base + "_sfx.mp4"
    wav = base + "_sfx_track.wav"
    write_wav(wav, mix(cues, duration(video)) * sfx_gain)
    if has_audio(video):
        fc = "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        fc = "[1:a]apad[a]"
    args = [ffmpeg(), "-y", "-i", video, "-i", wav, "-filter_complex", fc,
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", out]
    r = _run(args)
    try:
        os.remove(wav)
    except OSError:
        pass
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr else "ffmpeg failed")
    return out


def preview(kind: str) -> None:
    """Play one effect (Windows) — used by the SFX Lab's effect buttons."""
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"perry_sfx_{kind}.wav")
    write_wav(path, make(kind))
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
