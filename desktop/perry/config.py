"""
config.py

Loads config.json and fills in anything it doesn't mention.

Keeping the defaults here (rather than scattered through `config.get(...)`
calls) means a hand-edited or half-written config file can never crash Perry,
and there's one place to look up what a setting does.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")

DEFAULTS: dict = {
    "assistant_name": "Perry",
    "hotkey": "ctrl+alt+p",

    # Start with no visible window — the HUD appears when you clap.
    "start_hidden": True,

    # None lets Windows choose the microphone. Run `python . --mics` to find
    # the index of one that actually hears you.
    "mic_device_index": None,

    # --- clap detection -----------------------------------------------------
    "clap_enabled": True,
    "claps_required": 2,
    "clap_sensitivity": 5.0,      # multiples of the room's noise floor
    "clap_min_level": 0.012,      # absolute loudness gate, 0-1
    "clap_min_width_ms": 12,      # a keystroke is ~6ms, a clap ~40ms
    "clap_min_gap_ms": 80,
    "clap_max_gap_ms": 900,

    # --- waking -------------------------------------------------------------
    "require_claps": True,
    "arm_window_seconds": 8,
    "wake_phrase": "perry wake up",
    "wake_phrase_aliases": [
        "perry wakeup", "perry wake", "berry wake up",
        "hey perry wake up", "perry awake",
    ],
    "always_on_phrases": [
        "perry daddys home", "perry daddy is home", "perry daddy home",
    ],

    # --- voice --------------------------------------------------------------
    "voice_enabled": True,
    "recognize_only_when_armed": False,
    "tts_enabled": True,
    "tts_rate": 175,
    "listen_timeout_seconds": 6,
    "phrase_time_limit_seconds": 5,

    "session_file": "last_session.json",

    # --- phone link (Android Perry) -------------------------------------
    "phone_link_enabled": True,
    "phone_link_port": 47812,
    "phone_link_token": "",   # generated on first run; see `python . --phone`

    # --- abilities ----------------------------------------------------------
    # Separate programs in sibling folders that Perry can start. See
    # perry/abilities/. Note there is no scrooge_port here on purpose:
    # Scrooge's own config.json owns that, so there is one place to change it.
    "scrooge_enabled": True,
    "scrooge_path": "../scrooge",   # relative to the Perry folder

    # --- machine ------------------------------------------------------------
    # Bring Task Manager up when Perry starts, if it isn't already open.
    # Task Manager has no switch for choosing a page, so Perry writes the
    # preference into its settings file first — see perry/system.py.
    "task_manager_on_start": True,
    "task_manager_page": "performance",
}


def load(path: str | None = None) -> dict:
    """Read config.json over the defaults. Missing or broken file -> defaults."""
    cfg = dict(DEFAULTS)
    path = path or CONFIG_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError):
        # A malformed config shouldn't stop Perry from starting.
        pass
    return cfg


def save(cfg: dict, path: str | None = None) -> None:
    path = path or CONFIG_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def session_path(cfg: dict) -> str:
    return os.path.join(ROOT, cfg.get("session_file", "last_session.json"))
