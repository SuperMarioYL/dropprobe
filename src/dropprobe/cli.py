"""DropProbe CLI.

Single entry point: ``dropprobe latest``. ``--list`` shows this week's drops
+ local hardware without assembling ProbeCards; plain ``latest`` assembles
the static ProbeCards, and while no live probe has run (probe_drop still
returns NOT_PROBED) a human run falls back to the same list view with a
one-line "no probe ran" note. ``--json`` exports the full report.
"""

from __future__ import annotations

from datetime import UTC, datetime

import typer

from . import __version__
from .config_db import load_config_db
from .drops import fetch_carousel
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
        False, "--list", help="Only list this week's drops + your hardware. Skip probing.",
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Export the full report as JSON.",
    ),
    window: int = typer.Option(
        7, "--window", "-w", min=1, max=90, help="Trailing window in days (carousel cadence).",
    ),
    cache_dir: str = typer.Option(
        "", "--cache-dir", help="Model cache dir (used to measure free disk).",
    ),
) -> None:
    """Fetch this week's drops, detect your hardware, and assemble each drop's config.

    --list shows the carousel + your box without assembling ProbeCards.
    --json exports the full report (drops, hardware, ProbeCards) as JSON.
    """

    now = datetime.now(UTC)
    typer.echo(f"DropProbe {__version__} — fetching the last {window}d of drops...", err=True)
    fetch = fetch_carousel(window_days=window, now=now)
    drops = fetch.drops
    if fetch.all_orgs_failed:
        typer.echo(
            f"  warning: all {fetch.orgs_queried} Hugging Face Hub queries failed — "
            "the empty drop list may be a network problem",
            err=True,
        )
    hw = detect_hardware(cache_dir=cache_dir)

    # probe_drop() still returns NOT_PROBED, so the cards carry the static
    # config only. --json surfaces those static cards even before the live
    # probe lands; plain human runs fall back to the list view below while
    # every probe is NOT_PROBED.
    cards = None
    if not list_only:
        db = load_config_db()
        cards = [build_probe_card(d, hw, db, probe_drop(d, hw, db)) for d in drops]
        if (
            not as_json
            and cards
            and all(_is_not_probed(c) for c in cards)
        ):
            # No live probe ran — a human gets drops + hardware rather than
            # an all-"?" ProbeCard table.
            list_only = True
            typer.echo(
                "  (no probe ran — showing drops + hardware for now)", err=True
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
