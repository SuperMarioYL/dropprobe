"""Weekly carousel drop discovery.

The carousel is the set of open-weight model *drops* released by the major
CN labs each week. A "drop" is a single model release event — one HuggingFace
repo published by one of the curated labs. :func:`fetch_weekly_drops` pulls
the week's drops from a hardcoded list of lab / HuggingFace sources and
returns them as :class:`Drop` records.

m1 scope: fetch + list only. No probing happens here.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

try:  # network + HF client are optional at import time so unit tests can
    # monkeypatch; the m1 happy path does call the real Hub.
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

__all__ = ["Drop", "LabSource", "LAB_SOURCES", "fetch_weekly_drops"]


# --- lab registry -----------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class LabSource:
    """A single lab's discovery source descriptor.

    Attributes:
        lab: Human-readable lab name (e.g. ``"DeepSeek"``).
        org: HuggingFace organization id (e.g. ``"deepseek-ai"``).
        aliases: Alternate org ids that re-publish the same weights.
    """

    lab: str
    org: str
    aliases: tuple[str, ...] = ()


# Curated lab roster — the open-weight carousel publishers. Hand-curated for
# v0.1 per the plan (a community PR flow is explicitly out of scope).
LAB_SOURCES: tuple[LabSource, ...] = (
    LabSource("DeepSeek", "deepseek-ai"),
    LabSource("Kimi", "moonshotai", aliases=("moonshot-community",)),
    LabSource("GLM", "zhipuai", aliases=("THUDM",)),
    LabSource("Qwen", "Qwen", aliases=("QwenLM",)),
    LabSource("MiniMax", "MiniMaxAI", aliases=("MiniMaxLLMTeam",)),
)


# --- drop record ------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Drop:
    """One weekly carousel drop — a single model release event.

    Attributes:
        model_id: Canonical model id (the HF repo id, e.g.
            ``"deepseek-ai/DeepSeek-V4-Flash"``).
        lab: Lab display name (e.g. ``"DeepSeek"``).
        org: HuggingFace org id the weights live under.
        drop_date: ISO-8601 UTC date the drop was published.
        files: Snapshot of notable files in the repo (gguf / safetensors /
            config). Used by the probe layer to spot quant availability.
        tags: Free-form HF tags (``"text-generation"`` etc.).
    """

    model_id: str
    lab: str
    org: str
    drop_date: str
    files: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def repo_name(self) -> str:
        """The repo half of ``model_id`` (after the ``/``)."""

        return self.model_id.split("/", 1)[-1]


# --- fetch ------------------------------------------------------------------
_HUB_API = "https://huggingface.co/api/models"


def _within_window(drop_date: str, window_days: int, now: datetime) -> bool:
    """True if ``drop_date`` falls inside ``[now - window_days, now]``."""

    try:
        d = datetime.fromisoformat(drop_date.replace("Z", "+00:00"))
    except ValueError:
        return False
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return now - window_days * timedelta(days=1) <= d <= now


def _query_org(org: str, *, limit: int, timeout: float) -> list[dict[str, Any]]:
    """Fetch recent models for one HF org via the public Hub REST API.

    The Hub's ``/api/models?author=<org>`` endpoint lists models newest-first
    and returns each model's ``lastModified`` / ``tags`` / ``siblings`` (files).
    """

    if httpx is None:  # pragma: no cover - httpx is a hard dep in pyproject
        return []
    params = {"author": org, "limit": limit, "full": "true", "sort": "lastModified", "direction": "-1"}
    resp = httpx.get(_HUB_API, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def _to_drop(model: dict[str, Any], lab: LabSource) -> Drop:
    """Coerce one Hub model record into a :class:`Drop`."""

    model_id = model.get("id") or model.get("modelId") or ""
    if not model_id:
        raise ValueError("Hub model record missing id")
    siblings = model.get("siblings") or []
    files = tuple(s["rfilename"] for s in siblings if isinstance(s, dict) and s.get("rfilename"))
    tags = tuple(model.get("tags") or ())
    drop_date = model.get("lastModified") or model.get("createdAt") or datetime.now(UTC).isoformat()
    # Resolve the canonical lab name from whichever org actually hosts it.
    owner = model_id.split("/", 1)[0] if "/" in model_id else lab.org
    lab_name = lab.lab
    for src in LAB_SOURCES:
        if owner == src.org or owner in src.aliases:
            lab_name = src.lab
            break
    return Drop(
        model_id=model_id,
        lab=lab_name,
        org=owner,
        drop_date=drop_date,
        files=files,
        tags=tags,
    )


def fetch_weekly_drops(
    *,
    window_days: int = 7,
    now: datetime | None = None,
    per_lab_limit: int = 15,
    timeout: float = 15.0,
) -> list[Drop]:
    """Fetch this week's carousel drops from the curated lab / HF sources.

    Walks :data:`LAB_SOURCES`, queries the HuggingFace Hub for each org's most
    recent models, and keeps only those published inside the trailing
    ``window_days`` window. Returns drops newest-first.

    Degrades gracefully: a per-org HTTP failure is logged-and-skipped so one
    flaky lab never blanks the whole carousel. If *every* org is unreachable
    (offline box, no network), returns an empty list — :func:`fetch_weekly_drops`
    never raises on network errors, only on programmer mistakes.

    Args:
        window_days: Trailing window in days (default 7 — the carousel cadence).
        now: Reference "now" for the window (UTC). Defaults to real now; tests
            inject a fixed timestamp.
        per_lab_limit: Max models to pull per org from the Hub.
        timeout: Per-request HTTP timeout in seconds.

    Returns:
        Drops published within the window, newest-first.
    """

    now = now or datetime.now(UTC)
    drops: list[Drop] = []
    for lab in LAB_SOURCES:
        orgs = (lab.org, *lab.aliases)
        for org in orgs:
            try:
                records = _query_org(org, limit=per_lab_limit, timeout=timeout)
            except Exception:
                # Offline / 5xx / rate-limit — skip this org, keep going.
                # A carousel where one lab's Hub hiccups blanks *all* drops is
                # worse than one that's missing one lab for a day.
                continue
            for rec in records:
                try:
                    drop = _to_drop(rec, lab)
                except ValueError:
                    continue
                if _within_window(drop.drop_date, window_days, now):
                    drops.append(drop)
    # Newest-first, dedup by model_id (an org + its alias can both list it).
    seen: set[str] = set()
    unique: list[Drop] = []
    for d in sorted(drops, key=lambda x: x.drop_date, reverse=True):
        if d.model_id in seen:
            continue
        seen.add(d.model_id)
        unique.append(d)
    return unique


def drops_to_jsonable(drops: Sequence[Drop]) -> list[dict[str, Any]]:
    """Serialize drops to a JSON-friendly list of plain dicts."""

    return [dataclasses.asdict(d) for d in drops]
