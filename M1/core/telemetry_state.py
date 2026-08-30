"""
core/telemetry_state.py

Thread-safe telemetry data store for Milestone 1.

Deliberately minimal:
- One dict, one lock
- update() writes values
- get() reads values
- No callbacks, no history, no alerts, no thresholds

The mock source thread writes to this.
Widgets read from this every frame.
When Milestone 2 adds USB, only the source changes — this file stays identical.
"""

import threading
from typing import Any

# Default values returned when a key has never been written.
# Widgets can always call get() safely without checking for None.
DEFAULTS = {
    "cpu_usage":    0.0,   # %
    "cpu_temp":     0.0,   # °C
    "cpu_freq":     0.0,   # MHz
    "cpu_cores":    [],    # per-core usage list

    "ram_used":     0.0,   # GB
    "ram_total":    0.0,   # GB
    "ram_pct":      0.0,   # %

    "disk_read":    0.0,   # MB/s
    "disk_write":   0.0,   # MB/s

    "net_up":       0.0,   # MB/s
    "net_down":     0.0,   # MB/s
    "net_ping":     0.0,   # ms  ← NEW

    # GPU — populated by GPUtil on NVIDIA, 0.0 otherwise   ← NEW block
    "gpu_usage":    0.0,   # %
    "gpu_temp":     0.0,   # °C
    "gpu_mem_used": 0.0,   # MB
    "gpu_mem_total":0.0,   # MB
    "gpu_power":    0.0,   # W  (not available via GPUtil, reserved)
    "gpu_name":     "",    # e.g. "NVIDIA GeForce RTX 3080"
    "gpu_available":False, # True when a supported GPU was detected
}


class TelemetryState:
    """
    Shared telemetry store. Safe to read from the render thread
    and write from the mock source thread simultaneously.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._data: dict = dict(DEFAULTS)

    def update(self, data: dict) -> None:
        """
        Merge a dict of new values into the store.
        Called by the telemetry source thread.
        """
        with self._lock:
            self._data.update(data)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Read a single value. Returns the key's default if never written,
        or the provided default if the key is unknown entirely.
        """
        with self._lock:
            if key in self._data:
                return self._data[key]
            return DEFAULTS.get(key, default)

    def snapshot(self) -> dict:
        """
        Return a shallow copy of the full state.
        Useful for widgets that need multiple keys atomically.
        """
        with self._lock:
            return dict(self._data)