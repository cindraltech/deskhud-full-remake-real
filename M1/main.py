#!/usr/bin/env python3
"""
main.py — DeskHUD Milestone 1 Entry Point

Boots the application in this order:
  1. Configure logging
  2. Create TelemetryState (shared data store)
  3. Start MockSource thread (writes psutil data to state)
  4. Load widget layout from config/layout.json
  5. Initialise touch handler
  6. Open display and run render loop
  7. Clean shutdown on exit

Run on Pi:
    python3 main.py

Run on desktop (windowed, mouse as touch):
    DESKHUD_WINDOWED=1 python3 main.py
"""

import logging
import os
import signal
import sys

# ── Logging setup (before any imports that use logging) ───────────────
LOG_LEVEL = logging.DEBUG if os.environ.get("DESKHUD_DEBUG") else logging.INFO
logging.basicConfig(
    level   = LOG_LEVEL,
    format  = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt = "%H:%M:%S",
    stream  = sys.stdout,
)
log = logging.getLogger("main")

# ── Force windowed mode when env var is set ───────────────────────────
if os.environ.get("DESKHUD_WINDOWED"):
    from core import settings as _settings_module
    from dataclasses import replace
    _settings_module.SETTINGS = replace(_settings_module.SETTINGS, fullscreen=False)

# ── Imports ───────────────────────────────────────────────────────────
from core.settings        import SETTINGS
from core.telemetry_state import TelemetryState
from core.renderer        import Renderer
from telemetry.mock_source import MockSource
from widgets.engine       import WidgetEngine
from input.touch          import TouchHandler


def main() -> int:
    log.info("DeskHUD Milestone 1 — Starting")
    log.info(f"Display: {SETTINGS.width}x{SETTINGS.height} @ {SETTINGS.fps}fps")

    # ── 1. Shared telemetry store ─────────────────────────────────────
    telemetry = TelemetryState()

    # ── 2. Mock telemetry source ──────────────────────────────────────
    source = MockSource(telemetry)
    source.start()
    log.info("MockSource started.")

    # ── 3. Widget engine ──────────────────────────────────────────────
    engine = WidgetEngine(telemetry, layout_path="config/layout.json")
    engine.load()

    # ── 4. Touch handler ──────────────────────────────────────────────
    touch = TouchHandler()
    touch.start()

    # ── 5. Renderer ───────────────────────────────────────────────────
    renderer = Renderer(widget_engine=engine, touch_handler=touch)

    # Graceful shutdown on SIGTERM (systemd stop) and SIGINT (Ctrl+C)
    def _handle_signal(sig, frame):
        log.info(f"Received signal {sig}. Shutting down...")
        renderer.stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    try:
        renderer.init()
        renderer.run()   # blocks until quit
    except Exception as exc:
        log.critical(f"Fatal error: {exc}", exc_info=True)
        return 1
    finally:
        source.stop()
        log.info("DeskHUD shut down cleanly.")

    return 0


if __name__ == "__main__":
    sys.exit(main())