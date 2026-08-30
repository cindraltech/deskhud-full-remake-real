"""
telemetry/mock_source.py

Background thread that reads system metrics via psutil
and writes them to TelemetryState every 500ms.

"Mock" because it is local system data, not USB data from a gaming PC.
The interface is identical to what a real USB source will use in Milestone 2 —
only this file gets replaced, nothing else changes.

psutil notes for Pi 5:
- cpu_percent(interval=None) is non-blocking (returns value since last call)
- First call always returns 0.0 — we prime it in __init__
- sensors_temperatures() may not be available on all Pi OS builds
- cpu_freq() returns current, min, max — we want current
"""

import logging
import threading
import time
from typing import Optional

from core.settings import SETTINGS
from core.telemetry_state import TelemetryState

log = logging.getLogger(__name__)


class MockSource(threading.Thread):
    """
    Daemon thread that polls psutil and updates TelemetryState.
    Starts immediately on construction. Call stop() for clean shutdown.
    """

    def __init__(self, telemetry: TelemetryState):
        super().__init__(name="MockSource", daemon=True)
        self._telemetry = telemetry
        self._interval  = SETTINGS.telemetry_interval_ms / 1000.0
        self._stop_flag = threading.Event()

        # State for delta calculations
        self._prev_disk_read:  float = 0.0
        self._prev_disk_write: float = 0.0
        self._prev_net_up:     float = 0.0
        self._prev_net_down:   float = 0.0
        self._prev_ts:         float = time.time()

        # Prime psutil CPU measurement — first call always returns 0.0
        try:
            import psutil
            psutil.cpu_percent(interval=None, percpu=True)
        except Exception:
            pass

        log.info(f"MockSource init. Interval: {self._interval*1000:.0f}ms")

    def run(self) -> None:
        log.info("MockSource started.")
        while not self._stop_flag.is_set():
            try:
                data = self._collect()
                self._telemetry.update(data)
            except Exception as exc:
                # Never let a collection error kill the thread
                log.error(f"MockSource collection error: {exc}", exc_info=True)

            self._stop_flag.wait(timeout=self._interval)

        log.info("MockSource stopped.")

    def stop(self) -> None:
        """Signal the thread to exit. Returns immediately."""
        self._stop_flag.set()

    # ── Collection ────────────────────────────────────────────────────

    def _collect(self) -> dict:
        import psutil

        now = time.time()
        dt  = max(now - self._prev_ts, 0.001)
        self._prev_ts = now

        data = {}

        # ── CPU ───────────────────────────────────────────────────────
        try:
            cores = psutil.cpu_percent(interval=None, percpu=True)
            data["cpu_usage"]  = round(sum(cores) / len(cores), 1) if cores else 0.0
            data["cpu_cores"]  = [round(c, 1) for c in cores]
        except Exception as exc:
            log.debug(f"CPU usage error: {exc}")

        try:
            freq = psutil.cpu_freq()
            data["cpu_freq"] = round(freq.current, 0) if freq else 0.0
        except Exception as exc:
            log.debug(f"CPU freq error: {exc}")

        try:
            data["cpu_temp"] = self._get_cpu_temp()
        except Exception as exc:
            log.debug(f"CPU temp error: {exc}")

        # ── RAM ───────────────────────────────────────────────────────
        try:
            mem = psutil.virtual_memory()
            data["ram_total"] = round(mem.total / (1024 ** 3), 1)
            data["ram_used"]  = round(mem.used  / (1024 ** 3), 1)
            data["ram_pct"]   = round(mem.percent, 1)
        except Exception as exc:
            log.debug(f"RAM error: {exc}")

        # ── Disk I/O ──────────────────────────────────────────────────
        try:
            io = psutil.disk_io_counters()
            if io:
                read_rate  = max(0.0, (io.read_bytes  - self._prev_disk_read)  / dt / (1024 ** 2))
                write_rate = max(0.0, (io.write_bytes - self._prev_disk_write) / dt / (1024 ** 2))
                data["disk_read"]  = round(read_rate,  2)
                data["disk_write"] = round(write_rate, 2)
                self._prev_disk_read  = io.read_bytes
                self._prev_disk_write = io.write_bytes
        except Exception as exc:
            log.debug(f"Disk I/O error: {exc}")

        # ── Network I/O ───────────────────────────────────────────────
        try:
            net = psutil.net_io_counters()
            if net:
                up_rate   = max(0.0, (net.bytes_sent - self._prev_net_up)   / dt / (1024 ** 2))
                down_rate = max(0.0, (net.bytes_recv - self._prev_net_down) / dt / (1024 ** 2))
                data["net_up"]   = round(up_rate,   2)
                data["net_down"] = round(down_rate, 2)
                self._prev_net_up   = net.bytes_sent
                self._prev_net_down = net.bytes_recv
        except Exception as exc:
            log.debug(f"Network I/O error: {exc}")

        return data

    # ── Platform helpers ──────────────────────────────────────────────

    def _get_cpu_temp(self) -> float:
        """
        Get CPU temperature. Tries multiple sources in order.
        Returns 0.0 if unavailable on this platform.
        """
        import psutil

        # psutil sensors (works on Pi with thermal zone enabled)
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Pi thermal zone
                for key in ("cpu_thermal", "coretemp", "k10temp", "zenpower"):
                    if key in temps and temps[key]:
                        return round(temps[key][0].current, 1)
                # Fallback: first available sensor
                for entries in temps.values():
                    if entries:
                        return round(entries[0].current, 1)
        except AttributeError:
            # sensors_temperatures() not available on this platform
            pass

        # Pi-specific: read directly from thermal zone
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except (OSError, ValueError):
            pass

        return 0.0