# GPU weather verification — 2026-09-12

## Quality-preserving efficiency follow-up

The follow-up keeps the configured quality, FPS, resolution, cloud detail and
weather behavior intact. It does not add another weather fetch loop.

- `UniformUploadCache` compares the exact float32 values sent to Cogl and skips
  unchanged uploads, while retaining private copies of caller-owned arrays.
  `node tests/benchmark_uniforms.mjs` records **1,252** uploads instead of
  **16,800** over 300 steady-scene frames on two monitors: **92.55% fewer uniform
  uploads**. This is an actual cache-decision count, not a measured GPU-time or
  power reduction.
- Uniform interpolation reuses immutable steady states and unchanged vectors
  instead of allocating a new scene each frame. A 100,000-frame Node microbenchmark
  measured 232.99 ms before versus 1.02 ms after for the steady-state interpolation
  alone. This is not whole-frame timing. The numeric results matched the original
  implementation across 10,000 deterministic cases, including zero elapsed time,
  changing vectors and removed fields; independent review repeated 10,000 cases.
- An asynchronous DisplayConfig proxy stops the animation source when global
  display power mode is standby/suspend/off (1/2/3), and resumes when powered on.
  Unknown, unsupported and unavailable state leaves animation enabled. Proxy
  initialization is asynchronous because Mutter and Shell share a D-Bus owner;
  a synchronous call could deadlock the compositor.
- **No fullscreen/maximized-window shortcut:** GNOME 50 does not expose a reliable
  per-pixel opacity predicate. Freezing or hiding weather behind a transparent
  fullscreen application would visibly change functionality. This unsafe shortcut
  was deliberately rejected. Hardware power-button detection per monitor is also
  not claimed.

Final combined verification: `/tmp/dynwall-final-20260912-172215/`, exit 0.
The private GNOME 50 compositor passed application stacking, background refresh,
scene and extension disable/re-enable, display-off/on pause/resume, real desktop
file visibility and a real secondary-click popup. The helper found **4,150**
localized file-icon pixels and **67,042** menu pixels over the weather. A private
runtime mutation restoring the bad parent correctly failed with an invisible
desktop fixture (`/tmp/dynwall-desktop-red-run.LpBpdY`).

The DING test uses a private installed copy: upstream DING startup cleans up
processes matching its installation path. An early prototype using the system
path briefly restarted the login-session DING; the corrected isolated runs use
their own path and leave it alone. Virtual-pointer startup is also settled away
from the hot corner before testing, to avoid accidentally opening Activities.

Final tests: **33 Python**, **26 JavaScript**, shell syntax/ShellCheck and
`git diff --check` passed. EGL reference comparison passed again in
`/tmp/dynwall-gpu-parent-final/`: seven weather fixtures, zero-strength controls
and split-monitor images match the pre-optimization shader **byte for byte**.
Only stars-at-zero and grain-at-zero shader guards were retained. Alternating
baseline/optimized EGL timing runs showed modest daytime median reductions of
roughly 0.09–0.12 ms, with noisy/unchanged night timings; no broad GPU-utilization,
live-desktop FPS or power-saving percentage is claimed. Repeated timing samples
and their medians are recorded in the efficiency preview artifacts.

## Follow-up: wallpaper covering windows and desktop icons

The original smoke test rendered an empty desktop, so it missed a real stacking
regression. The installed extension was active when the problem was reported;
the retired player was disabled and not running.

Reproduction in a fresh private GNOME 50 session opened two actual GTK/Wayland
windows after starting the weather renderer. Both received focus, but the weather
actor painted above them. The screenshot contained **zero** visible pixels of
their distinctive magenta content. This also explains why desktop windows/icons
and their menus can disappear while the Shell dock remains visible.

The weather group now lives **inside** `Main.layoutManager._backgroundGroup`,
not as a direct sibling of application windows in `global.window_group`. This
keeps it under windows when Mutter restacks them, without changing input handling,
patching the window manager, or altering the weather shader.

The expanded `tests/smoke_gnome.sh` checks actual paint order after application
mapping, raising, scene recreation, static-background replacement, and extension
disable/re-enable. It also verifies visible application screenshot pixels and
that static-background replacement does not cover the weather. The original
code failed this test; the fix passed in fresh isolated sessions. Python **32**
tests and JavaScript **18** tests also passed again.

Evidence from this follow-up:
- Before: `/tmp/dynwall-stacking-red-20260912-170459/`.
- After: `/tmp/dynwall-stacking-green-20260912-170526/` — **326,105** visible
  application-content pixels instead of zero.
- Including static-background refresh: `/tmp/dynwall-stacking-refresh-20260912-170638/`.
- Pre-fix installed-extension backup and minimal patch:
  `~/.cache/dynwall/backups/stacking-20260912-170703/`.

