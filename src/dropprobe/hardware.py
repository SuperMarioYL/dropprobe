"""Local hardware detection.

Detects the box DropProbe is running on — GPU VRAM + arch, CPU RAM, free disk
— so the probe layer can answer "does this drop fit my hardware" without the
user hand-declaring it. m1 ships this fully; the probe layer (m2) consumes it.

Detection order:
  1. NVIDIA via ``pynvml`` (nvml) — the common home / 信创 case.
  2. ROCm via ``rocm-smi`` subprocess — the AMD band.
  3. CPU-only fallback — ``vram_gb=0`` when neither is present, so a
     big-DRAM CPU rig is still a first-class profile (the Kimi-K3-on-CPU
     reddit case is exactly this).

Everything degrades gracefully: a missing driver / missing module never
raises — it yields a zero for that axis. :func:`detect_hardware` only raises
on programmer mistakes, never on "your box has no NVIDIA GPU."
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
import shutil
import subprocess
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a hard dep in pyproject
    psutil = None  # type: ignore[assignment]

try:
    import pynvml
except ImportError:  # pragma: no cover - optional on CPU-only rigs
    pynvml = None  # type: ignore[assignment]

__all__ = ["HardwareProfile", "detect_hardware", "detect_vram"]


@dataclasses.dataclass(frozen=True)
class HardwareProfile:
    """A snapshot of the local box's inference-relevant resources.

    Attributes:
        vram_gb: Total GPU VRAM across visible devices, in GiB (10^30 bytes
            divided by 2^30). 0.0 on a CPU-only rig — see ``gpu_arch``.
        ram_gb: Total system RAM in GiB.
        disk_free_gb: Free disk on the volume holding the model cache, in GiB.
        gpu_arch: ``"nvidia"`` / ``"amd"`` / ``"cpu"``. ``"cpu"`` means no
            accelerator was detected (a big-DRAM CPU rig, e.g. 768GB DDR5).
        gpu_name: Human-readable GPU name (first device) or ``""`` on CPU.
        device_count: Number of visible GPU devices (0 on CPU-only).
    """

    vram_gb: float
    ram_gb: float
    disk_free_gb: float
    gpu_arch: str
    gpu_name: str = ""
    device_count: int = 0

    @property
    def is_cpu_only(self) -> bool:
        """True when no accelerator was detected."""

        return self.gpu_arch == "cpu" or self.device_count == 0


# --- VRAM -------------------------------------------------------------------
def _detect_nvidia() -> tuple[float, str, int] | None:
    """Return ``(vram_gb, first_gpu_name, device_count)`` via NVML, or None."""

    if pynvml is None:
        return None
    try:
        pynvml.nvmlInit()
    except Exception:
        return None
    try:
        count = pynvml.nvmlDeviceGetCount()
        total_bytes = 0
        first_name = ""
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_bytes += info.total
            if not first_name:
                try:
                    first_name = pynvml.nvmlDeviceGetName(handle)
                except Exception:
                    first_name = ""
        vram_gb = total_bytes / (1024 ** 3)
        if isinstance(first_name, bytes):
            first_name = first_name.decode("utf-8", "ignore")
        return (round(vram_gb, 1), first_name, count)
    except Exception:
        return None
    finally:
        with contextlib.suppress(Exception):
            pynvml.nvmlShutdown()


def _detect_rocm() -> tuple[float, str, int] | None:
    """Return ``(vram_gb, first_gpu_name, device_count)`` via ``rocm-smi``."""

    if not shutil.which("rocm-smi"):
        return None
    try:
        out = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--showproductname", "--json"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except Exception:
        return None
    if out.returncode != 0 or not out.stdout:
        return None
    try:
        import json as _json

        data = _json.loads(out.stdout)
    except Exception:
        return None
    # rocm-smi --json returns {"card0": {"VRAM Total Memory (B)": "...", ...}}
    total = 0
    count = 0
    first_name = ""
    for _key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        vram_b = entry.get("VRAM Total Memory (B)") or entry.get("Memory total (B)")
        if vram_b is None:
            continue
        try:
            total += int(str(vram_b).replace(",", "").strip())
        except ValueError:
            continue
        count += 1
        if not first_name:
            first_name = entry.get("Card model") or entry.get("Card series") or "AMD GPU"
    if count == 0:
        return None
    return (round(total / (1024 ** 3), 1), first_name, count)


def detect_vram() -> tuple[float, str, int]:
    """Detect GPU VRAM, name, and device count.

    Tries NVIDIA (NVML) first, then ROCm (rocm-smi), then falls back to a
    CPU-only zero profile. Never raises.
    """

    for detector in (_detect_nvidia, _detect_rocm):
        result = detector()
        if result is not None:
            vram, name, count = result
            return (vram, name, count)
    return (0.0, "", 0)


# --- RAM + disk -------------------------------------------------------------
def _detect_ram() -> float:
    if psutil is None:  # pragma: no cover
        return 0.0
    return round(psutil.virtual_memory().total / (1024 ** 3), 1)


def _detect_disk_free(path: str = "") -> float:
    target = path or os.path.expanduser("~/.cache/huggingface")
    parent = os.path.dirname(target) or os.sep
    # Prefer the cache dir's volume; fall back to cwd's volume.
    for candidate in (target, parent, os.getcwd()):
        if psutil is not None:
            try:
                usage = psutil.disk_usage(candidate)
                return round(usage.free / (1024 ** 3), 1)
            except Exception:
                continue
    if shutil.disk_usage is not None:
        try:
            usage = shutil.disk_usage(os.getcwd())
            return round(usage.free / (1024 ** 3), 1)
        except Exception:
            return 0.0
    return 0.0


# --- top-level --------------------------------------------------------------
def detect_hardware(*, cache_dir: str = "") -> HardwareProfile:
    """Build a :class:`HardwareProfile` for the current box.

    Args:
        cache_dir: Where model weights would land. Disk-free is measured on
            this volume so the "does it fit" arithmetic is honest.

    Returns:
        A frozen profile. GPU axes are zero/empty on a CPU-only rig.
    """

    vram_gb, gpu_name, device_count = detect_vram()
    if device_count == 0:
        gpu_arch = "cpu"
    elif _detect_nvidia() is not None:
        gpu_arch = "nvidia"
    else:
        gpu_arch = "amd"
    return HardwareProfile(
        vram_gb=vram_gb,
        ram_gb=_detect_ram(),
        disk_free_gb=_detect_disk_free(cache_dir),
        gpu_arch=gpu_arch,
        gpu_name=gpu_name,
        device_count=device_count,
    )


def hardware_to_jsonable(profile: HardwareProfile) -> dict[str, Any]:
    """Serialize a profile to a JSON-friendly plain dict."""

    return dataclasses.asdict(profile)
