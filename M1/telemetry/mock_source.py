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

GPU notes:
- Uses nvidia-smi via subprocess (no third-party GPU library needed)
- If nvidia-smi isn't available (e.g. on Raspberry Pi), all gpu_* keys
  stay at 0.0 and gpu_available stays False — no crash, no retry spam
- GPU collection is isolated in _collect_gpu() for easy replacement on Pi
"""

import logging
import threading
import time

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

        # nvidia-smi availability — checked once at startup, never retried.
        # Keeps GPU collection isolated and avoids subprocess overhead each frame.
        self._gpu_available: bool = self._check_nvidia_smi()

        # Prime psutil CPU measurement — first call always returns 0.0
        try:
            import psutil
            psutil.cpu_percent(interval=None, percpu=True)
        except Exception:
            pass

        log.info(f"MockSource init. Interval: {self._interval*1000:.0f}ms")
        log.info(f"GPU collection: {'nvidia-smi (NVIDIA)' if self._gpu_available else 'unavailable'}")

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

        # ── GPU — isolated, optional ──────────────────────────────────
        data.update(self._collect_gpu())

        # ── Ping ──────────────────────────────────────────────────────
        data.update(self._collect_ping())

        return data

    # ── GPU collection (isolated for Pi replacement) ──────────────────

    @staticmethod
    def _check_nvidia_smi() -> bool:
        """
        Check once at startup whether nvidia-smi is available and returns
        a valid GPU. Returns True only if both conditions are met.

        FileNotFoundError  → nvidia-smi not installed (Pi, AMD machine, etc.)
        Non-zero exit code → nvidia-smi present but no NVIDIA GPU found
        Any other error    → logged as warning, treated as unavailable
        """
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0 and result.stdout.strip():
                log.info(f"NVIDIA GPU detected via nvidia-smi: {result.stdout.strip()}")
                return True
            log.info("nvidia-smi ran but returned no GPU. GPU data will show 0.")
            return False
        except FileNotFoundError:
            log.info("nvidia-smi not found. GPU widget will show unavailable.")
            return False
        except Exception as exc:
            log.warning(f"GPU detection failed: {exc}. GPU data will show 0.")
            return False

    def _collect_gpu(self) -> dict:
        """
        Collect GPU metrics via nvidia-smi subprocess call.

        Queries utilization, temperature, VRAM used/total, and GPU name
        in a single nvidia-smi call to minimise subprocess overhead.

        Returns a dict with all gpu_* keys. If nvidia-smi is unavailable
        or any error occurs, returns safe zero/False values — never raises.

        This method is intentionally isolated so it can be swapped out
        for a Pi-compatible implementation (e.g. vcgencmd) without
        touching anything else in the codebase.
        """
        _ZERO = {
            "gpu_available": False,
            "gpu_usage":     0.0,
            "gpu_temp":      0.0,
            "gpu_mem_used":  0.0,
            "gpu_mem_total": 0.0,
            "gpu_power":     0.0,
            "gpu_name":      "",
        }

        if not self._gpu_available:
            return _ZERO

        try:
            import subprocess
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total,name",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5.0,
            )

            if result.returncode != 0:
                log.debug(f"nvidia-smi non-zero exit: {result.stderr.strip()}")
                return _ZERO

            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) < 5:
                log.debug(f"nvidia-smi unexpected output: {result.stdout.strip()}")
                return _ZERO

            return {
                "gpu_available": True,
                "gpu_usage":     round(float(parts[0]), 1),  # %
                "gpu_temp":      round(float(parts[1]), 1),  # °C
                "gpu_mem_used":  round(float(parts[2]), 0),  # MB
                "gpu_mem_total": round(float(parts[3]), 0),  # MB
                "gpu_power":     0.0,                        # reserved
                "gpu_name":      parts[4],
            }

        except Exception as exc:
            # Transient error (driver hiccup etc.) — return zeros,
            # keep _gpu_available True so we retry next cycle.
            log.debug(f"GPU collection error: {exc}")
            return _ZERO

    # ── Ping collection ───────────────────────────────────────────────

    @staticmethod
    def _collect_ping() -> dict:
        """
        Measure round-trip ping to 8.8.8.8 using the system ping command.
        Works on both Windows and Linux/Pi without any extra dependencies.

        Non-blocking concern: ping takes ~10-50ms. Acceptable here because
        this runs in a background thread on a 500ms interval.
        """
        try:
            import subprocess
            import platform
            import re

            host = "8.8.8.8"

            if platform.system() == "Windows":
                cmd = ["ping", "-n", "1", "-w", "1000", host]
            else:
                cmd = ["ping", "-c", "1", "-W", "1", host]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3.0,
            )

            match = re.search(r"[Tt]ime[=<]([\d.]+)\s*ms", result.stdout)
            if match:
                return {"net_ping": round(float(match.group(1)), 1)}

        except Exception as exc:
            log.debug(f"Ping error: {exc}")

        return {"net_ping": 0.0}

    # ── Platform helpers ──────────────────────────────────────────────

    def _get_cpu_temp(self) -> float:
        """
        Get CPU temperature. Tries multiple sources in order.
        Returns 0.0 if unavailable on this platform.

        sensors_temperatures() is Linux/macOS only. The hasattr guard
        satisfies Pylance's static analysis on Windows while still calling
        the function on Pi where it exists.
        """
        import psutil

        # psutil sensors — Linux/macOS only, guarded for Windows/Pylance
        if hasattr(psutil, "sensors_temperatures"):
            try:
                temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
                if temps:
                    for key in ("cpu_thermal", "coretemp", "k10temp", "zenpower"):
                        if key in temps and temps[key]:
                            return round(temps[key][0].current, 1)
                    # Fallback: first available sensor
                    for entries in temps.values():
                        if entries:
                            return round(entries[0].current, 1)
            except Exception:
                pass

        # Pi-specific: read directly from thermal zone sysfs
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except (OSError, ValueError):
            pass

        return 0.0