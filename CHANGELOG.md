# Changelog

All notable changes to DropProbe are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-10-11

### Fixed

- The README quickstart (zh + en) now reports the recorded demo's actual
  result for the 2 GiB profile: `runnable` is `false` (a definite static
  does-not-fit verdict), not `null`. The stale text predated the v0.2.0
  definite-verdict change and contradicted `docs/demo-results.json` and
  `examples/presentation_demo.py`'s own assertion.
- `examples/sample_run.md` no longer presents `dropprobe latest` as firing
  live 30-second inferences per drop — it shows the real behavior: ProbeCards
  are assembled statically and a human run falls back to the drops +
  hardware view while nothing has been probed. Internal milestone labels
  (m1/m2/m3) were removed from the user-facing sample and CLI strings; the
  fallback note now reads "no probe ran — showing drops + hardware for now".

### Added

- `dropprobe latest` now distinguishes an unreachable Hugging Face Hub from
  a genuinely quiet carousel: when every organization query fails, a stderr
  warning says the empty drop list may be a network problem. The new
  `fetch_carousel()` returns a `CarouselFetch` outcome (drops plus
  `orgs_queried` / `orgs_failed`); `fetch_weekly_drops()` keeps its
  `list[Drop]` return as a thin wrapper, so existing callers are unaffected.

## [0.2.0] — 2026-09-09

### Fixed

- `dropprobe latest --json` now exports the static ProbeCards in the
  `probe_cards` array. Previously the cards were assembled and then
  discarded by the m1 list-view fallback, so the documented full-report
  JSON export always shipped an empty array. A week with zero drops also
  no longer prints the misleading "smoke-probe lands in m2" note.
- Static VRAM-fit verdicts are now definite: a drop whose smallest curated
  quant does not fit the detected hardware reports `runnable: false`
  instead of collapsing to `null` ("?"). `runnable` stays `null` only for
  drops without a curated config entry.
- `detect_hardware` runs each GPU detector exactly once and labels
  `gpu_arch` from the detector that actually produced the result. A flaky
  second NVML round-trip could previously mislabel an NVIDIA box as `amd`
  while still reporting NVML-sourced VRAM and GPU name.

### Changed

- Replaced the deprecated `pynvml` dependency (a redirector shim that
  emits a `FutureWarning` on import) with `nvidia-ml-py`, which ships the
  identical `pynvml` module. No import-site changes are needed.
- Removed the unused `huggingface_hub` and `ollama` install requirements —
  nothing in the package imports them (Hub queries go through `httpx`;
  backend detection shells out to the `ollama` binary). They will return
  when the m2 live smoke-probe actually needs them.
- Updated the recorded demo (`docs/demo-results.json`,
  `examples/presentation_demo.py`) to reflect the definite static fit
  verdicts.
- `ProbeStatus` now inherits from `enum.StrEnum` (Python 3.12+) instead of
  `(str, enum.Enum)` — current ruff releases flag the latter (UP042), which
  had turned the CI lint step red. Serialization behavior is unchanged.

## [0.1.0] — 2026-08-04

### Added

- Initial release: weekly carousel drop discovery from the curated
  CN-lab HuggingFace sources (`dropprobe latest --list`), local hardware
  detection (NVML / ROCm / CPU fallback), the bundled per-drop config DB
  (quants, backend fork, day-0 tooling-readiness), static ProbeCard
  assembly, rich table output, and `--json` export of drops + hardware.
