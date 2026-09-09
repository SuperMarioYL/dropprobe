"""Tests for the probe + config-DB + probe-card assembly (m1).

m1 scope: the *static* assembly — config DB → quants / fork / tooling
joined onto a Drop + HardwareProfile — plus the ``NOT_PROBED`` contract for
the live smoke-probe (which lands in m2). These tests assert the data-model
contract without needing llama.cpp / Ollama on the box.
"""

from __future__ import annotations

import dropprobe.probe as probe_mod
from dropprobe.config_db import load_config_db
from dropprobe.drops import Drop
from dropprobe.hardware import HardwareProfile
from dropprobe.probe import (
    ProbeResult,
    ProbeStatus,
    build_probe_card,
    detect_backend,
    probe_drop,
)


# --- config DB loader -------------------------------------------------------
def test_config_db_loads_bundled_yaml():
    db = load_config_db()
    assert len(db) >= 5
    kimi = db.get("moonshotai/Kimi-K3-Instruct")
    assert kimi is not None
    # smallest quant is Q2_K (~39.5 GiB)
    assert kimi.smallest_quant is not None
    assert kimi.smallest_quant.name == "Q2_K"
    assert kimi.smallest_quant.source_repo == "GrEarl/Kimi-K3-GGUF"
    assert kimi.backend.fork_repo == "pwilkin/llama.cpp"
    assert kimi.backend.fork_ref == "kimi-k3-text"
    assert kimi.tooling.llama_cpp == "day-0"


def test_config_db_unknown_drop_returns_none():
    db = load_config_db()
    assert db.get("nobody/never-dropped") is None


# --- probe_drop contract (m1 → NOT_PROBED) ----------------------------------
def test_probe_drop_returns_not_probed_in_m1():
    drop = Drop("moonshotai/Kimi-K3-Instruct", "Kimi", "moonshotai", "2026-08-01")
    hw = HardwareProfile(24.0, 64.0, 200.0, "nvidia", "RTX 5090", 1)
    db = load_config_db()
    result = probe_drop(drop, hw, db)
    assert result.status is ProbeStatus.NOT_PROBED
    assert result.smoke_probe_ok is None
    assert result.runnable is None


def test_probe_result_runnable_property():
    assert ProbeResult(ProbeStatus.OK, smoke_probe_ok=True).runnable is True
    assert ProbeResult(ProbeStatus.FAILED, smoke_probe_ok=False).runnable is False
    assert ProbeResult(ProbeStatus.NOT_PROBED).runnable is None
    assert ProbeResult(ProbeStatus.SKIPPED).runnable is False


# --- build_probe_card static assembly --------------------------------------
def test_build_probe_card_known_drop_fills_static_fields():
    drop = Drop("moonshotai/Kimi-K3-Instruct", "Kimi", "moonshotai", "2026-08-01")
    hw = HardwareProfile(48.0, 128.0, 500.0, "nvidia", "RTX 5090", 2)
    db = load_config_db()
    card = build_probe_card(drop, hw, db)
    assert card.model_id == "moonshotai/Kimi-K3-Instruct"
    assert card.lab == "Kimi"
    assert card.quant is not None
    assert card.quant.name == "Q2_K"
    assert card.backend is not None
    assert card.backend.engine == "llama.cpp"
    assert card.tooling.llama_cpp == "day-0"
    # m1: live axes are None (not probed); runnable is the static VRAM best-guess.
    assert card.smoke_probe_ok is None
    assert card.runnable is True  # 39.5 GiB fits in 48 GiB (minus headroom)


def test_build_probe_card_vram_does_not_fit():
    drop = Drop("moonshotai/Kimi-K3-Instruct", "Kimi", "moonshotai", "2026-08-01")
    # Tiny GPU: Q2_K (39.5 GiB) doesn't fit in 12 GiB.
    hw = HardwareProfile(12.0, 32.0, 200.0, "nvidia", "RTX 3060", 1)
    db = load_config_db()
    card = build_probe_card(drop, hw, db)
    # A curated quant that provably does not fit gets a definite "no"
    # verdict — not the "?" (None) reserved for unknown drops.
    assert card.runnable is False


def test_build_probe_card_unknown_drop_has_no_config():
    drop = Drop("nobody/never-dropped", "Unknown", "nobody", "2026-08-01")
    hw = HardwareProfile(24.0, 64.0, 200.0, "nvidia", "RTX 4090", 1)
    db = load_config_db()
    card = build_probe_card(drop, hw, db)
    assert card.quant is None
    assert card.backend is None
    assert card.context_len == 0
    assert card.smoke_probe_ok is None
    # No curated quant → no static fit verdict either ("?").
    assert card.runnable is None
    assert "no curated config yet" in card.run_cmd


def test_build_probe_card_cpu_only_uses_ram_for_fit():
    """CPU-only rig (big-DRAM) fits quants against RAM, not VRAM."""

    drop = Drop("zhipuai/GLM-5.5-9B-Chat", "GLM", "zhipuai", "2026-08-01")
    # 768 GiB DDR5, no GPU — the Kimi-K3-on-CPU reddit rig class.
    hw = HardwareProfile(0.0, 768.0, 2000.0, "cpu", "", 0)
    db = load_config_db()
    card = build_probe_card(drop, hw, db)
    # GLM 5.5 9B Q4_K_M is ~5.9 GiB → fits in 768 GiB RAM trivially.
    assert card.quant is not None
    assert card.runnable is True
    assert hw.is_cpu_only is True


def test_probecard_to_dict_is_jsonable():
    drop = Drop("moonshotai/Kimi-K3-Instruct", "Kimi", "moonshotai", "2026-08-01")
    hw = HardwareProfile(24.0, 64.0, 200.0, "nvidia", "RTX 4090", 1)
    db = load_config_db()
    card = build_probe_card(drop, hw, db)
    d = card.to_dict()
    assert d["model_id"] == "moonshotai/Kimi-K3-Instruct"
    assert d["quant"]["name"] == "Q2_K"


# --- detect_backend (safe on a box with no backends) -------------------------
def test_detect_backend_none_when_missing(monkeypatch):
    monkeypatch.setattr(probe_mod.shutil, "which", lambda _name: None)
    assert detect_backend() is None
