"""Tests pinning the recorded demo artifacts to the code's actual behavior.

The v0.2.0 release shipped README quickstart text claiming the 2 GiB demo
profile yields runnable null while the recorded demo in docs/demo-results.json
(and examples/presentation_demo.py's own assertion) records false. These
tests keep the recorded artifact, the live example output, and the version
field in lockstep so the lie cannot ship again.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import dropprobe

REPO_ROOT = Path(__file__).resolve().parent.parent


def _demo_results() -> dict:
    return json.loads((REPO_ROOT / "docs" / "demo-results.json").read_text(encoding="utf-8"))


def test_recorded_demo_matches_live_example_output():
    """docs/demo-results.json records exactly what the example prints."""

    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "examples" / "presentation_demo.py")],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout
    assert out == _demo_results()["steps"][0]["output"]


def test_recorded_demo_version_matches_package():
    assert _demo_results()["version"] == dropprobe.__version__


def test_readme_quickstart_reports_definite_fit_verdict():
    """The quickstart must not resurrect the stale 'runnable is null' claim
    for the 2 GiB profile — the static verdict is a definite false."""

    zh = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    en = (REPO_ROOT / "README.en.md").read_text(encoding="utf-8")
    assert "后者为 null" not in zh
    assert "null for the second" not in en
