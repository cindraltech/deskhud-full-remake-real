"""
core/settings.py

All display and theme constants for Milestone 1.
Edit this file directly to change values during development.
No file I/O, no validation, no dot-notation — just values.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # ── Display ───────────────────────────────────────────────────────
    width:      int   = 1280
    height:     int   = 800
    fps:        int   = 60
    fullscreen: bool  = True
    title:      str   = "DeskHUD"

    # ── Theme colours (RGB tuples) ────────────────────────────────────
    color_bg:       tuple = (10,  10,  14)
    color_panel:    tuple = (20,  22,  30)
    color_border:   tuple = (35,  38,  50)
    color_accent:   tuple = (0,   200, 255)
    color_text:     tuple = (220, 220, 230)
    color_subtext:  tuple = (100, 110, 130)
    color_ok:       tuple = (50,  220, 120)
    color_warn:     tuple = (255, 160, 0)
    color_crit:     tuple = (255, 50,  50)

    # ── Typography ────────────────────────────────────────────────────
    font_family:    str   = "monospace"

    # ── Telemetry ─────────────────────────────────────────────────────
    telemetry_interval_ms: int = 500   # how often mock source updates


# Single shared instance imported everywhere
SETTINGS = Settings()