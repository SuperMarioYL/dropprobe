"""DropProbe CLI.

Single entry point: ``dropprobe latest``. m1 ships ``--list`` (fetch this
week's drops + detect local hardware, no probing). ``dropprobe latest``
without ``--list`` will, in m2, run the smoke-probes; for m1 it prints the
same list view with a one-line "probing lands in m2" note so the happy path
is demonstrable today. ``--json`` (m3) exports the full ProbeCard report.
"""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from . import __version__
from .config_db import load_config_db
from .drops import fetch_weekly_drops
from .hardware import detect_hardware
from .probe import build_probe_card, probe_drop
from .report import print_report

app = typer.Typer(
    name="dropprobe",
    help="One-command smoke-probe for the weekly open-weight carousel.",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dropprobe {__version__}")
        raise typer.Exit


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """DropProbe — smoke-probe each weekly open-weight drop against your hardware."""


@app.command()
def latest(
    list_only: bool = typer.Option(
        False, "--list", help="Only list this week's drops + your hardware (m1). Skip probing.",
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Export the full report as JSON (m3).",
    ),
    window: int = typer.Option(
        7, "--window", "-w", min=1, max=90, help="Trailing window in days (carousel cadence).",
    ),
    cache_dir: str = typer.Option(
        "", "--cache-dir", help="Model cache dir (used to measure free disk).",
    ),
) -> None:
    """Fetch this week's drops, detect your hardware, and (m2+) smoke-probe each.

    m1: ``dropprobe latest --list`` shows the carousel + your box.
    m2: ``dropprobe latest`` adds the 30s smoke-probe per drop.
    m3: ``dropprobe latest --json`` exports the full ProbeCard report.
    """

    now = datetime.now(UTC)
    typer.echo(f"DropProbe {__version__} — fetching the last {window}d of drops...", err=True)
    drops = fetch_weekly_drops(window_days=window, now=now)
    hw = detect_hardware(cache_dir=cache_dir)

    # m2+: probe each drop. Until then probe_drop() returns NOT_PROBED, so the
    # cards carry the static config only. --json (m3) surfaces those static
    # cards even before the live probe lands; plain human runs fall back to
    # the list view below while every probe is NOT_PROBED.
    cards = None
    if not list_only:
        db = load_config_db()
        cards = [build_probe_card(d, hw, db, probe_drop(d, hw, db)) for d in drops]
        if (
            not as_json
            and cards
            and all(_is_not_probed(c) for c in cards)
        ):
            # m1: no live probe yet — a human gets drops + hardware rather
            # than an all-"?" ProbeCard table.
            list_only = True
            typer.echo(
                "  (smoke-probe lands in m2 — showing drops + hardware for now)", err=True
            )

    if list_only:
        cards = None
    print_report(drops, hw, cards, as_json=as_json)


def _is_not_probed(card) -> bool:
    # A card is "not probed" when no live smoke-probe ran for it
    # (smoke_probe_ok is None); runnable may still hold a static VRAM-fit
    # best-guess, so it is not part of this predicate.
    return card.smoke_probe_ok is None


def main() -> None:
    """Console-script entry point."""

    app()


if __name__ == "__main__":
    main()
