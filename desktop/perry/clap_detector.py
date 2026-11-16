"""
clap_detector.py

Detects a deliberate double clap in a live microphone stream.

The hard part isn't hearing a loud noise — it's *not* firing on speech, music,
a slammed door or a keyboard. A clap has a signature those mostly lack:

  • a sharp onset that jumps far above the room's current noise floor, and
  • an almost immediate decay — it's gone within ~200 ms.

So each loud onset is held as "pending", and only counted once we've watched
it fall back near the floor. Speech sustains energy through that window and is
rejected. Two confirmed claps inside a short window fire the callback.

Everything is measured against an adaptive background level, so a quiet room
and a noisy café both work without you touching the settings. Run
`python clap_test.py` to watch the levels live and tune `config.json`.
"""

from __future__ import annotations

from typing import Callable

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


class ClapDetector:
    def __init__(
        self,
        on_claps: Callable[[], None],
        claps_required: int = 2,
        rate: int = 16000,
        sensitivity: float = 5.0,      # how far above the noise floor counts as an onset
        abs_floor: float = 0.07,       # absolute RMS gate (0-1); ignores quiet rooms' spikes
        attack_ratio: float = 2.8,     # jump over the last ~100 ms that counts as an attack
        min_width_ms: float = 12.0,    # a clap has body; a key click is over in ~10 ms
        min_gap_ms: int = 80,          # fastest believable gap between two claps
        max_gap_ms: int = 900,         # slowest — beyond this they're separate events
        transient_ms: int = 170,       # how long to wait before judging the decay
        decay_ratio: float = 0.45,     # must fall to this fraction of peak = transient
        cooldown_ms: int = 1500,       # ignore everything right after a trigger
        refractory_ms: int = 70,       # minimum spacing between counted onsets
        on_clap: Callable[[int], None] | None = None,
    ):
        self.available = np is not None
        self.on_claps = on_claps
        self.on_clap = on_clap or (lambda _n: None)
        self.claps_required = max(1, int(claps_required))
        self.rate = rate
        self.sensitivity = float(sensitivity)
        self.abs_floor = float(abs_floor)
        self.attack_ratio = float(attack_ratio)
        self.min_width = min_width_ms / 1000.0
        self.min_gap = min_gap_ms / 1000.0
        self.max_gap = max_gap_ms / 1000.0
        self.transient = transient_ms / 1000.0
        self.decay_ratio = float(decay_ratio)
        self.cooldown = cooldown_ms / 1000.0
        self.refractory = refractory_ms / 1000.0

        # Live state (all times are seconds of audio processed, not wall clock,
        # so a stuttering thread can't skew the gap measurements).
        self._frames = 0
        self._bg: float | None = None      # slow noise floor (quiet frames only)
        self._fast: float | None = None    # last ~100 ms level, for attack detection
        self._pending: dict | None = None
        self._last_onset_t = -1e9
        self._claps: list[float] = []
        self._mute_until = -1e9

        # Exposed for the tuning script / HUD.
        self.last_level = 0.0
        self.last_threshold = 0.0

    # ------------------------------------------------------------------ input
    def feed(self, data: bytes) -> None:
        """Feed one chunk of raw 16-bit mono PCM. Called from the audio thread."""
        if not self.available:
            return
        samples = np.frombuffer(data, dtype=np.int16)
        if samples.size == 0:
            return
        x = samples.astype(np.float32) / 32768.0

        t = self._frames / float(self.rate)
        self._frames += samples.size

        rms = float(np.sqrt(np.mean(x * x)))
        peak = float(np.max(np.abs(x)))
        self.last_level = rms

        if self._bg is None:
            self._bg = rms
        if self._fast is None:
            self._fast = rms

        threshold = max(self.abs_floor, self._bg * self.sensitivity)
        self.last_threshold = threshold

        loud = rms > threshold and peak > self.abs_floor
        # An attack is a sharp jump over the *recent* level, not just over the
        # room's noise floor. That's what lets a clap still register while
        # you're mid-sentence or music is playing — the absolute level is
        # already high, but a clap still leaps well above it.
        attack = rms > self._fast * self.attack_ratio
        prev_fast = self._fast
        self._fast = 0.65 * self._fast + 0.35 * rms

        if not loud:
            # The background only ever learns from quiet frames, so a long loud
            # passage can't slowly desensitise the detector.
            self._bg = 0.94 * self._bg + 0.06 * rms

        # 1. Resolve an onset we're already watching.
        if self._pending is not None:
            self._pending["peak"] = max(self._pending["peak"], rms)

            # 1a. Width gate, judged on the onset chunk plus the next one.
            # A clap has body — it stays near its peak for tens of
            # milliseconds. A keystroke, a mouse click or a cutlery clink is a
            # spike that's gone in under ten. Without this, lowering the
            # loudness gate far enough to hear a quiet clap also makes typing
            # look like clapping.
            if "width_buf" in self._pending:
                buf = np.concatenate([self._pending.pop("width_buf"), x])
                if self._width_seconds(buf) < self.min_width:
                    self._pending = None
                    return

            if t - self._pending["t"] >= self.transient:
                floor = max(self._pending["base"], self._bg)
                decayed = rms <= max(self._pending["peak"] * self.decay_ratio,
                                     floor * 1.6)
                if decayed:
                    self._count_clap(self._pending["t"])
                self._pending = None
            return

        # 2. Look for a new attack.
        if (loud and attack
                and t >= self._mute_until
                and t - self._last_onset_t >= self.refractory):
            self._pending = {"t": t, "peak": rms, "base": prev_fast,
                             "width_buf": x}
            self._last_onset_t = t

    def _width_seconds(self, x, frac: float = 0.15) -> float:
        """How long the sound actually stays near its own peak."""
        mag = np.abs(x)
        pk = float(np.max(mag))
        if pk <= 0:
            return 0.0
        return float(np.count_nonzero(mag > frac * pk)) / float(self.rate)

    # ----------------------------------------------------------------- counting
    def _count_clap(self, t: float) -> None:
        self._claps = [c for c in self._claps if t - c <= self.max_gap]
        self._claps.append(t)
        self.on_clap(len(self._claps))

        if len(self._claps) < self.claps_required:
            return

        recent = self._claps[-self.claps_required:]
        gaps = [b - a for a, b in zip(recent, recent[1:])]
        if all(self.min_gap <= g <= self.max_gap for g in gaps):
            self._claps = []
            self._mute_until = t + self.cooldown
            try:
                self.on_claps()
            except Exception:
                pass

    def reset(self) -> None:
        """Forget partial claps — call this after Perry wakes."""
        self._claps = []
        self._pending = None
        self._mute_until = self._frames / float(self.rate) + self.cooldown
