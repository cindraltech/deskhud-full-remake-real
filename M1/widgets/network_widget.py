"""
widgets/network_widget.py

Network telemetry widget — upload/download speed and ping.

Unlike CPU/RAM/GPU, network throughput has no natural 0–100% ceiling,
so this widget does not use the arc-gauge pattern. Instead it uses a
clean stacked readout: upload rate, download rate, and ping — colour
coded independently.

Displays (default mode):
- Upload speed (MB/s) with an up arrow
- Download speed (MB/s) with a down arrow
- Ping in ms, colour-coded (low = good, high = bad — inverted from
  the usual value_color logic since low ping is desirable)

If ping is 0.0 (collection failed — no internet, DNS blocked, etc.)
the widget shows "No Connection" the same way GpuWidget shows
"Unavailable" when no GPU is detected. This reuses the same visual
language established by GpuWidget rather than inventing a new one.

Tap to cycle display mode:
  combined → up + down + ping together (default)
  speed    → large up/down only
  ping     → large ping only
"""

import pygame

from core.settings import SETTINGS
from core.telemetry_state import TelemetryState
from widgets.base import BaseWidget, PADDING


# Ping thresholds — low is good, high is bad (inverted vs value_color)
PING_WARN_MS = 80.0
PING_CRIT_MS = 150.0


class NetworkWidget(BaseWidget):

    MODES = ("combined", "speed", "ping")

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

        up   = self.telemetry.get("net_up",   0.0)
        down = self.telemetry.get("net_down", 0.0)
        ping = self.telemetry.get("net_ping", 0.0)

        # Ping of exactly 0.0 means the last ping attempt failed —
        # collection code returns 0.0 on any error/timeout as its
        # "no data" sentinel (see mock_source._collect_ping).
        connected = ping > 0.0

        if not connected:
            self._draw_no_connection(surf, up, down)
            self.commit_frame(screen)
            return

        if self._mode == "combined":
            self._draw_combined(surf, up, down, ping)
        elif self._mode == "speed":
            self._draw_speed(surf, up, down)
        elif self._mode == "ping":
            self._draw_ping(surf, ping)

        self._draw_mode_dots(surf)

        self.commit_frame(screen)

    # ── Combined mode (default) ────────────────────────────────────────

    def _draw_combined(self, surf: pygame.Surface, up: float, down: float, ping: float) -> None:
        w, h = self.rect.w, self.rect.h

        self.draw_text(surf, "NETWORK", PADDING, PADDING, 12, SETTINGS.color_subtext)

        row_y   = h // 2 - 20
        row_gap = 34

        self.draw_text(
            surf, f"↑ {up:.2f} MB/s",
            PADDING, row_y, 20, SETTINGS.color_accent, "midleft",
        )
        self.draw_text(
            surf, f"↓ {down:.2f} MB/s",
            PADDING, row_y + row_gap, 20, SETTINGS.color_ok, "midleft",
        )

        ping_color = self._ping_color(ping)
        self.draw_text(
            surf, f"{ping:.0f} ms",
            w - PADDING, h - PADDING, 16, ping_color, "bottomright",
        )
        self.draw_text(
            surf, "ping",
            w - PADDING, h - PADDING - 20, 10, SETTINGS.color_subtext, "bottomright",
        )

    # ── Speed-only mode ────────────────────────────────────────────────

    def _draw_speed(self, surf: pygame.Surface, up: float, down: float) -> None:
        w, h = self.rect.w, self.rect.h
        cx    = w // 2

        self.draw_text(surf, f"↑ {up:.2f}",   cx, h // 2 - 26, 26, SETTINGS.color_accent, "center")
        self.draw_text(surf, f"↓ {down:.2f}", cx, h // 2 + 12, 26, SETTINGS.color_ok,     "center")
        self.draw_text(surf, "MB/s",           cx, h - PADDING, 11, SETTINGS.color_subtext, "midbottom")

    # ── Ping-only mode ─────────────────────────────────────────────────

    def _draw_ping(self, surf: pygame.Surface, ping: float) -> None:
        w, h = self.rect.w, self.rect.h
        cx, cy = w // 2, h // 2
        color = self._ping_color(ping)

        self.draw_text(surf, f"{ping:.0f}", cx, cy - 10, 36, color, "center")
        self.draw_text(surf, "ms ping", cx, cy + 24, 12, SETTINGS.color_subtext, "center")

    # ── No connection fallback ────────────────────────────────────────

    def _draw_no_connection(self, surf: pygame.Surface, up: float, down: float) -> None:
        """
        Shown when ping collection fails (no internet / DNS blocked).
        Up/down are still shown if non-zero, since local network
        traffic (e.g. LAN) can still be active without internet access.
        Mirrors GpuWidget._draw_unavailable's visual language.
        """
        w, h = self.rect.w, self.rect.h
        cx, cy = w // 2, h // 2

        self.draw_text(surf, "NETWORK", cx, cy - 20, 16, SETTINGS.color_subtext, "center")
        self.draw_text(surf, "No Connection", cx, cy, 13, SETTINGS.color_crit, "center")

        if up > 0.0 or down > 0.0:
            self.draw_text(
                surf, f"↑{up:.1f}  ↓{down:.1f} MB/s",
                cx, cy + 24, 11, SETTINGS.color_subtext, "center",
            )

    # ── Colour helper (inverted: low ping = good) ──────────────────────

    @staticmethod
    def _ping_color(ping: float) -> tuple:
        if ping >= PING_CRIT_MS:
            return SETTINGS.color_crit
        if ping >= PING_WARN_MS:
            return SETTINGS.color_warn
        return SETTINGS.color_ok

    # ── Mode indicator (same pattern as CpuWidget/GpuWidget) ───────────

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