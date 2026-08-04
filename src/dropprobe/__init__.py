"""DropProbe — one-command smoke-probe for the weekly open-weight carousel.

DropProbe fetches each week's open-weight model drops (DeepSeek, Kimi, GLM,
Qwen, MiniMax), detects the local hardware, and (in later milestones)
smoke-probes each drop via a 30-second capped test inference through
llama.cpp/Ollama. It prints a ProbeCard table showing which fork/quant/config
actually runs on your box.

This package is intentionally import-light: importing ``dropprobe`` must not
require llama.cpp/Ollama to be present, so the probe layer degrades to a stub
when the backends are absent.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .drops import Drop, fetch_weekly_drops
from .hardware import HardwareProfile, detect_hardware
from .probe import ProbeResult, ProbeStatus
from .report import print_drops, print_hardware, print_report

__all__ = [
    "__version__",
    "Drop",
    "fetch_weekly_drops",
    "HardwareProfile",
    "detect_hardware",
    "ProbeResult",
    "ProbeStatus",
    "print_drops",
    "print_hardware",
    "print_report",
]
