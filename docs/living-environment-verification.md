# Living environment verification — 2026-11-01

All eight approved features are implemented and connected to native controls and production rendering. Ambient audio was excluded. The existing uncommitted checkout was preserved; no commit, push, new service, forced logout, or unrelated desktop preference change was made.

## Acceptance

| Feature | Result | Evidence |
| --- | --- | --- |
| Custom landscape packs | Pass | Bounded versioned manifest, safe folder/ZIP import/export, traversal/symlink/corruption/failure tests, original Woodland River PNG, actual GNOME 50 foreground actor and EGL/Pillow composition |
| Persistent weather | Pass | Artistic snow/wetness, puddles, drying/melting; atomic 0600 state; stale/new-location reset; bounded resume; actual extension restart, reset and off tests |
| Preview scrubber | Pass | Native hour slider and six scenarios; asynchronous real thumbnail; unsaved selections; immediate preview/Return to live; no observation or environmental-state mutation |
| Customization and presets | Pass | Horizon, terrain scale, mist, warmth, darkness and animation intensity reach output; finite/clamped values; named preset save/load preserves credentials and unrelated config; saving a preset cannot activate an unsaved schedule |
| Seasonal scenery | Pass | Continuous hemisphere-aware seasonal weights; spring/summer foliage, autumn color/leaf loss, winter branches; existing seasonal/leaf toggle retained; four production captures |
| Atmospheric moments | Pass | Deterministic sparse shooting stars, distant lightning, fireflies, pollen and birds; contextual selection, intensity/off, reduced motion; all five effects rendered and inspected |
| Performance | Pass | Actual UPower subscription and Mutter monitor-fullscreen API, per-monitor shader suppression, all-monitor pause/resume, battery frame/quality reduction, existing lifecycle cleanup; honest configured-workload controls |
| Favorites and schedules | Pass | Native collection/editing, local-clock entries, midnight wrap, bounded favorite rotation, preview priority, Automatic-art precedence, discrete material selection and gradual palette changes; actual native schedule selection |

## Final checks

- `/usr/bin/python3 -m unittest discover -p 'test_*.py' -q`: **108 passed**. [Log](previews/living/python-tests.log).
- `node --test tests/*.test.mjs`: **62 passed**. [Log](previews/living/node-tests.log).
- `git diff --check`: passed.
- Production EGL: `env PATH=/usr/bin:/bin /usr/bin/python3 tests/render_shader.py --output /tmp/dynwall-living-render-20261101-0848 --width 1280 --height 720 --timing-runs 3 --reference-dir /tmp/dynwall-installed-baseline-20261101-0840`: passed. This compiled the exact final `extension/weather.glsl` and rendered 54 named scene/effect fixtures plus the existing derived physics/monitor checks. Every legacy reference capture matched byte-for-byte with added uniforms neutral.
- `env PATH=/usr/bin:/bin bash tests/smoke_gnome.sh /tmp/dynwall-living-smoke-20261101-0849`: **exit 0**. Actual private GNOME 50 drawing, application stacking, two-monitor fullscreen, display power, reduced motion, disable/re-enable, desktop icons/context menu, native packs, surface restart/reset/off, preview isolation/exit, schedules, battery policy and real GTK controls passed. Extension errors were empty before and after re-enable.
- Actual installed entrypoint `~/.local/bin/dynwall --preview-output …` passed with isolated XDG paths and the normal Linuxbrew-first PATH. A discovered missing-Pillow launch failure was fixed by using `/usr/bin/python3` in the executable's shebang; a poisoned-PATH regression covers it. Existing timer and settings launch paths now use that verified runtime.

The first temporary baseline images were lost during the server restart. The reference was regenerated from the unchanged installed 16,139-byte pre-feature shader before installed staging. Its source is retained as [baseline-weather.glsl](previews/living/baseline-weather.glsl), with [baseline measurements](previews/living/baseline-measurements.json). Reproduction can use `--shader docs/previews/living/baseline-weather.glsl --baseline-only` to regenerate that reference. The old 640×360 sampling attempt failed an existing rain-direction assertion; acceptance uses the standard 1280×720 harness.

## Artifacts

- [Feature overview](previews/living/overview.png)
- [Actual production sky plus Woodland River](previews/living/pack-woodland-production.png)
- [All five rare moments, active regions](previews/living/rare-moments.png)
- [Wet terrain](previews/living/living-wet.png), [accumulated snow](previews/living/living-accumulated-snow.png)
- [Winter](previews/living/living-winter.png), [spring](previews/living/living-spring.png), [summer](previews/living/living-summer.png), [autumn](previews/living/living-autumn.png)
- [Native GTK preview controls](previews/living/native-settings-living-preview.png), [customization/presets](previews/living/native-settings-living-customization.png), [favorites/schedules](previews/living/native-settings-living-schedules.png)
- [Actual native spanned pack](previews/living/native-living-woodland.png), [native snow preview](previews/living/native-living-snow-preview.png)
- [Production measurements](previews/living/measurements.json) and [native state evidence](previews/living/native/).

