# Environment improvement verification — 2026-10-30

The wallpaper now combines low layered hills and mist with a clustered treeline,
smooth gradients, gentler cloud lighting and atmospheric sun/moon discs. Seasonal
leaves and precipitation remain in the foreground. Both GPU and static rendering
honor the landscape switch. The static vignette now preserves center brightness
instead of multiplying the whole image by the configured strength.

Art direction uses the user's custom prompt plus a single renderer contract,
actual canvas size, date and observations. Prompt/default-contract/canvas edits
invalidate cached art. Offline five-stop palettes evolve smoothly through local
day phases and take subtle northern-calendar autumn inspiration. These are
artistic choices, not a solar ephemeris or geographic terrain reconstruction.

Verification against the final source:

- **50 Python tests** and **33 JavaScript tests** pass, including RED/GREEN
  regressions for prompt edits, custom prompt context, offline palettes, static
  depth, one-pixel canvas support, landscape controls and static vignette lighting.
  Existing importlib/PyGObject deprecation warnings remain.
- The production GLSL passes NVIDIA EGL rendering at **3840×1080 Balanced** and
  **960×540 Low/High**. Checks cover terrain visibility and occlusion, static
  terrain under time changes, sky-only control, legacy omitted-uniform behavior,
  multi-monitor seams, cloud/star occlusion, precipitation and leaf wind direction.
  Landscape and legacy-controller tests failed before their implementations.
- The isolated GNOME 50 smoke test passes on two virtual monitors, including the
  real settings controls, GPU uniform uploads, landscape and seasonal switches,
  stacking, static-background refresh, desktop icons/context menu, display power,
  reduced motion and extension disable/re-enable.
- The compositor test initially reproduced delayed landscape disabling: its flag
  was being interpolated with weather. Uploading the landscape control directly
  from the current target fixes the delay; the same real test passes afterward.
- ShellCheck, shell syntax checks, `git diff --check` and scoped self-review pass.
  Review covered compatibility, static/GPU contracts, resource ownership,
  compositing order and preservation of user settings. No new dependencies,
  services, frame timers or weather requests were introduced.

Preview assets: [panorama](previews/environment-preview.jpg),
[animated gust](previews/environment-gust.gif),
[NVIDIA measurements and shader hash](previews/environment-measurements.json).
Balanced draw/finish medians across eleven fixtures were approximately 1.4–6.6 ms
at 3840×1080 on the Quadro M6000. These isolated timings exclude GNOME composition
and are not a sustained desktop FPS or power measurement.

Temporary full evidence:

- `/tmp/dynwall-environment-ultrawide/` and its sibling `.log`.
- `/tmp/dynwall-environment-low/`, `/tmp/dynwall-environment-high/` and their logs.
- `/tmp/dynwall-environment-gnome-green/` and its sibling `.log`.
- `/tmp/dynwall-depth-red/` and `/tmp/dynwall-depth-compat-red/` reproduce missing
  terrain and missing legacy-controller defaults; `/tmp/dynwall-environment-gnome/`
  reproduces the landscape-toggle delay.

Installed extension files were backed up and updated under the earlier reload
authorization. The static wallpaper was regenerated and applied; the extension
was disabled/re-enabled and independently read back as ACTIVE with no extension
errors. Configuration bytes match their backup: custom prompt, model, dimensions,
quality and FPS were preserved. Backup:
`~/.cache/dynwall/backups/environment-20261030-024755/`.

The current OpenAI art-direction request is rejected with HTTP 401 in the production
service log. Credentials were left untouched; the improved offline composition is
being used. API authentication is not claimed fixed. GNOME caches JS imports for
the session: the shader supports old controllers, but new JS controls and seasonal
logic require a fresh login. No forced logout, lock or suspend was performed.
