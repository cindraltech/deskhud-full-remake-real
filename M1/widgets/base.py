"""
widgets/base.py

Abstract base class for all DeskHUD widgets.

Every widget:
- Gets its own pygame.Surface (allocated once in __init__)
- Reads from TelemetryState in draw()
- Calls begin_frame() to clear and draw the panel background
- Calls commit_frame() to blit itself to the main screen
- Can override on_touch(x, y) for interactivity

Nothing in this file knows about specific metrics or layout.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

import pygame

from core.settings import SETTINGS
from core.telemetry_state import TelemetryState

PADDING = 12  # standard inner padding used by all widgets


class BaseWidget(ABC):

    def __init__(
        self,
        rect:      pygame.Rect,
        config:    dict,
        telemetry: TelemetryState,
    ):
        self.rect      = rect
        self.config    = config
        self.telemetry = telemetry

        # Allocated once — reused every frame
        self._surface = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)

        # Font cache — keyed by size, never re-created after first use
        self._font_cache: dict[int, pygame.font.Font] = {}

    # ── Interface ─────────────────────────────────────────────────────

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        """
        Render this widget to screen.
        Must call begin_frame() at the start and commit_frame(screen) at the end.
        Reads from self.telemetry. Never allocates surfaces or fonts.
        """
        pass

    def update(self) -> None:
        """
        Called once per frame before draw().
        Override for animations or pre-draw state changes.
        Default: no-op.
        """
        pass

    def on_touch(self, x: int, y: int, gesture: str = "tap") -> None:
        """
        Called when a gesture lands within this widget's rect.
        x and y are in screen coordinates.
        Override in interactive widgets. Default: no-op.
        """
        pass

    # ── Frame helpers ─────────────────────────────────────────────────

    def begin_frame(self) -> pygame.Surface:
        """
        Clear the widget surface and draw the standard panel background.
        Call at the start of draw(). Returns the surface to draw onto.
        """
        self._surface.fill((0, 0, 0, 0))

        # Panel background
        pygame.draw.rect(
            self._surface,
            SETTINGS.color_panel,
            pygame.Rect(0, 0, self.rect.w, self.rect.h),
            border_radius=8,
        )

        # Panel border
        pygame.draw.rect(
            self._surface,
            SETTINGS.color_border,
            pygame.Rect(0, 0, self.rect.w, self.rect.h),
            width=1,
            border_radius=8,
        )

        return self._surface

    def commit_frame(self, screen: pygame.Surface) -> None:
        """Blit the widget surface to the main screen. Call at the end of draw()."""
        screen.blit(self._surface, (self.rect.x, self.rect.y))

    # ── Text rendering ────────────────────────────────────────────────

    def draw_text(
        self,
        surface: pygame.Surface,
        text:    str,
        x:       int,
        y:       int,
        size:    int            = 16,
        color:   tuple | None   = None,
        anchor:  str            = "topleft",
    ) -> None:
        """
        Render text at (x, y) with the given anchor point.
        anchor accepts any pygame Rect attribute name:
          'topleft', 'center', 'midtop', 'midbottom', 'topright', etc.
        """
        color = color or SETTINGS.color_text
        font  = self._get_font(size)
        surf  = font.render(str(text), True, color)
        rect  = surf.get_rect(**{anchor: (x, y)})
        surface.blit(surf, rect)

    def _get_font(self, size: int) -> pygame.font.Font:
        """Return a cached font at the given size. Creates it on first use."""
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.SysFont(
                SETTINGS.font_family, size
            )
        return self._font_cache[size]

    # ── Colour helpers ────────────────────────────────────────────────

    def value_color(self, pct: float) -> tuple:
        """Return ok/warn/crit color based on a percentage 0–100."""
        if pct >= 90:
            return SETTINGS.color_crit
        if pct >= 70:
            return SETTINGS.color_warn
        return SETTINGS.color_ok

    def temp_color(self, temp_c: float) -> tuple:
        """Return ok/warn/crit color based on temperature in °C."""
        if temp_c >= 90:
            return SETTINGS.color_crit
        if temp_c >= 75:
            return SETTINGS.color_warn
        return SETTINGS.color_ok