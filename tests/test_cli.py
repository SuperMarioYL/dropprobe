"""Tests for the CLI surface.

The static ProbeCards are assembled from the config DB even though the live
smoke-probe is not wired in; a human run falls back to the list view while
nothing has been probed, and --json exports the cards regardless. The CLI
also distinguishes an unreachable Hub from a quiet carousel, and the version
surfaces stay in lockstep (VERSION file, pyproject, ``__version__``,
``--version`` output, recorded-demo artifacts).

The fetch + hardware layers are monkeypatched so these tests assert the CLI
contract without network access or a real GPU.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

import dropprobe
from dropprobe.cli import app
from dropprobe.drops import CarouselFetch, Drop
from dropprobe.hardware import HardwareProfile
from dropprobe.probe import ProbeResult, ProbeStatus

runner = CliRunner()

_KIMI = Drop("moonshotai/Kimi-K3-Instruct", "Kimi", "moonshotai", "2026-08-01")
_HW = HardwareProfile(48.0, 128.0, 500.0, "nvidia", "RTX 5090", 2)
_ORGS = 9  # 5 labs + 4 aliases in LAB_SOURCES


def _patch_sources(monkeypatch, drops, *, orgs_failed=0, orgs_queried=_ORGS):
    outcome = CarouselFetch(
        drops=list(drops), orgs_queried=orgs_queried, orgs_failed=orgs_failed
    )
    monkeypatch.setattr("dropprobe.cli.fetch_carousel", lambda **_kw: outcome)
    monkeypatch.setattr("dropprobe.cli.detect_hardware", lambda **_kw: _HW)


def _json_report(result):
    """Parse the JSON document out of the CLI output.

    The version banner is echoed to stderr before the JSON body; the test
    runner captures both, so the document starts at the first ``{`` line.
    """

    lines = result.output.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("{"))
    return json.loads("\n".join(lines[start:]))


# --- m4: --json exports the static ProbeCards ---------------------------------
def test_latest_json_exports_static_probecards(monkeypatch):
    _patch_sources(monkeypatch, (_KIMI,))

    result = runner.invoke(app, ["latest", "--json"])

    assert result.exit_code == 0
    report = _json_report(result)
    assert len(report["drops"]) == 1
    assert report["hardware"]["gpu_arch"] == "nvidia"
    # The static card must be exported — not silently discarded.
    assert len(report["probe_cards"]) == 1
    card = report["probe_cards"][0]
    assert card["model_id"] == "moonshotai/Kimi-K3-Instruct"
    assert card["quant"]["name"] == "Q2_K"
    assert card["backend"]["fork_repo"] == "pwilkin/llama.cpp"
    # m1: no live probe ran; runnable is the static VRAM-fit verdict.
    assert card["smoke_probe_ok"] is None
    assert card["runnable"] is True


def test_latest_list_json_omits_probecards(monkeypatch):
    """--list explicitly skips the card assembly, even with --json."""

    _patch_sources(monkeypatch, (_KIMI,))

    result = runner.invoke(app, ["latest", "--list", "--json"])

    assert result.exit_code == 0
    report = _json_report(result)
    assert len(report["drops"]) == 1
    assert report["probe_cards"] == []


def test_latest_json_empty_window_is_quiet(monkeypatch):
    """A week with zero drops exports a valid empty report — without the
    'no probe ran' note (that note is about probes, not about an empty
    carousel)."""

    _patch_sources(monkeypatch, ())

    result = runner.invoke(app, ["latest", "--json"])

    assert result.exit_code == 0
    report = _json_report(result)
    assert report["drops"] == []
    assert report["probe_cards"] == []
    assert "no probe ran" not in result.stderr


# --- m1 human view: list fallback while probing is m2 --------------------------
def test_latest_plain_falls_back_to_list_view(monkeypatch):
    """With no live probe, a human gets drops + hardware plus the note —
    not an all-'?' ProbeCard table."""

    _patch_sources(monkeypatch, (_KIMI,))

    result = runner.invoke(app, ["latest"])

    assert result.exit_code == 0
    assert "This week's open-weight drops" in result.output
    assert "ProbeCard report" not in result.output
    assert "no probe ran — showing drops + hardware for now" in result.stderr


def test_latest_output_has_no_milestone_jargon(monkeypatch):
    """User-facing help and status text never leak internal milestone ids."""

    _patch_sources(monkeypatch, (_KIMI,))

    help_result = runner.invoke(app, ["latest", "--help"])
    assert help_result.exit_code == 0
    assert not re.search(r"\bm[0-9]\b", help_result.output)

    run_result = runner.invoke(app, ["latest"])
    assert run_result.exit_code == 0
    assert not re.search(r"\bm[0-9]\b", run_result.output)
    assert not re.search(r"\bm[0-9]\b", run_result.stderr)


# --- hub reachability diagnosis ------------------------------------------------
def test_latest_warns_when_every_hub_query_failed(monkeypatch):
    """An all-orgs outage is called out as a possible network problem, not
    silently presented as a quiet week."""

    _patch_sources(monkeypatch, (), orgs_failed=_ORGS)

    result = runner.invoke(app, ["latest"])

    assert result.exit_code == 0
    assert f"all {_ORGS} Hugging Face Hub queries failed" in result.stderr
    assert "network problem" in result.stderr


def test_latest_quiet_week_prints_no_outage_warning(monkeypatch):
    """Healthy orgs with zero in-window drops must not trigger the warning."""

    _patch_sources(monkeypatch, (), orgs_failed=0)

    result = runner.invoke(app, ["latest", "--list"])

    assert result.exit_code == 0
    assert "Hub queries failed" not in result.stderr


def test_latest_plain_shows_probecards_once_probed(monkeypatch):
    """Once any live probe runs (m2+), the human view shows the ProbeCard
    table — including rows whose static runnable verdict is False."""

    _patch_sources(monkeypatch, (_KIMI,))
    monkeypatch.setattr(
        "dropprobe.cli.probe_drop",
        lambda *_a, **_kw: ProbeResult(
            status=ProbeStatus.OK, smoke_probe_ok=True, latency_ms=123.0
        ),
    )

    result = runner.invoke(app, ["latest"])

    assert result.exit_code == 0
    assert "ProbeCard report" in result.output
    assert "smoke-probe lands in m2" not in result.stderr


# --- version lockstep ----------------------------------------------------------
def test_version_lockstep():
    repo_root = Path(__file__).resolve().parent.parent
    version_file = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert version_file == dropprobe.__version__
    assert f'version = "{version_file}"' in pyproject

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"dropprobe {dropprobe.__version__}" in result.output

    # Recorded-demo artifacts carry the version too.
    demo_results = json.loads(
        (repo_root / "docs" / "demo-results.json").read_text(encoding="utf-8")
    )
    assert demo_results["version"] == version_file
    cast_banner = (repo_root / "assets" / "demo.cast").read_text(encoding="utf-8")
    sample_run = (repo_root / "examples" / "sample_run.md").read_text(encoding="utf-8")
    assert f"DropProbe {version_file} — fetching" in cast_banner
    assert f"DropProbe {version_file} — fetching" in sample_run
