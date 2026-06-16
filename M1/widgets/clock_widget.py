"""
widgets/clock_widget.py

Clock widget — displays current time and date.

Tap to cycle display mode:
  full  → HH:MM:SS + full date (default)
  time  → HH:MM only, large
  date  → date only
"""

import time

import pygame

from core.settings import SETTINGS
from core.telemetry_state import TelemetryState
from widgets.base import BaseWidget, PADDING


class ClockWidget(BaseWidget):

    MODES = ("full", "time", "date")

    def __init__(self, rect: pygame.Rect, config: dict, telemetry: TelemetryState):
        super().__init__(rect, config, telemetry)
        self._mode_index = 0

    @property
    def _mode(self) -> str:
        return self.MODES[self._mode_index]

    def on_touch(self, x: int, y: int, gesture: str = "tap") -> None:
        self._mode_index = (self._mode_index + 1) % len(self.MODES)

    def draw(self, screen: pygame.Surface) -> None:
        surf = self.begin_frame()
        w, h = self.rect.w, self.rect.h
        cx   = w // 2
        cy   = h // 2

        now  = time.localtime()

        if self._mode == "full":
            self.draw_text(
                surf, time.strftime("%H:%M:%S", now),
                cx, cy - 14, 22, SETTINGS.color_accent, "center",
            )
            self.draw_text(
                surf, time.strftime("%A", now),
                cx, cy + 10, 12, SETTINGS.color_subtext, "center",
            )
            self.draw_text(
                surf, time.strftime("%d %B %Y", now),
                cx, cy + 26, 11, SETTINGS.color_subtext, "center",
            )

        elif self._mode == "time":
            self.draw_text(
                surf, time.strftime("%H:%M", now),
                cx, cy, 34, SETTINGS.color_accent, "center",
            )
            self.draw_text(
                surf, time.strftime("%S", now),
                cx, cy + 28, 14, SETTINGS.color_subtext, "center",
            )

        elif self._mode == "date":
            self.draw_text(
                surf, time.strftime("%d", now),
                cx, cy - 14, 34, SETTINGS.color_accent, "center",
            )
            self.draw_text(
                surf, time.strftime("%B %Y", now),
                cx, cy + 16, 13, SETTINGS.color_subtext, "center",
            )

        self.commit_frame(screen)