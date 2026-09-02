"""
widgets/gpu_widget.py

GPU usage widget — circular arc gauge.

Displays:
- Circular arc showing GPU utilisation % (colour-coded ok/warn/crit)
- Usage percentage in the centre
- Temperature below the percentage
- VRAM used/total at the bottom (small)

If no NVIDIA GPU was detected (gpu_available is False), shows a clean
"GPU Unavailable" message instead of a zeroed-out gauge — this makes
it visually obvious the widget is working correctly, just has no data
source, rather than looking broken.

Tap to cycle display mode:
  usage  → shows usage % (default)
  temp   → shows temperature °C prominently
  vram   → shows VRAM used/total prominently

Mirrors the CPU widget's arc rendering approach exactly, so both
gauges look and behave consistently.
"""

import math

import pygame

from core.settings import SETTINGS
from core.telemetry_state import TelemetryState
from widgets.base import BaseWidget, PADDING


class GpuWidget(BaseWidget):

    MODES = ("usage", "temp", "vram")

    # Arc geometry — identical to CpuWidget for visual consistency
    ARC_START_DEG = 150
    ARC_SWEEP_DEG = 240
    ARC_WIDTH     = 10

    def __init__(self, rect: pygame.Rect, config: dict, telemetry: TelemetryState):
        super().__init__(rect, config, telemetry)
        self._mode_index = 0

    @property
    def _mode(self) -> str:
        return self.MODES[self._mode_index]

    def on_touch(self, x: int, y: int, gesture: str = "tap") -> None:
        """Cycle through display modes on tap. No-op if GPU unavailable."""
        if self.telemetry.get("gpu_available", False):
            self._mode_index = (self._mode_index + 1) % len(self.MODES)

    def draw(self, screen: pygame.Surface) -> None:
        surf = self.begin_frame()

        available = self.telemetry.get("gpu_available", False)

        if not available:
            self._draw_unavailable(surf)
            self.commit_frame(screen)
            return

        cx = self.rect.w // 2
        cy = self.rect.h // 2
        r  = min(cx, cy) - PADDING - self.ARC_WIDTH

        usage      = self.telemetry.get("gpu_usage",     0.0)
        temp       = self.telemetry.get("gpu_temp",      0.0)
        mem_used   = self.telemetry.get("gpu_mem_used",  0.0)
        mem_total  = self.telemetry.get("gpu_mem_total", 0.0)

        usage_color = self.value_color(usage)
        temp_color  = self.temp_color(temp)

        # Track arc (background)
        self._draw_arc(surf, cx, cy, r, 0, 100, SETTINGS.color_border)

        # Value arc
        self._draw_arc(surf, cx, cy, r, 0, usage, usage_color)

        # Centre content depends on mode
        if self._mode == "usage":
            self.draw_text(surf, f"{usage:.0f}%",  cx, cy - 18, 30, usage_color, "center")
            self.draw_text(surf, "GPU",             cx, cy + 12, 12, SETTINGS.color_subtext, "center")
            if temp > 0:
                self.draw_text(surf, f"{temp:.0f}°C", cx, cy + 30, 11, temp_color, "center")

        elif self._mode == "temp":
            self.draw_text(surf, f"{temp:.0f}°",   cx, cy - 18, 30, temp_color, "center")
            self.draw_text(surf, "TEMP",            cx, cy + 12, 12, SETTINGS.color_subtext, "center")
            self.draw_text(surf, f"{usage:.0f}%",  cx, cy + 30, 11, usage_color, "center")

        elif self._mode == "vram":
            gb_used  = mem_used  / 1024
            gb_total = mem_total / 1024
            self.draw_text(surf, f"{gb_used:.1f}", cx, cy - 18, 28, SETTINGS.color_accent, "center")
            self.draw_text(surf, f"of {gb_total:.0f} GB", cx, cy + 10, 11, SETTINGS.color_subtext, "center")
            self.draw_text(surf, f"{usage:.0f}%",  cx, cy + 30, 11, usage_color, "center")

        self._draw_mode_dots(surf)

        self.commit_frame(screen)

    # ── Unavailable state ─────────────────────────────────────────────

    def _draw_unavailable(self, surf: pygame.Surface) -> None:
        """
        Clean fallback shown when no NVIDIA GPU was detected
        (nvidia-smi missing, no GPU found, or running on Raspberry Pi).
        """
        cx = self.rect.w // 2
        cy = self.rect.h // 2
        r  = min(cx, cy) - PADDING - self.ARC_WIDTH

        # Empty track arc for visual consistency with the active state
        self._draw_arc(surf, cx, cy, r, 0, 100, SETTINGS.color_border)

        self.draw_text(surf, "GPU",   cx, cy - 12, 16, SETTINGS.color_subtext, "center")
        self.draw_text(surf, "Unavailable", cx, cy + 10, 12, SETTINGS.color_subtext, "center")

    # ── Arc drawing (identical pattern to CpuWidget) ───────────────────

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