These are isolated-compositor results, not a claim that the updated module has
already loaded in the user's running Shell. The extension was disabled there to
remove the obstructing renderer without restarting or logging out the session.
The corrected `extension.js` is installed and matches the tested source
(`23a0273f4e26e2f14aa4c857ea229ad3f30304b333832131763640e22e2cec55`,
including the subsequent efficiency changes).
The static wallpaper timer and Desktop Icons NG remain active. The extension is
intentionally still disabled: **log out and back in, then run**
`gnome-extensions enable dynwall@rucaradio` to load the fix and resume animation.
Enabling it before logging out would run GNOME's cached, pre-fix module.

Source confirmation against matching installed package versions:
- Mutter 50.1 `src/compositor/compositor.c:577-639`: restacking lowers window
  actors and recognized background groups, leaving arbitrary sibling actors
  under the plugin's responsibility.
- GNOME Shell 50.1 `js/ui/shellDBus.js:489-493`: `ReloadExtension` returns
  `NOT_SUPPORTED`; `js/ui/extensionSystem.js:401-528` documents module caching.
- Installed DING `emulateX11WindowType.js:228-249` lowers its desktop window;
  `app/desktopManager.js:680-697` opens its GTK right-click menu. The weather
  actors are nonreactive, so the demonstrated fault is visual occlusion rather
  than a pointer grab.

## Verified build and behavior

- Python: `/usr/bin/python3 -m unittest discover -p 'test_*.py' -v` — **32 tests pass**.
- Renderer JS: `node --test tests/*.test.mjs` — **18 tests pass**.
- TopWeather: `./tests/run.sh` — **71 assertions pass**, plus incomplete-package installer regression.
- Both repositories pass `git diff --check`; shell/JS syntax and TopWeather schema compilation pass.
- Existing importlib/PyGObject deprecation warnings are not suppressed; they did not fail tests.

## Actual NVIDIA rendering

```bash
/usr/bin/python3 tests/render_shader.py --device 0 --width 3840 --height 1080 \
  --output /tmp/dynwall-shader-nvidia
```

Renderer: **Quadro M6000**, OpenGL 4.6, NVIDIA 580.178.04. Balanced full-canvas
shader draw/finish costs roughly **3–5 ms/frame** in the isolated EGL harness.
This excludes GNOME compositor overhead and is **not** a measured live-desktop
frame-rate or power guarantee. Default frame cap is 30 FPS.

The harness runs the exact production shader, not a reimplementation. It checks:
- Animated cloud changes with stars/grain/glow/drift disabled; clear control stays static.
- Precipitation visibility with otherwise identical scene uniforms.
- Falling rain trajectory agrees with positive and negative horizontal wind.
- Clouds occlude stars (clear vs overcast star-signal comparison).
- Rendering two adjacent monitor partitions agrees with one continuous canvas.

Persistent artifacts: `docs/previews/weather-preview.jpg` and
`docs/previews/gpu-measurements.json` (includes the shader SHA-256).

## Actual GNOME Shell integration, isolated from the user's desktop

```bash
./tests/smoke_gnome.sh /tmp/dynwall-gnome-smoke-final
```

The harness creates a private HOME/config/data/runtime, a private D-Bus session,
and a headless GNOME 50 Wayland compositor with **two 1920×1080 virtual monitors**.
It temporarily installs a test-only debug helper into that private session for
state inspection/screenshots. It does not enable unsafe mode on the user's Shell.
All test processes are stopped at completion. Use a fresh output directory each run.

Verified on the final package:
- Both monitor actors actually draw the shader behind GNOME UI (screenshot captured).
- Reduced-motion setting stops the frame source and hides the effect; restoring it resumes.
- Atomic scene disable removes the actors; atomic re-enable restores them.
- Expired weather clears cloud coverage; a fresh snapshot restores observed coverage.
- Extension disable removes the actor group; re-enable succeeds without extension errors.
- The real GTK settings window constructs and collects the new FPS/quality controls.

This caught and fixed a real WATCH_MOVES bug: Gio's same-directory atomic rename
supplies the destination as `other_file`; checking only the old temporary filename
missed scene/weather updates, including re-enable while the frame timer was stopped.
The corrected implementation checks both filenames.

## Actual current-weather boundary

Used the updated TopWeather fetch/parser/export code with its installed settings,
not a separate IP-located weather endpoint. One successful response reported wttr
code **302 / Moderate rain**, **100% cloud cover**, wind **14 km/h from 232°**.
The exported snapshot was accepted by Dynwall's Python validator and mapped by the
production JS to overcast + rain, with no snow. The rain intensity is explicitly a
visual preset: wttr's amount has an unspecified period, so no mm/hour was invented.
These are observations at verification time, not a permanent statement of weather.

