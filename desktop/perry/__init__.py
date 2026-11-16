"""
Perry — an Iron-Man / Jarvis-style desktop assistant for Windows.

Two claps arm him, "Perry wake up" restores your last working session.

Module map:
    app             the Perry class — wires everything together, owns the
                    arm-window state machine
    config          loading and defaults for config.json
    audio_hub       opens the microphone once, fans the stream to consumers
    clap_detector   double-clap detection
    voice           speech recognition + text-to-speech
    session_manager capture/restore of open applications
    hud             the tkinter heads-up display
    console         Perry at a command prompt — the `perry` command
    system          Windows housekeeping (Task Manager on the Performance page)
    test_window     the in-app test runner window
    tools/          standalone diagnostics (mic probe, clap level meter)
    abilities/      how Perry starts the programs in sibling folders
                    (scrooge — the money brain)
"""

__version__ = "0.3.0"
