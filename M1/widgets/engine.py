"""
widgets/engine.py

Widget engine for Milestone 1.

Responsibilities:
- Read config/layout.json at startup
- Instantiate widget objects from type strings
- Call update() and draw() on each widget every frame
- Dispatch touch events to the topmost widget under the touch point
- Catch and log widget errors without crashing the display

Adding a new widget type: create the file in widgets/, add one entry to REGISTRY.
"""

import importlib
import json
import logging
from pathlib import Path
from typing import Optional

import pygame

from core.telemetry_state import TelemetryState

log = logging.getLogger(__name__)

# Maps type string in layout.json → (module_path, class_name)
REGISTRY: dict[str, tuple[str, str]] = {
    "cpu":   ("widgets.cpu_widget",   "CpuWidget"),
    "ram":   ("widgets.ram_widget",   "RamWidget"),
    "clock": ("widgets.clock_widget", "ClockWidget"),
}


class WidgetEngine:

    def __init__(self, telemetry: TelemetryState, layout_path: str = "config/layout.json"):
        self._telemetry   = telemetry
        self._layout_path = Path(layout_path)
        self._widgets: list = []

    def load(self) -> None:
        """
        Read layout.json and instantiate all widgets.
        Call once at startup before the render loop begins.
        """
        if not self._layout_path.exists():
            log.warning(
                f"Layout file not found: {self._layout_path}. "
                "No widgets will be loaded."
            )
            return

        try:
            with open(self._layout_path, "r", encoding="utf-8") as f:
                layout = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.error(f"Failed to read layout file: {exc}")
            return

        widgets_def = layout.get("widgets", [])
        loaded = 0

        for widget_def in widgets_def:
            widget = self._instantiate(widget_def)
            if widget is not None:
                self._widgets.append(widget)
                loaded += 1

        log.info(
            f"Layout loaded from {self._layout_path}: "
            f"{loaded}/{len(widgets_def)} widgets."
        )

    def render(self, screen: pygame.Surface) -> None:
        """
        Update and draw all widgets. Called every frame.
        Errors in individual widgets are caught — one broken widget
        never stops the rest from rendering.
        """
        for widget in self._widgets:
            try:
                widget.update()
                widget.draw(screen)
            except Exception as exc:
                log.error(
                    f"Widget error [{widget.__class__.__name__}]: {exc}",
                    exc_info=True,
                )

    def handle_touch(self, x: int, y: int, gesture: str = "tap") -> bool:
        """
        Dispatch a touch event to the topmost widget under (x, y).
        Widgets are checked in reverse draw order — last drawn is topmost.
        Returns True if a widget consumed the event.
        """
        for widget in reversed(self._widgets):
            if widget.rect.collidepoint(x, y):
                try:
                    widget.on_touch(x, y, gesture)
                except Exception as exc:
                    log.error(
                        f"Touch error [{widget.__class__.__name__}]: {exc}",
                        exc_info=True,
                    )
                return True
        return False

    # ── Widget instantiation ──────────────────────────────────────────

    def _instantiate(self, widget_def: dict) -> Optional[object]:
        """
        Build a widget instance from a layout definition dict.
        Returns None and logs a warning on any failure.
        """
        wtype = widget_def.get("type", "")

        if wtype not in REGISTRY:
            log.warning(f"Unknown widget type: '{wtype}'. Skipping.")
            return None

        module_path, class_name = REGISTRY[wtype]

        try:
            module = importlib.import_module(module_path)
            cls    = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            log.error(f"Cannot load widget '{wtype}': {exc}")
            return None

        try:
            rect = pygame.Rect(
                widget_def.get("x", 0),
                widget_def.get("y", 0),
                widget_def.get("w", 200),
                widget_def.get("h", 200),
            )
            return cls(
                rect      = rect,
                config    = widget_def,
                telemetry = self._telemetry,
            )
        except Exception as exc:
            log.error(
                f"Failed to instantiate widget '{wtype}': {exc}",
                exc_info=True,
            )
            return None