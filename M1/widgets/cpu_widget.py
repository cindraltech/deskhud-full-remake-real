"""
widgets/cpu_widget.py

CPU usage widget — circular arc gauge.

Displays:
- Circular arc showing usage % (colour-coded ok/warn/crit)
- Usage percentage in the centre
- Temperature below the percentage
- CPU frequency at the bottom (small)

Tap to cycle display mode:
  usage  → shows usage % (default)
  temp   → shows temperature °C prominently
  freq   → shows clock speed GHz prominently

Arc rendering uses pre-calculated point steps.
The arc surface is NOT pre-rendered because the value changes
every frame and colour-coding changes with it.
"""

import math

import pygame

from core.settings import SETTINGS
from core.telemetry_state import TelemetryState
from widgets.base import BaseWidget, PADDING


class CpuWidget(BaseWidget):

    MODES = ("usage", "temp", "freq")

    # Arc geometry
    ARC_START_DEG = 150    # start angle (degrees from 3 o'clock, going counter-clockwise)
    ARC_SWEEP_DEG = 240    # total sweep in degrees
    ARC_WIDTH     = 10     # line width in pixels

    def __init__(self, rect: pygame.Rect, config: dict, telemetry: TelemetryState):
        super().__init__(rect, config, telemetry)
        self._mode_index = 0   # index into MODES

    @property
    def _mode(self) -> str:
        return self.MODES[self._mode_index]

    def on_touch(self, x: int, y: int, gesture: str = "tap") -> None:
        """Cycle through display modes on tap."""
        self._mode_index = (self._mode_index + 1) % len(self.MODES)

    def draw(self, screen: pygame.Surface) -> None:
        surf = self.begin_frame()

        cx = self.rect.w // 2
        cy = self.rect.h // 2
        r  = min(cx, cy) - PADDING - self.ARC_WIDTH

        usage = self.telemetry.get("cpu_usage", 0.0)
        temp  = self.telemetry.get("cpu_temp",  0.0)
        freq  = self.telemetry.get("cpu_freq",  0.0)

        usage_color = self.value_color(usage)
        temp_color  = self.temp_color(temp)

        # Draw track arc (background)
        self._draw_arc(surf, cx, cy, r, 0, 100, SETTINGS.color_border)

        # Draw value arc
        self._draw_arc(surf, cx, cy, r, 0, usage, usage_color)

        # Centre content depends on mode
        if self._mode == "usage":
            self.draw_text(surf, f"{usage:.0f}%",  cx, cy - 18, 30, usage_color, "center")
            self.draw_text(surf, "CPU",             cx, cy + 12, 12, SETTINGS.color_subtext, "center")
            if temp > 0:
                self.draw_text(surf, f"{temp:.0f}°C", cx, cy + 30, 11, temp_color, "center")

        elif self._mode == "temp":
            self.draw_text(surf, f"{temp:.0f}°",   cx, cy - 18, 30, temp_color, "center")
            self.draw_text(surf, "TEMP",            cx, cy + 12, 12, SETTINGS.color_subtext, "center")
            self.draw_text(surf, f"{usage:.0f}%",  cx, cy + 30, 11, usage_color, "center")

        elif self._mode == "freq":
            ghz = freq / 1000 if freq > 0 else 0.0
            self.draw_text(surf, f"{ghz:.1f}",     cx, cy - 18, 30, SETTINGS.color_accent, "center")
            self.draw_text(surf, "GHz",             cx, cy + 12, 12, SETTINGS.color_subtext, "center")
            self.draw_text(surf, f"{usage:.0f}%",  cx, cy + 30, 11, usage_color, "center")

        # Mode indicator dots at the bottom
        self._draw_mode_dots(surf)

        self.commit_frame(screen)

    # ── Arc drawing ───────────────────────────────────────────────────

    def _draw_arc(
        self,
        surf:  pygame.Surface,
        cx:    int,
        cy:    int,
        r:     int,
        v_start: float,
        v_end:   float,
        color: tuple,
    ) -> None:
        """
        Draw a portion of a circular arc from v_start% to v_end%
        of the total ARC_SWEEP_DEG range.
        """
        if v_end <= v_start:
            return

        steps = max(1, int((v_end - v_start) / 100 * self.ARC_SWEEP_DEG))
        half  = self.ARC_WIDTH // 2

        for i in range(steps):
            pct   = (v_start + i) / 100.0
            angle = math.radians(self.ARC_START_DEG - pct * self.ARC_SWEEP_DEG)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            x1    = cx + int((r - half) * cos_a)
            y1    = cy - int((r - half) * sin_a)
            x2    = cx + int((r + half) * cos_a)
            y2    = cy - int((r + half) * sin_a)
            pygame.draw.line(surf, color, (x1, y1), (x2, y2), 2)

    # ── Mode indicator ────────────────────────────────────────────────

    def _draw_mode_dots(self, surf: pygame.Surface) -> None:
        """Draw small dots at the bottom showing current mode."""
        n      = len(self.MODES)
        dot_r  = 3
        gap    = 10
        total  = n * (dot_r * 2) + (n - 1) * gap
        start_x = self.rect.w // 2 - total // 2 + dot_r
        y       = self.rect.h - PADDING

        for i in range(n):
            x     = start_x + i * (dot_r * 2 + gap)
            color = SETTINGS.color_accent if i == self._mode_index else SETTINGS.color_border
            pygame.draw.circle(surf, color, (x, y), dot_r)