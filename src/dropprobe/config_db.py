"""Bundled per-drop config DB.

A curated YAML file maps each known drop to the candidate GGUF quants,
backend fork, and day-0 tooling-readiness that the probe layer (m2) needs.
For v0.1 the file is author-curated and shipped in-repo — a community PR flow
is explicitly out of scope (the kill-criterion signals when to open it).

m1 loads the DB so the architecture is wired end-to-end, but does not yet
*use* it for probing (that's m2). The loader is real and tested; the probe
function (:mod:`dropprobe.probe`) consumes :class:`DropConfig` entries.
"""

from __future__ import annotations

import dataclasses
import functools
from importlib import resources
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard dep in pyproject
    yaml = None  # type: ignore[assignment]

__all__ = [
    "QuantSpec",
    "BackendSpec",
    "ToolingStatus",
    "DropConfig",
    "ConfigDB",
    "load_config_db",
]


@dataclasses.dataclass(frozen=True)
class QuantSpec:
    """One candidate GGUF quant for a drop.

    Attributes:
        name: Quant name (e.g. ``"Q2_K"``, ``"Q4_K_M"``).
        size_gb: On-disk weight size in GiB.
        source_repo: HF repo id shipping this quant (attribution — the
            config DB credits the community quant author).
    """

    name: str
    size_gb: float
    source_repo: str


@dataclasses.dataclass(frozen=True)
class BackendSpec:
    """The backend fork that runs this drop.

    Attributes:
        fork_repo: GitHub repo id (e.g. ``"pwilkin/llama.cpp"``).
        fork_ref: Git ref / branch (e.g. ``"kimi-k3-text"``).
        engine: ``"llama.cpp"`` or ``"ollama"``.
    """

    fork_repo: str
    fork_ref: str
    engine: str = "llama.cpp"


@dataclasses.dataclass(frozen=True)
class ToolingStatus:
    """Day-0 tooling readiness for a drop.

    Each axis is one of ``"day-0"`` / ``"supported"`` / ``"none"``.
    """

    comfyui: str = "none"
    llama_cpp: str = "none"
    ollama: str = "none"


@dataclasses.dataclass(frozen=True)
class DropConfig:
    """The runnable-config record the config DB stores per drop.

    This is the *static* half of a :class:`~dropprobe.probe.ProbeCard` — the
    smoke-probe (m2) fills in the live ``runnable`` / ``smoke_probe_ok`` axes.
    """

    model_id: str
    quants: tuple[QuantSpec, ...]
    backend: BackendSpec
    context_len: int
    tooling: ToolingStatus = dataclasses.field(default_factory=ToolingStatus)

    @property
    def smallest_quant(self) -> QuantSpec | None:
        """The smallest viable quant (the probe layer starts here)."""

        return min(self.quants, key=lambda q: q.size_gb) if self.quants else None


class ConfigDB:
    """In-memory view over the bundled config DB YAML.

    Lookups are by exact ``model_id``; unknown drops return ``None`` so the
    probe layer can fall back to its own heuristics.
    """

    def __init__(self, entries: dict[str, DropConfig]) -> None:
        self._entries: dict[str, DropConfig] = dict(entries)

    def get(self, model_id: str) -> DropConfig | None:
        """Return the config for ``model_id`` or ``None`` if unknown."""

        return self._entries.get(model_id)

    def all_ids(self) -> list[str]:
        """All known model ids (for debugging / ``--list`` extras)."""

        return sorted(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


def _coerce_entry(model_id: str, raw: dict[str, Any]) -> DropConfig:
    """Coerce one YAML entry into a :class:`DropConfig`."""

    quants = tuple(
        QuantSpec(
            name=str(q["name"]),
            size_gb=float(q["size_gb"]),
            source_repo=str(q.get("source_repo", "")),
        )
        for q in (raw.get("quants") or [])
    )
    b = raw.get("backend") or {}
    backend = BackendSpec(
        fork_repo=str(b.get("fork_repo", "")),
        fork_ref=str(b.get("fork_ref", "")),
        engine=str(b.get("engine", "llama.cpp")),
    )
    t = raw.get("tooling") or {}
    tooling = ToolingStatus(
        comfyui=str(t.get("comfyui", "none")),
        llama_cpp=str(t.get("llama_cpp", "none")),
        ollama=str(t.get("ollama", "none")),
    )
    return DropConfig(
        model_id=model_id,
        quants=quants,
        backend=backend,
        context_len=int(raw.get("context_len", 0)),
        tooling=tooling,
    )


@functools.lru_cache(maxsize=1)
def load_config_db() -> ConfigDB:
    """Load the bundled ``config_db.yaml`` (cached for the process).

    The YAML ships as a package data file under
    ``dropprobe/data/config_db.yaml``. Returns an empty :class:`ConfigDB` if
    the file is missing or PyYAML is unavailable — the probe layer treats an
    empty DB as "no curated config; fall back to heuristics."
    """

    entries: dict[str, DropConfig] = {}
    if yaml is None:  # pragma: no cover
        return ConfigDB(entries)
    try:
        text = (
            resources.files("dropprobe")
            .joinpath("data/config_db.yaml")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):
        return ConfigDB(entries)
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return ConfigDB(entries)
    for model_id, body in (raw.get("drops") or {}).items():
        if not isinstance(body, dict):
            continue
        try:
            entries[model_id] = _coerce_entry(model_id, body)
        except (KeyError, TypeError, ValueError):
            continue
    return ConfigDB(entries)
