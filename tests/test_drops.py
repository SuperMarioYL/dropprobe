"""Tests for carousel fetch outcomes (drops + per-org reachability).

fetch_carousel exposes orgs_queried / orgs_failed so the CLI can tell an
unreachable Hub from a genuinely quiet week; fetch_weekly_drops stays the
list-returning compat wrapper. The Hub layer is monkeypatched — no network.
"""

from __future__ import annotations

from datetime import UTC, datetime

import dropprobe.drops as drops_mod
from dropprobe.drops import (
    LAB_SOURCES,
    CarouselFetch,
    fetch_carousel,
    fetch_weekly_drops,
)

_NOW = datetime(2026, 10, 11, tzinfo=UTC)


def _org_count() -> int:
    return sum(1 + len(lab.aliases) for lab in LAB_SOURCES)


def _hub_record(model_id: str, last_modified: str) -> dict:
    return {
        "id": model_id,
        "lastModified": last_modified,
        "tags": ["text-generation"],
        "siblings": [{"rfilename": "config.json"}],
    }


def test_fetch_carousel_counts_org_failures(monkeypatch):
    """Every org failing is reported, and the empty list is flagged as a
    network gap rather than a quiet week."""

    def _fail(org, *, limit, timeout):
        raise ConnectionError(f"offline: {org}")

    monkeypatch.setattr(drops_mod, "_query_org", _fail)

    fetch = fetch_carousel(window_days=7, now=_NOW)

    assert fetch.drops == []
    assert fetch.orgs_queried == _org_count()
    assert fetch.orgs_failed == fetch.orgs_queried
    assert fetch.all_orgs_failed is True


def test_fetch_carousel_partial_failure_is_not_all_failed(monkeypatch):
    """One flaky lab degrades the carousel but is not a total outage."""

    calls = {"n": 0}

    def _flaky(org, *, limit, timeout):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise ConnectionError(f"5xx: {org}")
        return []

    monkeypatch.setattr(drops_mod, "_query_org", _flaky)

    fetch = fetch_carousel(window_days=7, now=_NOW)

    assert fetch.orgs_queried == _org_count()
    assert fetch.orgs_failed == 3
    assert fetch.all_orgs_failed is False


def test_fetch_carousel_quiet_week_is_not_a_failure(monkeypatch):
    """Healthy orgs returning nothing is a quiet week — no failure flagged."""

    monkeypatch.setattr(drops_mod, "_query_org", lambda org, *, limit, timeout: [])

    fetch = fetch_carousel(window_days=7, now=_NOW)

    assert fetch.drops == []
    assert fetch.orgs_failed == 0
    assert fetch.all_orgs_failed is False


def test_fetch_carousel_collects_in_window_drops(monkeypatch):
    def _ok(org, *, limit, timeout):
        if org == "moonshotai":
            return [_hub_record("moonshotai/Kimi-K3-Instruct", "2026-10-08T00:00:00Z")]
        return []

    monkeypatch.setattr(drops_mod, "_query_org", _ok)

    fetch = fetch_carousel(window_days=7, now=_NOW)

    assert [d.model_id for d in fetch.drops] == ["moonshotai/Kimi-K3-Instruct"]
    assert fetch.orgs_queried == _org_count()
    assert fetch.orgs_failed == 0
    assert fetch.all_orgs_failed is False


def test_fetch_weekly_drops_wrapper_returns_drops_list(monkeypatch):
    """The public list[Drop] contract keeps working over the outcome record."""

    expected = CarouselFetch(
        drops=[], orgs_queried=_org_count(), orgs_failed=_org_count()
    )
    monkeypatch.setattr(drops_mod, "fetch_carousel", lambda **_kw: expected)

    assert fetch_weekly_drops(window_days=7, now=_NOW) == []
