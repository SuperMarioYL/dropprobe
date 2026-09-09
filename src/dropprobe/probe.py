"""Smoke-probe layer — the genuinely new behavior.

The smoke-probe fires a 30-second capped test inference on the user's *real*
hardware with the smallest viable GGUF quant, instead of doing static VRAM
arithmetic. Static arithmetic tells you whether a quant *fits*; the
smoke-probe tells you whether the backend fork *actually runs it* on your
box — the fork / quant / day-0-tooling columns are unfakeable.

**Milestone status:** m1 ships the data model (:class:`ProbeResult`,
:class:`ProbeCard`) and the *static* assembly (config DB → quants / fork /
tooling-readiness joined onto a :class:`~dropprobe.drops.Drop` +
:class:`~dropprobe.hardware.HardwareProfile`). The *live* 30s inference is
m2 — :func:`probe_drop` returns ``ProbeStatus.NOT_PROBED`` until m2 lands.
"""

from __future__ import annotations

import dataclasses
import enum
import shutil
import subprocess
from typing import Any

from .config_db import BackendSpec, ConfigDB, DropConfig, QuantSpec, ToolingStatus
from .drops import Drop
from .hardware import HardwareProfile

__all__ = [
    "ProbeStatus",
    "ProbeResult",
    "ProbeCard",
    "build_probe_card",
    "probe_drop",
    "detect_backend",
]


class ProbeStatus(enum.StrEnum):
    """Outcome of a smoke-probe attempt on one drop."""

    OK = "ok"  # the 30s inference completed
    FAILED = "failed"  # the inference errored / timed out / OOM'd
    NOT_PROBED = "not_probed"  # m1: probing not yet implemented (m2 lands it)
    SKIPPED = "skipped"  # no quant fit the hardware at all


@dataclasses.dataclass(frozen=True)
class ProbeResult:
    """The live half of a ProbeCard — what the smoke-probe measured.

    Attributes:
        status: :class:`ProbeStatus` outcome.
        smoke_probe_ok: True if the 30s inference produced tokens. ``None``
            until m2 actually runs the probe.
        latency_ms: Time-to-first-token, if measured.
        error: Human-readable failure reason (``""`` on success / not-probed).
    """

    status: ProbeStatus
    smoke_probe_ok: bool | None = None
    latency_ms: float | None = None
    error: str = ""

    @property
    def runnable(self) -> bool | None:
        """``True`` if the probe succeeded; ``None`` if not yet probed."""

        if self.status is ProbeStatus.NOT_PROBED:
            return None
        return self.status is ProbeStatus.OK


