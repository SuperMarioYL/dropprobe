"""Tests for the CLI surface.

m4: ``dropprobe latest --json`` exports the *static* ProbeCards (the cards
are assembled from the config DB even though the live smoke-probe is m2).
m8: the version surfaces stay in lockstep (VERSION file, pyproject,
``__version__``, ``--version`` output).

The fetch + hardware layers are monkeypatched so these tests assert the CLI
contract without network access or a real GPU.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import dropprobe
from dropprobe.cli import app
from dropprobe.drops import Drop
from dropprobe.hardware import HardwareProfile
from dropprobe.probe import ProbeResult, ProbeStatus

runner = CliRunner()

_KIMI = Drop("moonshotai/Kimi-K3-Instruct", "Kimi", "moonshotai", "2026-08-01")
_HW = HardwareProfile(48.0, 128.0, 500.0, "nvidia", "RTX 5090", 2)


def _patch_sources(monkeypatch, drops):
    monkeypatch.setattr("dropprobe.cli.fetch_weekly_drops", lambda **_kw: list(drops))
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
    misleading 'smoke-probe lands in m2' note (that note is about probes,
    not about an empty carousel)."""

    _patch_sources(monkeypatch, ())

    result = runner.invoke(app, ["latest", "--json"])

    assert result.exit_code == 0
    report = _json_report(result)
    assert report["drops"] == []
    assert report["probe_cards"] == []
    assert "smoke-probe lands in m2" not in result.stderr


# --- m1 human view: list fallback while probing is m2 --------------------------
def test_latest_plain_falls_back_to_list_view(monkeypatch):
    """With no live probe (m1), a human gets drops + hardware plus the m2
    note — not an all-'?' ProbeCard table."""

    _patch_sources(monkeypatch, (_KIMI,))

    result = runner.invoke(app, ["latest"])

    assert result.exit_code == 0
    assert "This week's open-weight drops" in result.output
    assert "ProbeCard report" not in result.output
    assert "smoke-probe lands in m2" in result.stderr


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


# --- m8: version surfaces stay in lockstep -------------------------------------
def test_version_lockstep():
    repo_root = Path(__file__).resolve().parent.parent
    version_file = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert version_file == dropprobe.__version__
    assert f'version = "{version_file}"' in pyproject

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"dropprobe {dropprobe.__version__}" in result.output