The renderer was Quadro M6000/NVIDIA 580.178.04. Timings are repeated offscreen GL draw/finish samples at 1280×720 under host load, not GNOME compositor-wide frame timings or GPU utilization. Runtime `_frameCpuMs` is CPU submission duration only. The settings display configured FPS/quality rather than invented GPU telemetry.

## Supported behavior and use

Open `dynwall-settings`. Scroll to Custom landscapes to select Woodland River or import a local folder/ZIP. Save applies the selection; importing validates and canonicalizes assets and refreshes the catalog without activating a new default. Opaque photographs are cut above their marked horizon; transparent illustrations retain treetops. See [the pack format](../packs/README.md). Foregrounds span the full monitor bounds; panoramic source artwork avoids stretching.

The customization group saves named combinations of scene, pack and controls. Save preset persists the preset without applying other unsaved settings. Load restores controls; Save applies them. Favorites likewise remain local until saved. Schedules are disabled by default. Timed entries take priority over rotation; clear entries to rotate saved favorites. Rotation is off at zero and otherwise has a five-minute minimum. Native selection refreshes within the existing 15-second read interval. Static fallback follows the existing timer/manual invocation.

Preview is explicitly temporary. Choose the hour/scenario, press Preview, and use Return to live when finished. The picture is an illustrative offline Pillow still; the desktop uses the actual animated production shader. Hour 24 means next local midnight. Invalid or expired requests leave live presentation intact. Requests expire after two hours, and normal settings-window close removes them. Preview solar positions are an illustrative local-hour composition; live solar calculation resumes from real coordinates/time immediately. No synthetic snapshot is written into TopWeather or persisted environmental history.

Persistent snow and wetness are normalized artistic coverage, not measured snow depth or water levels. Only fresh supported observations drive accumulation; known condition codes provide explicitly artistic fallback when measured rates are absent, and a measured zero wins. Celsius/Fahrenheit temperatures are handled consistently for melting. Each integration step is capped at one minute; stale/missing observations and changed locations reset coverage rather than replay old precipitation. Reset/off clears accumulated state. Files use XDG paths and owner-only atomic publication.

Procedural built-in terrain receives snow/wet surfaces and seasonal foliage. Custom foregrounds retain their authored pixels, with animated weather/celestial sky behind them and common composition/preview controls. Dynamic surface/foliage and rare moments require the native extension; Pillow supplies the static counterpart and illustrative preview. This is not a promise of animated seasonal recoloring of arbitrary photographs.

Battery saver caps native work at 15 FPS/low quality. Unknown/absent UPower safely retains configured work. Covered monitors stop shader uploads; covering every monitor stops the frame source. Lock/suspend/display-off/reduced-motion and cleanup retain the existing lifecycle behavior. Battery input was injected only inside the private test extension; the host's physical battery state was not changed. Real host lock, suspend and login were not triggered.

## Independent review and repairs

Two new independent scoped static reviews were performed: completed Python/CLI domain, then completed native/GTK/shader integration. Child shell calls repeatedly stalled without output; the reviewers used transferred source and explicitly made no runtime-test claim. The integration lead executed the decisive reproductions and fixes:

1. Optional `landscape: null/list/string` crashed the new static customization path. A failing regression reproduced it; normalization fixed it.
2. CLI/domain/native preview validation disagreed, including hour 24 and huge timestamps. Failing metadata and actual-image CLI regressions now pass under one strict contract.
3. Preview values lingered in current shader uniforms after mode changes. Actual GNOME failure showed current snow 0.248 versus target 0.393 after eight seconds. Mode-identity changes now reset interpolation; native preview and Return to live assertions pass immediately.
4. Fractional rotation 0.5 differed between Python and JavaScript. The failing cross-runtime test now passes with rotation disabled consistently.

Native runtime verification also found removed `Clutter.Image`; the pack compositor now uses the installed GNOME 50 `St.ImageContent.set_bytes` API and actual Cogl context. The fullscreen test's actor-order assumption and GVariant parsing were corrected from actual diagnostic evidence. All final feature gates were rerun after the relevant fixes. Puddles/tree spacing were visually inspected and softened; final production renders were regenerated and inspected.

## Installation and session limits

Installed staging completed: all 11 extension files independently matched source SHA-256 hashes. The backup is `/home/rucaradio/.local/state/dynwall-upgrades/20261101T033152-living-environment`. Exact paths and hashes are recorded in [staging.json](previews/living/staging.json). The launchers already point at this checkout. No real user configuration, default scene, schedule enablement, service setup, or desktop preference was changed by verification/staging.

GNOME caches extension modules. A normal user logout/login is still needed to ensure the real desktop loads the updated modules. The fresh private session proved the integrated version; a fresh real-user session has not been exercised. Private screenshots contain deliberately magenta test windows and may show the private test-instrumentation unsafe-mode notification; this was confined to the throwaway bus/session.