@dataclasses.dataclass(frozen=True)
class ProbeCard:
    """A per-drop runnable-config record — the core primitive (plan §2).

    Joins the static config (Drop + HardwareProfile + DropConfig) with the
    live :class:`ProbeResult`. m1 fills the static half; m2 fills the live
    half via :func:`probe_drop`; m3 formats the full table + ``--json``.
    """

    model_id: str
    lab: str
    drop_date: str
    hardware_profile: HardwareProfile
    quant: QuantSpec | None
    backend: BackendSpec | None
    context_len: int
    tooling: ToolingStatus
    runnable: bool | None
    smoke_probe_ok: bool | None
    run_cmd: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict (for ``dropprobe latest --json``, m3)."""

        d = dataclasses.asdict(self)
        # ProbeStatus is a str enum; asdict keeps it — coerce for pure JSON.
        return d


def _vr_fits(quant: QuantSpec | None, hw: HardwareProfile) -> bool:
    """Static VRAM fit arithmetic (the part the smoke-probe replaces).

    Kept as a fallback for CPU-only rigs where no GPU probe can run, and so
    m1 can produce a runnable-axis best-guess before m2 fires real inferences.
    """

    if quant is None:
        return False
    if hw.is_cpu_only:
        # Big-DRAM CPU rig: quants live in system RAM, not VRAM.
        return quant.size_gb <= hw.ram_gb
    # GPU: leave ~1.5 GiB headroom for the KV cache + runtime.
    return quant.size_gb <= max(hw.vram_gb - 1.5, 0.0)


def build_probe_card(
    drop: Drop,
    hw: HardwareProfile,
    db: ConfigDB,
    result: ProbeResult | None = None,
) -> ProbeCard:
    """Assemble a :class:`ProbeCard` from the static config + (optional) probe.

    m1 calls this with ``result=None`` → the card's live axes are ``None``
    ("not probed yet") and ``runnable`` falls back to the static VRAM fit
    (definite True/False when a curated quant exists, ``None`` otherwise).
    m2 will pass a real :class:`ProbeResult` from :func:`probe_drop`.
    """

    cfg: DropConfig | None = db.get(drop.model_id)
    quant = cfg.smallest_quant if cfg else None
    backend = cfg.backend if cfg else None
    tooling = cfg.tooling if cfg else ToolingStatus()
    context_len = cfg.context_len if cfg else 0
    result = result or ProbeResult(status=ProbeStatus.NOT_PROBED)
    runnable = result.runnable
    if runnable is None and quant is not None:
        # Static best-guess while the live probe is m2: a curated quant gets
        # a definite fits / does-not-fit verdict. Only an unknown drop (no
        # curated config) stays None ("?").
        runnable = _vr_fits(quant, hw)
    run_cmd = _render_run_cmd(drop, quant, backend)
    return ProbeCard(
        model_id=drop.model_id,
        lab=drop.lab,
        drop_date=drop.drop_date,
        hardware_profile=hw,
        quant=quant,
        backend=backend,
        context_len=context_len,
        tooling=tooling,
        runnable=runnable,
        smoke_probe_ok=result.smoke_probe_ok,
        run_cmd=run_cmd,
    )


def _render_run_cmd(
    drop: Drop, quant: QuantSpec | None, backend: BackendSpec | None
) -> str:
    """Render a copy-paste run command, or a placeholder if no config yet."""

    if backend is None or quant is None:
        return f"# {drop.model_id}: no curated config yet — see config_db.yaml"
    if backend.engine == "ollama":
        return (
            f"ollama run {quant.source_repo or drop.model_id}:{quant.name.lower()} "
            f"--ctx-size 4096"
        )
    return (
        f"llama.cpp/{backend.fork_ref} -m {quant.name}.gguf "
        f"-c 4096 -n 128 --no-warmup"
    )


# --- backend detection (m2 helper, safe to call in m1) ----------------------
def detect_backend() -> str | None:
    """Return ``"llama.cpp"`` / ``"ollama"`` / ``None`` for the local box.

    The plan says: assume llama.cpp is present, fall back to Ollama if the
    llama.cpp binary is missing. Safe to call in m1 (used by the probe layer
    in m2); returns ``None`` when neither backend is on PATH.
    """

    for binary, name in (
        ("llama-cli", "llama.cpp"),
        ("main", "llama.cpp"),
        ("ollama", "ollama"),
    ):
        if shutil.which(binary):
            # Disambiguate "main" — only treat it as llama.cpp if it looks
            # like one (the probe layer in m2 will verify by --version).
            if binary == "main" and not _looks_like_llamacpp(binary):
                continue
            return name
    return None


def _looks_like_llamacpp(binary: str) -> bool:
    """Heuristic: does ``binary --help`` mention llama.cpp-ish flags?"""

    try:
        out = subprocess.run(
            [binary, "--help"], capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return False
    blob = (out.stdout + out.stderr).lower()
    return any(tok in blob for tok in ("-m ", "model", "llama", "gguf"))


def probe_drop(  # noqa: D401 - imperative is fine
    drop: Drop,
    hw: HardwareProfile,
    db: ConfigDB,
    *,
    timeout_s: float = 30.0,
) -> ProbeResult:
    """Smoke-probe one drop on the local hardware (m2 — not yet implemented).

    The m2 milestone launches a 30s capped test inference via llama.cpp or
    Ollama on the smallest viable quant and records ``runnable`` /
    ``smoke_probe_ok``. Until m2 lands, this returns ``NOT_PROBED`` so the
    m1 ``--list`` flow can run end-to-end without a backend present.
    """

    # m2 will: pick smallest viable quant from db.get(drop.model_id),
    # ensure the quant is cached (HF download, never >small-quant size),
    # launch `llama.cpp -m <quant>.gguf -p "ping" -n 8 --no-mmap` with the
    # 30s timeout, capture exit code + first-token latency, and return OK /
    # FAILED / SKIPPED accordingly. For m1 we surface NOT_PROBED explicitly.
    return ProbeResult(status=ProbeStatus.NOT_PROBED, error="probing lands in m2")