## Review fixes

Independent review led to fixes for wind/rain direction, freezing-rain mapping,
stale sun/moon type, atomic file events, settings scene-writer races, superseded
TopWeather fetches/alerts, precipitation provenance and installer preflight/staging.
All identified blocking findings were re-reviewed and closed.

## Not verified / operational boundaries

- Physical monitor hotplug and fractional-scale combinations.
- Real lock/unlock and suspend/resume cycles (handlers are implemented; no disruptive
  user-session lock/suspend was performed).
- Sustained live-desktop frame rate, power use, gaming interaction, or all other GNOME versions.
- The fallback moon is stylized, not a physical ephemeris; clouds are procedural and
  stars are not a catalogue. Solar positioning is approximate, not observatory-grade.
- GNOME imports extension modules once per session. Updated TopWeather and a newly
  installed Dynwall extension may require **one logout/login**; no forced restart.

Rollback: `gnome-extensions disable dynwall@rucaradio` immediately exposes the
existing static wallpaper. The 30-minute fallback timer remains independent.

## Original installation handoff (before the stacking fix above)

Reviewed files were copied back into `/home/rucaradio/dynwall` and
`/home/rucaradio/topweather` only after confirming their original worktrees had
not changed during implementation. Preexisting Dynwall changes were retained.
Installed extension modules match their reviewed source byte-for-byte.

Both installers ran successfully. Dynwall is configured for Balanced / 30 FPS,
with the existing mesh-off preference retained; the retired player is disabled
and the fallback timer remains active. A successful fetch using TopWeather's
installed location/provider settings seeded the first private weather snapshot.
Dynwall was appended to (not substituted for) the existing enabled-extension list.

**The active user Shell has not discovered the new Dynwall extension yet.** One
logout/login is still required to load it and the updated TopWeather publisher.
No user-session logout, restart, lock or suspend was initiated. A configured
startup entry is not evidence of currently running animation.

Rollback copies of prior configuration, installed TopWeather, systemd units and
the preexisting user diff are in:
`~/.cache/dynwall/backups/weather-20260912-163723/`.
Changes remain uncommitted; nothing was pushed.
# Halloween themes and general weather lighting — October 30, 2026

The `halloween` theme now selects Hollow Harvest by day and Witching Hour at
night, using a fresh TopWeather `isNight` observation or local 07:00–18:00
daytime fallback. A local-date cutoff stops selection on November 1. The CLI,
scene refresh and settings saves retain the selection; preset rendering never
requires an AI request. Previous user settings, scene and installed shader are
saved in `~/.config/dynwall/before-halloween-20261030-030800/`.

General shader improvements use existing uniforms: wind-integrated cloud
advection, projected soft cloud shadows, slope lighting, slower ground mist,
independent stellar scintillation, and continuous wind displacement for snow.
The effects are stylized visual approximations. They retain the reported
weather and work with every palette, beyond the Halloween cutoff.

Verification on the final implementation:

- 60 Python tests and 33 Node tests passed. Python emitted the existing
  `load_module` and PyGObject deprecation warnings.
- Production GLSL compiled and rendered on **Quadro M6000**, NVIDIA 580.178.04,
  at low, balanced and high quality. Balanced 3840×1080 fixture medians ranged
  up to 5.9 ms; Halloween day/night were 5.02/5.42 ms. These are isolated EGL
  frame timings, excluding GNOME compositor overhead.
- Isolated pixel checks establish calm-cloud stability, moving terrain shadows
  with mist disabled, mist movement with clouds disabled, stationary bare hills,
  continuous snowfall when wind readings change, wind-sensitive star twinkle,
  cloud occlusion, rain/leaf direction and multi-monitor continuity.
- The private GNOME 50 session passed drawing, pause/resume, disable/re-enable,
  real window stacking, desktop icon visibility and secondary-click menu checks.
  Run it with `env PATH=/usr/bin:/bin bash tests/smoke_gnome.sh OUTPUT_DIR` here;
  the shell's alternate Python lacks Pillow. The first run stopped at that
  screenshot-check prerequisite; the system-Python rerun passed completely.
- Only the installed GLSL file was replaced, with a saved copy for rollback;
  disabling and re-enabling the extension reread it without changing JavaScript
  modules. Installed bytes match the tested source. The login session reports
  **ACTIVE**, with no new Dynwall/shader errors in the user journal.
- Direct login-desktop screenshot access is denied by GNOME. Visual validation
  used GPU previews and the isolated compositor, not a captured user desktop.

[Day/night preview](previews/halloween-day-night.jpg) and
[GPU measurements](previews/halloween-physics-measurements.json).
