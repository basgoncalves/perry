# Perry — your Jarvis-style desktop assistant

Perry is an Iron-Man-style assistant that lives quietly in the background from
the moment Windows starts. To wake him:

> 👏 👏 &nbsp;*(clap twice)* → the orb appears, glowing amber
> 🗣️ &nbsp;**"Perry wake up"** → he restores your last working session

No hotkey to remember, no window to find. Just clap.

Session restore is still a functional stub — it relaunches the apps you had
open (browser-tab and window-layout fidelity are the next upgrade).

## How waking up works

Perry always hears the mic, but he only *acts* on two things in sequence:

1. **Two claps** put him on alert for 8 seconds. The HUD slides in with an
   amber orb — that's your confirmation he's listening.
2. **"Perry wake up"** inside those 8 seconds actually wakes him. He turns
   cyan, greets you, and restores your session.

Requiring both is deliberate. A clap alone gets triggered by a slammed door;
a phrase alone gets triggered by anyone saying "Perry" on a podcast. Together
they're essentially false-proof — and a stray false *arm* costs you nothing,
since the orb just fades away after 8 seconds.

Other ways in:

| Trigger | What happens |
|---|---|
| 👏👏 then "Perry wake up" | Restores your last session |
| "Perry, Daddy's home" | Restores your last session — works any time, no claps needed |
| `Ctrl + Alt + P` | Summons the HUD by hand and arms him |
| `Esc` or `✕` | Hides the HUD; Perry keeps listening |
| `⏻` (top-left) | Quits Perry properly — he stops listening |

## What works today

