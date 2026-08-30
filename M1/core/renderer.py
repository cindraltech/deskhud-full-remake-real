"""
core/renderer.py

Owns the pygame display and drives the render loop.

Responsibilities:
- Initialise pygame and open the window
- Run the 60Hz loop
- Clear the screen each frame
- Call widget_engine.render()
- Process pygame events and route touch to widget_engine.handle_touch()
- Flip the display buffer
- Log frame time warnings when FPS drops below target
- Clean shutdown on quit

Nothing else. No widget logic, no telemetry, no config parsing.
"""

import logging
import time

import pygame

from core.settings import SETTINGS

log = logging.getLogger(__name__)

# Pygame user event IDs for gesture input
EVENT_GESTURE = pygame.USEREVENT + 1


class Renderer:
    def __init__(self, widget_engine, touch_handler):
        self._engine        = widget_engine
        self._touch         = touch_handler
        self._screen        = None
        self._clock         = None
        self._running       = False

        # Frame timing for performance logging
        self._frame_warn_threshold = 1.0 / (SETTINGS.fps * 0.8)  # warn if >25% over budget

    # ── Lifecycle ─────────────────────────────────────────────────────

    def init(self) -> None:
        """
        Initialise pygame and open the display.
        Must be called before run().
        Raises RuntimeError if display cannot be opened.
        """
        pygame.init()
        pygame.mouse.set_visible(False)

        flags = 0
        if SETTINGS.fullscreen:
            flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF

        try:
            self._screen = pygame.display.set_mode(
                (SETTINGS.width, SETTINGS.height), flags
            )
        except Exception as exc:
            # Fullscreen failed — fall back to windowed (common on desktop dev)
            log.warning(
                f"Fullscreen failed ({exc}). Falling back to windowed mode."
            )
            self._screen = pygame.display.set_mode(
                (SETTINGS.width, SETTINGS.height)
            )

        pygame.display.set_caption(SETTINGS.title)
        self._clock = pygame.time.Clock()

        log.info(
            f"Display opened: {SETTINGS.width}x{SETTINGS.height} "
            f"@ {SETTINGS.fps}fps "
            f"({'fullscreen' if SETTINGS.fullscreen else 'windowed'})"
        )

    def run(self) -> None:
        """
        Main render loop. Blocks until quit.
        Call init() first.
        """
        if self._screen is None:
            raise RuntimeError("Renderer.init() must be called before run().")

        self._running = True
        log.info("Render loop started.")

        while self._running:
            frame_start = time.perf_counter()

            # ── 1. Process events ─────────────────────────────────────
            for event in pygame.event.get():
                self._handle_event(event)

            # ── 2. Process touch input ────────────────────────────────
            # Touch handler posts its own pygame events, but we also
            # let it do per-frame processing here if needed
            self._touch.process()

            # ── 3. Clear screen ───────────────────────────────────────
            self._screen.fill(SETTINGS.color_bg)

            # ── 4. Render widgets ─────────────────────────────────────
            self._engine.render(self._screen)

            # ── 5. Flip buffers ───────────────────────────────────────
            pygame.display.flip()

            # ── 6. Cap frame rate ─────────────────────────────────────
            self._clock.tick(SETTINGS.fps)

            # ── 7. Log frame time warnings ────────────────────────────
            frame_time = time.perf_counter() - frame_start
            if frame_time > self._frame_warn_threshold:
                log.debug(
                    f"Frame over budget: {frame_time*1000:.1f}ms "
                    f"(budget {1000/SETTINGS.fps:.1f}ms)"
                )

        log.info("Render loop exited.")
        self._cleanup()

    def stop(self) -> None:
        """Signal the render loop to exit on the next frame."""
        self._running = False

    # ── Event handling ────────────────────────────────────────────────

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self._running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._running = False

        elif event.type == EVENT_GESTURE:
            # Touch handler posted a gesture — dispatch to widget engine
            self._engine.handle_touch(
                event.dict.get("x", 0),
                event.dict.get("y", 0),
                event.dict.get("gesture", "tap"),
            )

        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Desktop testing fallback — mouse click acts as tap
            x, y = event.pos
            self._engine.handle_touch(x, y, "tap")

    # ── Cleanup ───────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        pygame.quit()
        log.info("pygame shut down.")

    # ── Debug info ────────────────────────────────────────────────────

    @property
    def actual_fps(self) -> float:
        """Current measured FPS. Safe to call during the loop."""
        if self._clock:
            return self._clock.get_fps()
        return 0.0