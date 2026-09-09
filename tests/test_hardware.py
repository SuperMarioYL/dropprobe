"""Tests for hardware detection (m1).

These run on any box — they mock NVML / psutil so they assert the *logic*,
not the specific GPU plugged into the CI runner. ``detect_hardware`` must
never raise on a CPU-only rig (the Kimi-K3-on-CPU reddit case).
"""

from __future__ import annotations

import types

import dropprobe.hardware as hw_mod


# --- detect_hardware never raises on a CPU-only box -------------------------
def test_detect_hardware_cpu_only_no_nvml(monkeypatch):
    """No NVML + no rocm-smi → CPU-only profile, no exception."""

    monkeypatch.setattr(hw_mod, "pynvml", None)
    monkeypatch.setattr(hw_mod.shutil, "which", lambda _name: None, raising=False)
    fake_psutil = types.SimpleNamespace(
        virtual_memory=lambda: types.SimpleNamespace(total=128 * 1024 ** 3),
        disk_usage=lambda _p: types.SimpleNamespace(free=200 * 1024 ** 3),
    )
    monkeypatch.setattr(hw_mod, "psutil", fake_psutil)

    profile = hw_mod.detect_hardware()

    assert profile.gpu_arch == "cpu"
    assert profile.device_count == 0
    assert profile.vram_gb == 0.0
    assert profile.is_cpu_only is True
    assert profile.ram_gb == 128.0
    assert profile.disk_free_gb == 200.0
    assert profile.gpu_name == ""


def test_detect_vram_nvidia_mock(monkeypatch):
    """NVML present + returns 2 devices × 24 GiB → 48 GiB total, nvidia arch."""

    class _Mem:
        def __init__(self, total):
            self.total = total

    class _Handle:
        pass

    fake_nvml = types.SimpleNamespace(
        nvmlInit=lambda: None,
        nvmlShutdown=lambda: None,
        nvmlDeviceGetCount=lambda: 2,
        nvmlDeviceGetHandleByIndex=lambda _i: _Handle(),
        nvmlDeviceGetMemoryInfo=lambda _h: _Mem(24 * 1024 ** 3),
        nvmlDeviceGetName=lambda _h: b"NVIDIA GeForce RTX 5090",
    )
    monkeypatch.setattr(hw_mod, "pynvml", fake_nvml)
    # Force the nvidia path (rocm-smi absent).
    monkeypatch.setattr(hw_mod.shutil, "which", lambda _name: None, raising=False)

    vram, name, count = hw_mod.detect_vram()

    assert vram == 48.0
    assert count == 2
    assert name == "NVIDIA GeForce RTX 5090"


def test_detect_vram_nvml_init_fails_falls_back_to_cpu(monkeypatch):
    """nvmlInit raising → treated as no NVIDIA GPU, not a crash."""

    fake_nvml = types.SimpleNamespace(
        nvmlInit=lambda: (_ for _ in ()).throw(RuntimeError("no driver")),
        nvmlShutdown=lambda: None,
    )
    monkeypatch.setattr(hw_mod, "pynvml", fake_nvml)
    monkeypatch.setattr(hw_mod.shutil, "which", lambda _name: None, raising=False)

    vram, _name, count = hw_mod.detect_vram()

    assert vram == 0.0
    assert count == 0


def test_hardware_profile_is_frozen():
    """HardwareProfile is a frozen dataclass — profiles are snapshots."""

    p = hw_mod.HardwareProfile(0.0, 64.0, 100.0, "cpu")
    try:
        p.vram_gb = 1.0  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("HardwareProfile should be frozen")


def test_hardware_to_jsonable_roundtrip():
    p = hw_mod.HardwareProfile(24.0, 64.0, 200.0, "nvidia", "RTX 5090", 1)
    d = hw_mod.hardware_to_jsonable(p)
    assert d["vram_gb"] == 24.0
    assert d["gpu_arch"] == "nvidia"
    assert d["gpu_name"] == "RTX 5090"


# --- detect_hardware: single detection pass, arch matches the winning detector
def _fake_psutil(monkeypatch):
    fake_psutil = types.SimpleNamespace(
        virtual_memory=lambda: types.SimpleNamespace(total=64 * 1024 ** 3),
        disk_usage=lambda _p: types.SimpleNamespace(free=200 * 1024 ** 3),
    )
    monkeypatch.setattr(hw_mod, "psutil", fake_psutil)


def test_detect_hardware_nvidia_single_pass(monkeypatch):
    """detect_hardware invokes the NVIDIA detector exactly once and labels
    gpu_arch "nvidia" — no second NVML round-trip that could flake."""

    calls = []

    def fake_nvidia():
        calls.append(1)
        return (24.0, "NVIDIA GeForce RTX 5090", 1)

    monkeypatch.setattr(hw_mod, "_detect_nvidia", fake_nvidia)
    monkeypatch.setattr(hw_mod, "_detect_rocm", lambda: None)
    _fake_psutil(monkeypatch)

    profile = hw_mod.detect_hardware()

    assert len(calls) == 1
    assert profile.gpu_arch == "nvidia"
    assert profile.vram_gb == 24.0
    assert profile.gpu_name == "NVIDIA GeForce RTX 5090"
    assert profile.device_count == 1
    assert profile.is_cpu_only is False


def test_detect_hardware_rocm_labels_amd(monkeypatch):
    """A successful rocm-smi detection labels gpu_arch "amd"."""

    monkeypatch.setattr(hw_mod, "_detect_nvidia", lambda: None)
    monkeypatch.setattr(hw_mod, "_detect_rocm", lambda: (16.0, "AMD Radeon RX 7900 XTX", 1))
    _fake_psutil(monkeypatch)

    profile = hw_mod.detect_hardware()

    assert profile.gpu_arch == "amd"
    assert profile.vram_gb == 16.0
    assert profile.device_count == 1


def test_detect_hardware_no_detector_cpu_profile(monkeypatch):
    """Both detectors failing → CPU-only profile with zeroed GPU axes."""

    monkeypatch.setattr(hw_mod, "_detect_nvidia", lambda: None)
    monkeypatch.setattr(hw_mod, "_detect_rocm", lambda: None)
    _fake_psutil(monkeypatch)

    profile = hw_mod.detect_hardware()

    assert profile.gpu_arch == "cpu"
    assert profile.vram_gb == 0.0
    assert profile.device_count == 0
    assert profile.gpu_name == ""
