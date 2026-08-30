"""
widgets/ram_widget.py

RAM usage widget — horizontal bar with numeric readout.

Displays:
- Horizontal fill bar (colour-coded ok/warn/crit)
- Used / Total in GB
- Usage percentage

Tap to cycle display mode:
  bar   → horizontal bar (default)
  large → large percentage only, minimal style
"""

import os
import sys

import pygame

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.settings import SETTINGS
from core.telemetry_state import TelemetryState
from widgets.base import BaseWidget, PADDING


class RamWidget(BaseWidget):

    MODES = ("bar", "large")

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

        used  = self.telemetry.get("ram_used",  0.0)
        total = self.telemetry.get("ram_total", 1.0) or 1.0
        pct   = self.telemetry.get("ram_pct",   0.0)
        color = self.value_color(pct)
        w, h  = self.rect.w, self.rect.h

        if self._mode == "bar":
            self._draw_bar_mode(surf, used, total, pct, color, w, h)
        elif self._mode == "large":
            self._draw_large_mode(surf, pct, used, total, color, w, h)

        self.commit_frame(screen)

    # ── Bar mode ──────────────────────────────────────────────────────

    def _draw_bar_mode(
        self,
        surf:  pygame.Surface,
        used:  float,
        total: float,
        pct:   float,
        color: tuple,
        w:     int,
        h:     int,
    ) -> None:
        # Header labels
        self.draw_text(surf, "RAM",
                       PADDING, PADDING, 12, SETTINGS.color_subtext)
        self.draw_text(surf, f"{used:.1f} / {total:.0f} GB",
                       w - PADDING, PADDING, 12, SETTINGS.color_subtext, "topright")

        # Bar track
        bar_x = PADDING
        bar_y = h // 2 - 10
        bar_w = w - PADDING * 2
        bar_h = 20
        pygame.draw.rect(
            surf, SETTINGS.color_border,
            (bar_x, bar_y, bar_w, bar_h),
            border_radius=5,
        )

        # Bar fill
        fill_w = max(0, int(bar_w * pct / 100))
        if fill_w > 0:
            pygame.draw.rect(
                surf, color,
                (bar_x, bar_y, fill_w, bar_h),
                border_radius=5,
            )

        # Percentage below bar
        self.draw_text(
            surf, f"{pct:.0f}%",
            w // 2, bar_y + bar_h + 8,
            14, color, "midtop",
        )

    # ── Large mode ────────────────────────────────────────────────────

    def _draw_large_mode(
        self,
        surf:  pygame.Surface,
        pct:   float,
        used:  float,
        total: float,
        color: tuple,
        w:     int,
        h:     int,
    ) -> None:
        self.draw_text(surf, f"{pct:.0f}%",
                       w // 2, h // 2 - 14, 36, color, "center")
        self.draw_text(surf, "RAM",
                       w // 2, h // 2 + 16, 12, SETTINGS.color_subtext, "center")
        self.draw_text(surf, f"{used:.1f}/{total:.0f}GB",
                       w // 2, h // 2 + 34, 11, SETTINGS.color_subtext, "center")