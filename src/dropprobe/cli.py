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

    # m2+: probe each drop. For m1, probe_drop() returns NOT_PROBED so we stay
    # in the list view unless the user passed --json (m3 surfaces the static
    # cards even before the live probe lands).
    cards = None
    if not list_only:
        db = load_config_db()
        cards = [build_probe_card(d, hw, db, probe_drop(d, hw, db)) for d in drops]
        # If every probe is NOT_PROBED, we're on m1 — show the list view and
        # a one-line note rather than an empty ProbeCard table.
        if all(c.smoke_probe_ok is None and c.runnable is not None for c in cards) or (
            cards and all(_is_not_probed(c) for c in cards)
        ):
            list_only = True
            typer.echo(
                "  (smoke-probe lands in m2 — showing drops + hardware for now)", err=True
            )

    if list_only:
        cards = None
    print_report(drops, hw, cards, as_json=as_json)


def _is_not_probed(card) -> bool:
    # A card is "not probed" when its smoke_probe_ok is None AND it came from
    # the NOT_PROBED path (runnable is the static VRAM-fit best-guess).
    return card.smoke_probe_ok is None


def main() -> None:
    """Console-script entry point."""

    app()


if __name__ == "__main__":
    main()
