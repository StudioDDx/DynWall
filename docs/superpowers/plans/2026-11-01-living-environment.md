# Living environment implementation plan

Approval: all eight feature concepts approved; ambient audio excluded. Preserve all existing uncommitted work. No commits, pushes, new services, automatic schedules, logout, or unrelated desktop changes.

## Architecture and shared contract

Use additive local Python domain helpers, pure JavaScript environmental/runtime helpers, and native GTK controls. TopWeather remains the only observation authority; never write synthetic observations to its cache. Existing schema-v1 scene fields remain backward compatible.

Config additions: `landscape_pack` (local pack id or empty); `scene_customization` (finite clamped horizon, terrain_scale, mist, warmth, darkness, animation_intensity); `presets` (bounded named customization/background/pack snapshots); `favorites` (bounded scene selections); `schedule` (disabled by default, local minute entries and optional bounded rotation); `preview` (separate transient cache document, never a weather observation); `persistent_weather` (enabled flag); `atmospheric_intensity` (0..1); `battery_saver` (true); existing weather_fps/weather_quality remain the visible configured workload controls.

Python module dynwall_living.py owns normalized config, pack validation/import/export and Pillow compositing, preset/favorite/schedule selection, and preview scene derivation. Public functions: normalize_living_config(config), resolve_selection(config, now), preview_scene(scene, request, now), import_pack(source, destination), export_pack(pack, destination), load_pack(path), composite_pack(image, pack, customization). Epoch clocks are injectable. Pack manifest v1 includes id/name/horizon/foreground relative PNG path; reject traversal, symlinks, nonfinite horizons, corrupt images and excessive assets. Owner-only atomic publication uses sibling temp files.

JavaScript module living.js owns pure sanitizeLiving(raw), seasonState(epochMs, latitude), advanceEnvironment(previous, snapshot, epochMs), rareMoments(epochMs, context), performancePolicy(flags), resolveSchedule(config, epochMs). State is bounded, location keyed, stale snapshots never accumulate, resume deltas capped, preview cannot persist. New shader uniforms flow through state.js/shader.js explicitly. Weather state uses atomic owner-only local state, no weather fetcher. Continuous uniforms interpolate; discrete materials switch without interpolating identifiers.

Scene additions: living normalized settings, selected pack metadata, optional preview marker/clock, environmental snow/wetness and season/event uniforms. Preview wins over schedules, explicit configured scene wins when scheduling disabled; existing automatic AI/theme behavior remains intact. Return to live removes preview and recomputes celestial state from the live clock.

## Exclusive ownership and tasks

1. Python worker: dynwall_living.py, test_living.py, packs/ and pack-authoring helper. Implement pack domain, real locally drawn sample pack, presets/customization/schedules/favorites/preview helpers. No edits to dynwall, dynwall_weather.py, settings, extension runtime or shaders. Regression-first validation, corrupt/path input, atomic failures, restart, midnight and priority tests.
2. JavaScript worker: extension/living.js, extension/weather.glsl, extension/shader.js, tests/renderer-living.test.mjs and additive rendering fixtures. Implement bounded environment/season/events/performance policy plus visible production shader effects. No edits to extension.js/state.js or settings. Deterministic clocks/randomness, hemispheres, reduced motion, multi-monitor/fullscreen/battery policy tests. Preserve existing leaves and celestial physics.
3. GTK worker: dynwall-settings and test_living_settings.py. Implement native import/export/select, customization/presets, preview scrubber/scenarios/return-live, favorites/schedule/rotation, persistence reset/off and performance/intensity controls. Preserve credentials and unknown config keys, atomic saves. Use domain API above; coordinate changes through integration lead. Capture native GTK evidence when permitted. No other shared file edits.
4. Integration lead: dynwall, dynwall_weather.py, extension/extension.js, extension/state.js, install.sh, README.md, tests/render_shader.py, docs verification. Wire every domain/control to actual fallback/native output, GNOME UPower/fullscreen/lifecycle behavior, safe environment persistence, preview cache watchers, custom foreground actors and rendering evidence.

## Execution and acceptance

Baseline: run system Python unittest discovery and Node tests before changes. Implement meaningful failing tests before behavior. Three workers share checkout, do not spawn children, preserve preexisting edits, no worktrees or commits. Route denied writes through harness approval; never bypass sandbox permissions.

Integrated checks: /usr/bin/python3 -m unittest discover -p test_*.py -q; node --test tests/*.test.mjs; isolated EGL production renders for customization, wet/snow, four seasons, each rare event, preview scenarios and sample pack; inspect screenshots. Native GTK screenshot and private GNOME smoke: env PATH=/usr/bin:/bin bash tests/smoke_gnome.sh /tmp/dynwall-living-UNIQUE. Independently review final scoped implementation, adjudicate and fix material findings once.

All eight acceptance gates require actual native controls and connected output. Check missing packs, malformed configs, owner-only atomic state, stale/different locations, bounded resume, preview exit without observation mutation, presets retaining credentials, hemisphere fixtures, sparse events/off/reduced-motion, fullscreen across monitors, UPower absence, midnight schedules and priority. Record exact evidence and remaining runtime gaps in docs/living-environment-verification.md. Stage installed files only when write permissions permit; never force GNOME restart. Disclose module cache/logout limitations honestly.

## Baseline evidence

2026-11-01: initial read-only run collected 65 Python tests; 36 errors due to no writable temporary directory. Node four test files passed (runner reports file-level counts). Baseline is permission-blocked, not product-failing. No implementation changes yet.

## Progress evidence

- Approved harness escalation succeeded for concrete checkout writes; unrestricted baseline: 65 Python tests and 34 Node tests passed. Initial sandbox-only errors were environmental.
- Original production EGL at 1280x720 passed, Quadro M6000/NVIDIA 580.178.04; baseline artifacts `/tmp/dynwall-living-baseline-20261101-012`. The 640x360 sampling attempt failed the existing rain-direction assertion, so standard resolution remains required.
- First private GNOME smoke passed with native UPower watcher/fullscreen query setup and GTK construction; artifacts `/tmp/dynwall-living-smoke-20261101-021`. This predates full living-feature integration.
- Root preview/material bridge regression tests RED then GREEN: synthetic weather remains separate, local preview clock/solar position, expired/disabled preview rejection, discrete terrain switches, authored-art preservation when schedules disabled, pack descriptor rejection.
- Three implementation workers own the agreed additive domains; root owns native/published/fallback integration.

## Final integration ledger

- Server restart cancelled initial workers; actual status was checked and only unfinished scopes restarted. Repeated child shell reads then stalled without output. Workers authored concrete implementation patches; root applied them through normal approved writes and ran tests centrally. No sandbox denial was bypassed.
- Python domain, original Woodland River pack, native GTK helper/controls, pure JS state/policy modules, actual production shader and runtime bridges are integrated. Shared config contracts are cross-runtime tested.
- Final tests:108 Python,62 Node; strict neutral legacy EGL comparisons and54 named production fixtures passed. Final private GNOME50 smoke `/tmp/dynwall-living-smoke-20261101-0849` exited0 with real GTK, persistence, preview/live, pack, schedules, power/fullscreen and lifecycle checks.
- Two independent scoped static reviews completed; all four material findings reproduced/fixed. Additional runtime repairs: GNOME50 St.ImageContent and system-Python executable entrypoint. See docs/living-environment-verification.md for evidence, supported limits, artifacts and staged-install manifest.
- All eight feature acceptance gates pass. Normal real-user logout/login remains unperformed and necessary for cached GNOME module discovery. No default/schedule was activated; ambient audio excluded.
