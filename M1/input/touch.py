"""
input/touch.py

Touch input handler for Milestone 1.

On Raspberry Pi:
  Reads raw touch events from the Linux evdev subsystem.
  Normalises coordinates to screen pixels.
  Posts pygame USEREVENT events with gesture type and coordinates.

On desktop (no evdev / development machine):
  Transparently falls back to pygame mouse events.
  No code changes needed when moving between environments.

Gesture recognition in Milestone 1:
  tap         — finger down and up with minimal movement
  swipe_left  — fast horizontal movement to the left
  swipe_right — fast horizontal movement to the right

Only tap is wired to widgets in Milestone 1.
Swipe events are posted but not consumed — ready for Milestone 2 profile switching.

The renderer calls process() each frame to inject queued mouse-fallback events.
evdev events are posted from a background thread via pygame.event.post().
"""

import logging
import math
import threading
import time
from typing import Optional

import pygame

from core.settings import SETTINGS

log = logging.getLogger(__name__)

# Gesture thresholds
TAP_MAX_MOVEMENT_PX   = 15     # max pixel movement to count as a tap (not swipe)
SWIPE_MIN_DISTANCE_PX = 60     # minimum distance for a swipe
SWIPE_MAX_DURATION_S  = 0.4    # maximum time for a swipe gesture

# pygame event type ID
EVENT_GESTURE = pygame.USEREVENT + 1

# evdev device name hints for auto-detection
TOUCH_DEVICE_HINTS = ["touch", "touchscreen", "ft5", "goodix", "edt", "capacitive"]


def post_gesture(gesture: str, x: int, y: int) -> None:
    """Post a gesture event into the pygame event queue."""
    pygame.event.post(
        pygame.event.Event(
            EVENT_GESTURE,
            {"gesture": gesture, "x": x, "y": y},
        )
    )


class TouchHandler:
    """
    Manages touch input. Call start() once before the render loop.
    Call process() each frame (handles mouse fallback).
    """

    def __init__(self):
        self._evdev_thread: Optional[threading.Thread] = None
        self._evdev_available = False
        self._device_path: Optional[str] = None

        # Touch state for gesture recognition
        self._touch_start_x:  Optional[int]   = None
        self._touch_start_y:  Optional[int]   = None
        self._touch_start_ts: Optional[float] = None
        self._touch_active    = False

        # Screen dimensions for coordinate normalisation
        self._screen_w = SETTINGS.width
        self._screen_h = SETTINGS.height

    def start(self) -> None:
        """
        Attempt to start evdev touch reading.
        Falls back silently to mouse mode if evdev is unavailable.
        """
        device = self._detect_evdev_device()
        if device:
            self._device_path    = device
            self._evdev_available = True
            self._evdev_thread = threading.Thread(
                target=self._evdev_loop,
                name="TouchHandler",
                daemon=True,
            )
            self._evdev_thread.start()
            log.info(f"Touch: evdev mode on {device}")
        else:
            log.info("Touch: mouse fallback mode (no evdev device found).")

    def process(self) -> None:
        """
        Called every frame by the renderer.
        Handles mouse-based touch fallback for desktop testing.
        evdev mode posts events from its own thread — no work needed here.
        """
        if self._evdev_available:
            return  # evdev thread handles everything

        # Mouse fallback — treat clicks as taps
        # pygame.MOUSEBUTTONDOWN events are handled directly in the renderer
        # so nothing extra needed here. This method is a hook for future use.

    # ── evdev device detection ────────────────────────────────────────

    def _detect_evdev_device(self) -> Optional[str]:
        try:
            import evdev  # type: ignore
            devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
            for dev in devices:
                name_lower = dev.name.lower()
                if any(hint in name_lower for hint in TOUCH_DEVICE_HINTS):
                    return dev.path
            log.debug("evdev available but no touch device found by name hint.")
        except ImportError:
            log.debug("evdev not installed.")
        except Exception as exc:
            log.debug(f"evdev detection error: {exc}")
        return None

    # ── evdev read loop ───────────────────────────────────────────────

    def _evdev_loop(self) -> None:
        """Background thread: read evdev events, post pygame gestures."""
        import evdev  # type: ignore
        from evdev import ecodes

        while True:
            try:
                device     = evdev.InputDevice(self._device_path)
                abs_info_x = device.absinfo(ecodes.ABS_MT_POSITION_X)
                abs_info_y = device.absinfo(ecodes.ABS_MT_POSITION_Y)
                log.debug(f"evdev device opened: {device.name}")

                x_raw = 0
                y_raw = 0

                for event in device.read_loop():
                    if event.type == ecodes.EV_ABS:
                        if event.code in (ecodes.ABS_MT_POSITION_X, ecodes.ABS_X):
                            x_raw = event.value
                        elif event.code in (ecodes.ABS_MT_POSITION_Y, ecodes.ABS_Y):
                            y_raw = event.value

                    elif event.type == ecodes.EV_KEY:
                        if event.code == ecodes.BTN_TOUCH:
                            sx, sy = self._normalise(x_raw, y_raw, abs_info_x, abs_info_y)
                            if event.value == 1:
                                self._on_finger_down(sx, sy)
                            else:
                                self._on_finger_up(sx, sy)

            except Exception as exc:
                log.warning(f"evdev loop error: {exc}. Retrying in 2s...")
                time.sleep(2.0)

    # ── Gesture recognition ───────────────────────────────────────────

    def _on_finger_down(self, x: int, y: int) -> None:
        self._touch_active    = True
        self._touch_start_x   = x
        self._touch_start_y   = y
        self._touch_start_ts  = time.time()

    def _on_finger_up(self, x: int, y: int) -> None:
        if not self._touch_active:
            return

        self._touch_active = False

        if (
            self._touch_start_x is None
            or self._touch_start_y is None
            or self._touch_start_ts is None
        ):
            return

        dx       = x - self._touch_start_x
        dy       = y - self._touch_start_y
        distance = math.sqrt(dx * dx + dy * dy)
        duration = time.time() - self._touch_start_ts

        if distance < TAP_MAX_MOVEMENT_PX:
            post_gesture("tap", self._touch_start_x, self._touch_start_y)

        elif distance >= SWIPE_MIN_DISTANCE_PX and duration <= SWIPE_MAX_DURATION_S:
            if abs(dx) >= abs(dy):
                gesture = "swipe_right" if dx > 0 else "swipe_left"
            else:
                gesture = "swipe_down" if dy > 0 else "swipe_up"
            post_gesture(gesture, self._touch_start_x, self._touch_start_y)

        # Reset
        self._touch_start_x  = None
        self._touch_start_y  = None
        self._touch_start_ts = None

    # ── Coordinate normalisation ──────────────────────────────────────

    def _normalise(self, x_raw: int, y_raw: int, abs_x, abs_y) -> tuple[int, int]:
        """Map raw evdev coordinates to screen pixel coordinates."""
        try:
            x_range = max(abs_x.max - abs_x.min, 1)
            y_range = max(abs_y.max - abs_y.min, 1)
            x = int((x_raw - abs_x.min) / x_range * self._screen_w)
            y = int((y_raw - abs_y.min) / y_range * self._screen_h)
            x = max(0, min(self._screen_w - 1, x))
            y = max(0, min(self._screen_h - 1, y))
            return x, y
        except Exception:
            return x_raw, y_raw