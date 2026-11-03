# GPU Weather Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development; tasks 1–3 run in parallel with disjoint file ownership.

**Goal:** Real-time GPU clouds/precipitation/night sky driven by TopWeather on GNOME Wayland.
**Architecture:** TopWeather snapshot → tested controller and scene JSON → native GNOME GPU background. Static PNG remains fallback.
**Tech Stack:** Python/Pillow, GJS/Gio, GNOME Shell GLSLEffect, GLSL; Python/Node tests.
**Spec:** `docs/superpowers/specs/2026-09-12-gpu-weather-design.md`

## Global Constraints
- English-only outputs. GNOME 50 target. No picture-uri animation.
- Preserve existing user edits; work in isolated worktrees; do not commit user-owned changes.
- Weather units/time/unknown fields explicit. No credentials in snapshots.
- Snapshot and scene interfaces are defined in the spec and shared by every task.

### Task 1 — TopWeather export
Files: TopWeather `weather.js`, `extension.js`, new snapshot helper/tests, installer and README.
- [ ] Write/run failing provider-fixture and export tests (clouds, rain, snow units, malformed/missing observations).
- [ ] Add fields to provider requests/parsers; retain current public display behavior.
- [ ] Export successful fetches atomically, invalidate on settings changes/disable; never disrupt panel on write failure.
- [ ] Run existing/new tests and report exact files and evidence. No activation.

### Task 2 — GPU renderer
Files: new `extension/` and `tests/` shader/state tests only.
- [ ] Write failing scene/weather sanitation and transition tests, then implement pure renderer state.
- [ ] Implement GNOME 50 actor lifecycle and GLSLEffect with weather layers, cloud occlusion, precipitation, safe scheduling.
- [ ] Add reproducible GLSL/offscreen preview harness (same production shader), render fixtures and inspect outputs.
- [ ] Test clean enable/disable/error cleanup and expose static fallback. No live enable by agent.

### Task 3 — Python controller
Files: new `dynwall_weather.py`, `test_weather.py` only.
Interface: `load_weather(path=None, now=None)` returns valid snapshot or None; `weather_description(snapshot)` returns context string; `build_scene_document(spec, snapshot, cfg, now=None)` returns schema; `write_scene(path, document)` atomic/private write.
- [ ] Write/run failing tests for freshness/future/corrupt payloads, unknown units/values, finite numbers, scene envelope/atomic permissions.
- [ ] Implement helpers, preserving schema and unknown semantics.
- [ ] Test all helpers without network or desktop side effects.

### Task 4 — Integration/settings/installation (parent)
Files: `dynwall`, `dynwall-settings`, `install.sh`, README and integration tests.
- [ ] Add failing tests for CLI scene output/config and safe settings save (must not enable legacy player).
- [ ] Connect TopWeather snapshot + scene publishing; expose refresh/quality/FPS flags and safe settings.
- [ ] Install extension without implicit session disruption; provide enable/disable commands and rollback.
- [ ] Run all tests; inspect/render shader fixtures; copy validated changes back without overwriting preexisting edits.
- [ ] Perform controlled runtime validation, independent review, diff checks, and document unverified desktop cases.

## Execution ledger
- Baseline: seven Dynwall tests pass; TopWeather clean; Dynwall six user-modified tracked files preserved in isolated worktree and backup patch.
- Ruling: use one agreed data contract across parallel tasks; no separate network poller — TopWeather already owns polling and location.
- Ruling: no automatic commits of baseline dirty work; final changes remain reviewable in original checkout.

## Final verification ledger
- Tasks 1–4 implemented; Python32, renderer18, TopWeather71 assertions + installer regression pass.
- Independent controller/TopWeather and renderer reviews closed all identified blockers.
- Actual M6000 shader fixtures and private dual-monitor GNOME lifecycle/atomic-update tests pass.
- Ruling: measured weather/daylight overrides decorative celestial type; palette/position/size retained — avoids a sun persisting at midnight.
- Ruling: canonical snowfall stays unknown unless water-equivalent is actually measured; raw cm depth + period exported separately — no invented density conversion.
- Ruling: retain static fallback and no forced user-session restart — live activation may wait for logout/login.
- Detailed evidence and remaining boundaries: `docs/verification.md`.