- **Clap detection** — an onset detector with three gates: a sharp attack
  relative to the recent level (so it works mid-sentence), a minimum pulse
  width (so keystrokes and mouse clicks don't count), and an immediate decay
  (so speech and music don't). Verified against a suite of synthetic
  scenarios including claps over speech and typing on a quiet mic.
- **Shared microphone** — clap detection and speech recognition run off one
  audio stream (`audio_hub.py`), because two PyAudio streams on one device is
  unreliable on Windows.
- **Silent autostart** — Perry launches hidden at login and listens.
- **Jarvis HUD** — frameless, always-on-top, glowing orb that changes colour
  with his state. Drag to move.
- **Real speech recognition** — listens on your mic and shows what it hears.
- **Talks back** — offline text-to-speech.
- **Session save/restore (stub)** — snapshots the apps that own a visible
  window to `last_session.json` and relaunches them on wake.
- **Scrooge, his first ability** — a portfolio tracker, research screener,
  watchlist and dividend-income planner. `python . --scrooge`.
- **A command prompt** — `perry` from any terminal, sharing its vocabulary
  with the voice path.
- **Task Manager on the Performance page** — brought up when Perry starts, if
  it isn't already open.

## Task Manager

When Perry starts he brings Task Manager up on the **Performance** page, if
it isn't already running. `perry system` does it on demand.

Task Manager has no command-line switch for choosing a page — it opens on
whichever one you were last on. Since Windows 11 22H2 that preference lives
in a JSON file, so Perry writes it before launching:

```
%LocalAppData%\Microsoft\Windows\TaskManager\settings.json
{"DefaultStartPage": 1}      0 Processes   1 Performance   2 App history
                             3 Startup     4 Users         5 Details
                             6 Services
```

Two consequences worth knowing. The page sticks for launches you do yourself
too, not just Perry's — that's the same setting as **Settings → Default
start page** inside Task Manager. And if you'd rather he left it alone, set
`task_manager_on_start` to `false` in `config.json`.

## Abilities

Perry is *who he is*: ears, voice, HUD, sessions. An **ability** is *something
he can do* — a separate program in a sibling folder, with its own
dependencies and its own environment.

```
perry/
├── Perry/          <- the assistant
└── scrooge/        <- the money brain
```

Perry finds and starts an ability; he never imports one. That boundary is
the point. Scrooge's Streamlit and pandas install is a few hundred megabytes
that would slow down a login that has to feel instant, so it lives in its
own `.venv` and Perry only ever hands a path to a subprocess. An ability can
break, or be deleted outright, without Perry noticing — `perry/abilities/`
holds the handful of lines that make that true.

| Ability | What it does | Open it with |
|---|---|---|
| **Scrooge** | Portfolio, research, watchlist, dividend income | `python . --scrooge` |

Scrooge has its own README in `../scrooge/`.

## The `perry` command

Double-click **`Add Perry to PATH.bat`** in the folder above this one, once.
After that, `perry` works from any folder, in any command prompt:

```
C:\> perry
Perry. Type what you want, or 'help'.
> check stocks
Opening Scrooge on Research with GOOGL, NVDA, 2331.HK ...
> quit
```

Or as a one-shot, which does the thing and exits:

```
C:\> perry check stocks
C:\> perry check stocks NVDA 2331.HK
C:\> perry system
C:\> perry help
```

Phrasing is loose, and it's the *same* vocabulary the voice path uses — so
"check stocks", "Perry, check the stocks" and "stocks" all land in the same
place whether you type them or say them. Teaching Perry a new phrase should
never mean teaching him twice.

| You type | What happens |
|---|---|
| `check stocks` | Scrooge's Research page, loaded with everything you own or watch |
| `check stocks NVDA 2331.HK` | ...loaded with just those instead |
| `portfolio` / `how am I doing` | Scrooge's portfolio overview |
| `watchlist`, `dividends` | Straight to those pages |
| `system` / `task manager` | Task Manager on the Performance page |
| `tests` | The test suite, right there in the terminal |
| `help` | Everything he knows |
| `quit` | Leaves the console; Perry keeps listening in the background |

### If `perry` isn't recognised

Two things it's almost always one of:

1. **`Add Perry to PATH.bat` hasn't been run yet.** Run it. It reports what
   it did and then checks that `perry` actually resolves, so you'll know
   before you close the window.
2. **The command prompt was already open.** A PATH change only reaches
   windows opened *afterwards*. The installer works around this by also
   dropping shims into `%LOCALAPPDATA%\Microsoft\WindowsApps`, which is
   already on your PATH — so after running it once, `perry` works even in
   terminals you had open at the time.

Either way, this always works and needs no setup at all:

```
"%USERPROFILE%\Desktop\perry\perry.cmd" check stocks
```

If the error mentions Python rather than `perry`, install Python from
python.org and tick **Add python.exe to PATH** on the first screen. Perry
falls back to the `py` launcher if `python` isn't there, but it needs one of
the two.

## Running him

Everything is one command from the project folder:

```bash
cd ~/Desktop/perry/Perry

python .            # launch the assistant (hidden, listening)
python . --show     # launch with the HUD visible — good for a first try
python . --console  # the typed console (what `perry` runs)
python . --scrooge  # open Scrooge, his money brain
python . --tests    # run the test suite in the terminal
python . --mics     # probe every microphone, find one that hears you
python . --meter    # live clap level meter, for tuning
python . --help     # this list
```

Use whichever `python` your shell has — Anaconda's, the system one, doesn't
matter. Perry's dependencies live in the project's own `.venv`, so if you
started him with a different interpreter he hands off to that one instead of
failing with "PyAudio not installed". If there's no `.venv` yet, he builds one
first.

## Tests

Click **TESTS** in the bottom-right of the HUD and the suite runs in its own
window — you watch each check go green as it happens, without leaving Perry.
The same suite runs in the terminal with `python . --tests`.

Nothing in it needs a microphone, a network connection or a real desktop
session: audio is synthesised in memory and Perry's collaborators are injected
as fakes. A suite you can run in two seconds is a suite you'll actually run.

## Setup (Windows) — automatic

Perry sets himself up. You don't create a virtual environment or install
anything by hand. On every launch, `bootstrap.py`:

1. Creates the local `.venv` if it's missing (or rebuilds it if corrupted).
2. Verifies every dependency imports, and installs/repairs anything broken —
   including the tricky **PyAudio** mic backend (with an automatic `pipwin`
   fallback) and **numpy** for the clap detector.
3. Starts Perry from the clean environment.

When everything is already healthy this check is a single fast import test, so
logging in doesn't stall.

The only prerequisite is that **Python is installed and on your PATH**.

### Turn on autostart (do this once)

```
Double-click:  Enable Perry Autostart.bat
```

That drops a shortcut in your Windows Startup folder and starts Perry right
away, so you don't have to log out. From then on he's listening every time you
log in.

To undo it: `Disable Perry Autostart.bat`.

> `SpeechRecognition`'s default recognizer uses Google's free web API, so a
> network connection is needed for voice. Clap detection is fully offline.
>
> Tip: the global hotkey and process capture work best if you launch **"as
> Administrator."** If PyAudio can't be installed at all, Perry still runs — he
> just disables voice and the `Ctrl+Alt+P` hotkey keeps working.

## Tuning the claps

Every room and microphone is different. To see exactly what Perry hears:

```bash
python . --meter
```

Clap a few times and watch the live level meter. Then adjust `config.json`:

- **Claps not registering?** Look at "peak so far" — that's how loud your claps
  actually are. Set `clap_min_level` to roughly 60% of it. Also worth raising
  the mic's own gain in Windows: **Settings → System → Sound → your input
  device → Input volume**, and check the Levels/Boost tab in the classic
  Sound control panel.
- **Random noise waking him?** Raise `clap_min_level`.
- **Typing or clicking waking him?** Raise `clap_min_width_ms` (try `18`).
- **Your two claps are too fast/slow?** Widen `clap_min_gap_ms` /
  `clap_max_gap_ms`.

## Configure

Edit `config.json`:

| Key | Meaning |
|-----|---------|
| `hotkey` | Summon combo (e.g. `ctrl+alt+p`) |
| `start_hidden` | Start with no visible window (`true` for autostart) |
| `clap_enabled` | Turn clap detection on/off |
| `claps_required` | How many claps arm him (default `2`; `1` works but false-triggers more) |
| `clap_sensitivity` | How far above the room's noise floor counts as a clap |
| `clap_min_level` | Absolute loudness gate, 0–1. Default `0.012` suits a quiet mic; raise it if noise triggers him |
| `clap_min_width_ms` | Minimum pulse length. Raise it if keystrokes/clicks trigger him, lower it if crisp claps are missed |
| `mic_device_index` | Pin a specific microphone (`null` = Windows default). Run `python . --mics` to find the number |
| `clap_min_gap_ms` / `clap_max_gap_ms` | Allowed spacing between the two claps |
| `require_claps` | If `false`, "Perry wake up" works on its own |
| `arm_window_seconds` | How long the claps keep him armed |
| `wake_phrase` / `wake_phrase_aliases` | Phrases that work once armed |
| `always_on_phrases` | Phrases that work with no claps at all |
| `recognize_only_when_armed` | If `true`, audio is only sent for transcription after you clap — more private, but the always-on phrases stop working |
| `voice_enabled` / `tts_enabled` | Mic listening / spoken replies |
| `session_file` | Where the session snapshot is stored |
| `scrooge_enabled` | Whether `python . --scrooge` works at all |
| `scrooge_path` | Where Scrooge lives, relative to the Perry folder (default `../scrooge`). Scrooge's own `config.json` owns its port, so there's one place to change it |
| `task_manager_on_start` | Bring Task Manager up when Perry starts, if it isn't already open |
| `task_manager_page` | Which page it opens on (`performance`, `processes`, `services`...) |

## Layout

```
perry/                          the folder you launch from
├── perry.cmd                   the `perry` command
├── scrooge.cmd                 the `scrooge` command
├── Add Perry to PATH.bat       run once, then both work anywhere
├── install_path.ps1            what that .bat actually does
├── Perry/                      the assistant (below)
└── scrooge/                    an ability — see its own README

Perry/
├── __main__.py                 python . lands here — nothing else
├── bootstrap.py                self-healing launcher (venv + dependencies)
├── config.json                 all your settings
│
├── perry/                      the assistant
│   ├── app.py                  the Perry class: wiring + arm-window state machine
│   ├── config.py               defaults, so a broken config.json can't stop him
│   ├── audio_hub.py            opens the mic once, fans it out to consumers
│   ├── clap_detector.py        attack / width / decay clap detection
│   ├── voice.py                speech recognition + text-to-speech
│   ├── session_manager.py      capture and restore your open apps
│   ├── hud.py                  the Jarvis HUD
│   ├── console.py              the typed console — what `perry` runs
│   ├── system.py               Task Manager on the Performance page
│   ├── test_window.py          the TESTS button's window
│   ├── tools/
│   │   ├── mic_devices.py      python . --mics
│   │   └── clap_meter.py       python . --meter
│   └── abilities/
│       └── scrooge.py          find and start ../scrooge
│
└── tests/                      python . --tests, or the TESTS button
    ├── runner.py               one runner behind both front-ends
    ├── fakes.py                synthetic audio + injectable stand-ins
    ├── test_clap_detector.py
    ├── test_wake_routing.py
    ├── test_audio_hub.py
    ├── test_voice.py
    ├── test_abilities.py
    ├── test_console.py
    ├── test_system.py
    └── test_config.py
```

`perry/app.py` takes every collaborator through its constructor, which is what
lets `tests/test_wake_routing.py` drive the real wake logic with no
microphone, no display and no apps to relaunch.

## Roadmap (next drafts)

1. Restore **browser tabs** and window positions, not just apps.
2. "Projects" — named session profiles you can switch between.
3. Offline wake-word engine, so no audio leaves the machine at all.
4. Package as a single `.exe`.
5. A **SCROOGE button** on the HUD, next to TESTS —
   `perry/abilities/scrooge.py` already has `launch(wait=False)` for it.
6. **Voice hooks into abilities**: "Perry, how's my portfolio" answered aloud
   through the TTS he already has. The console's command table is already
   the shared vocabulary — wiring `on_phrase` into `console.resolve()` is
   most of the work.
