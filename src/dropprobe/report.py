"""ProbeCard report rendering.

m1 renders two rich tables — the week's drops + the local hardware profile
— which is everything ``dropprobe latest --list`` shows. m3 extends
:func:`print_report` to the full ProbeCard table (model / best-fit quant /
VRAM fits / fork / tooling-readiness / run command) and a ``--json`` export.

The rich dependency is soft: if ``rich`` is absent we fall back to a plain
ASCII table so the tool never hard-fails on a minimal box. The m1 happy path
on a clean install *will* have rich (it's in ``key_deps``), but the fallback
keeps the tool usable mid-upgrade.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Sequence
from typing import Any, TextIO

from .drops import Drop
from .hardware import HardwareProfile
from .probe import ProbeCard

try:
    from rich.console import Console
    from rich.table import Table

    _HAS_RICH = True
except ImportError:  # pragma: no cover - rich is a hard dep in pyproject
    _HAS_RICH = False

__all__ = ["print_drops", "print_hardware", "print_report", "report_to_json"]


# --- drops table (m1) -------------------------------------------------------
def print_drops(
    drops: Sequence[Drop],
    *,
    file: TextIO | None = None,
) -> None:
    """Print this week's carousel drops.

    m1 surface: one row per drop — model / lab / drop date. Probing columns
    land in m3 via :func:`print_report`.
    """

    if not drops:
        _say(file, "No drops this week (offline, or the carousel was quiet).")
        return
    if _HAS_RICH and file is None:
        console = Console()
        table = Table(title="This week's open-weight drops", show_lines=False)
        table.add_column("Model", style="bold")
        table.add_column("Lab", style="cyan")
        table.add_column("Drop date", style="dim")
        table.add_column("Files", justify="right")
        for d in drops:
            table.add_row(d.model_id, d.lab, _short_date(d.drop_date), str(len(d.files)))
        console.print(table)
        return
    # Plain fallback
    _say(file, "This week's open-weight drops:")
    _say(file, f"  {'MODEL':<40} {'LAB':<10} {'DROP DATE':<12} FILES")
    for d in drops:
        _say(file, f"  {d.model_id:<40} {d.lab:<10} {_short_date(d.drop_date):<12} {len(d.files)}")


# --- hardware table (m1) ----------------------------------------------------
def print_hardware(
    hw: HardwareProfile,
    *,
    file: TextIO | None = None,
) -> None:
    """Print the detected local hardware profile."""

    rows = [
        ("GPU arch", hw.gpu_arch or "cpu"),
        ("GPU", hw.gpu_name or "(none detected — CPU-only rig)"),
        ("GPU count", str(hw.device_count)),
        ("VRAM (GiB)", f"{hw.vram_gb:.1f}" if hw.vram_gb else "0.0"),
        ("RAM (GiB)", f"{hw.ram_gb:.1f}"),
        ("Disk free (GiB)", f"{hw.disk_free_gb:.1f}"),
    ]
    if _HAS_RICH and file is None:
        console = Console()
        table = Table(title="Your hardware", show_lines=False)
        table.add_column("Axis", style="bold")
        table.add_column("Value")
        for k, v in rows:
            table.add_row(k, v)
        console.print(table)
        if hw.is_cpu_only:
            console.print("[dim]CPU-only rig detected — quants will run in system RAM.[/dim]")
        return
    _say(file, "Your hardware:")
    for k, v in rows:
        _say(file, f"  {k:<18} {v}")
    if hw.is_cpu_only:
        _say(file, "  CPU-only rig detected — quants will run in system RAM.")


# --- full report (m1 = drops + hardware; m3 = ProbeCard table + json) ------
def print_report(
    drops: Sequence[Drop],
    hw: HardwareProfile,
    cards: Sequence[ProbeCard] | None = None,
    *,
    as_json: bool = False,
    file: TextIO | None = None,
) -> None:
    """Print the full DropProbe report.

    - ``as_json=False, cards=None`` (m1 ``--list``): drops table + hardware table.
    - ``as_json=False, cards=set`` (m3): the full ProbeCard table.
    - ``as_json=True`` (m3 ``--json``): a JSON document to stdout/file.
    """

    if as_json:
        _emit_json(drops, hw, cards, file)
        return
    if cards:
        _print_probecard_table(cards, file=file)
        return
    print_drops(drops, file=file)
    print_hardware(hw, file=file)


def _print_probecard_table(cards: Sequence[ProbeCard], *, file: TextIO | None) -> None:
    """Render the full ProbeCard table (m3)."""

    if not cards:
        _say(file, "No ProbeCards to show.")
        return
    if _HAS_RICH and file is None:
        console = Console()
        table = Table(title="ProbeCard report", show_lines=True)
        table.add_column("Model", style="bold")
        table.add_column("Quant", style="magenta")
        table.add_column("VRAM fits", justify="center")
        table.add_column("Fork", style="cyan")
        table.add_column("Tooling", justify="center")
        table.add_column("Run command", style="green")
        for c in cards:
            quant = c.quant.name if c.quant else "—"
            fits = _yesno(c.runnable)
            fork = f"{c.backend.fork_repo}@{c.backend.fork_ref}" if c.backend else "—"
            tooling = _tooling_summary(c.tooling)
            table.add_row(c.model_id, quant, fits, fork, tooling, c.run_cmd)
        console.print(table)
        return
    _say(file, "ProbeCard report:")
    for c in cards:
        quant = c.quant.name if c.quant else "—"
        fits = _yesno(c.runnable)
        fork = f"{c.backend.fork_repo}@{c.backend.fork_ref}" if c.backend else "—"
        _say(file, f"  {c.model_id} | {quant} | fits={fits} | {fork}")
        _say(file, f"    run: {c.run_cmd}")


# --- json (m3) --------------------------------------------------------------
def report_to_json(
    drops: Sequence[Drop],
    hw: HardwareProfile,
    cards: Sequence[ProbeCard] | None,
) -> dict[str, Any]:
    """Build the JSON-exportable report dict (m3 ``--json``)."""

    return {
        "drops": [dataclasses.asdict(d) for d in drops],
        "hardware": dataclasses.asdict(hw),
        "probe_cards": [c.to_dict() for c in (cards or [])],
    }


def _emit_json(
    drops: Sequence[Drop],
    hw: HardwareProfile,
    cards: Sequence[ProbeCard] | None,
    file: TextIO | None,
) -> None:
    payload = report_to_json(drops, hw, cards)
    out = file or sys.stdout
    json.dump(payload, out, indent=2, default=str, ensure_ascii=False)
    out.write("\n")


# --- helpers ----------------------------------------------------------------
def _short_date(iso: str) -> str:
    return (iso or "")[:10]


def _yesno(value: bool | None) -> str:
    if value is None:
        return "?"
    return "yes" if value else "no"


def _tooling_summary(t: Any) -> str:
    parts = []
    for axis in ("comfyui", "llama_cpp", "ollama"):
        val = getattr(t, axis, "none")
        mark = {"day-0": "day0", "supported": "ok", "none": "—"}.get(val, val)
        parts.append(f"{axis[:3]}:{mark}")
    return " ".join(parts)


def _say(file: TextIO | None, msg: str) -> None:
    (file or sys.stdout).write(msg + "\n")
