# Autumn gust verification — 2026-10-30

Implemented occasional seasonal gusts, two depths of procedural tumbling leaves,
decorative cloud acceleration, and a persistent Seasonal effects switch. Events
run entirely inside the existing animation clock and never rewrite observations.

Checks against the final implementation:

- 40 Python tests and 32 JavaScript tests pass. New cases cover event timing,
  recurrence, fade, hemisphere, paused/invalid time, direction stability, config
  round-trip and the scene setting. Existing importlib/PyGObject deprecation
  warnings remain.
- Production GLSL compiles and renders on the Quadro M6000 with NVIDIA 580.178.04.
  Balanced at 3840×1080 and low/high at 960×540 pass leaf visibility, motion,
  both wind directions, zero-strength transparency and monitor continuity checks.
- All 11 original reference PNGs at 960×540 match the pre-feature shader byte for
  byte when the effect is inactive. The new branch does not change quiet skies.
- `tests/smoke_gnome.sh` passes in an isolated GNOME 50 session with two virtual
  monitors: actual effect uploads to both actors, atomic seasonal disable while
  ordinary weather continues, unchanged observed cloud cover, settings widget
  collection, application stacking, desktop icons/context menu, display power,
  reduced motion and extension disable/re-enable.
- Self-review checked scene compatibility, resource ownership, weather separation,
  installer packaging and pause behavior. No additional actors or timers were
  introduced. ShellCheck, shell syntax checks and `git diff --check` pass.

Artifacts: [animated preview](previews/autumn-gust.gif),
[still preview](previews/autumn-gust.png),
[NVIDIA measurements](previews/autumn-gust-measurements.json).
The preview isolates leaves against a clear sky. The recorded gust timing measures
that isolated clear-sky effect, not total compositor work or live desktop FPS.

Full temporary evidence:

- `/tmp/dynwall-autumn-baseline/` — pre-feature render references.
- `/tmp/dynwall-autumn-pointed/` — final shader, 960×540 preview and checks.
- `/tmp/dynwall-autumn-ultrawide/` — final shader, 3840×1080 checks.
- `/tmp/dynwall-autumn-low/` and `/tmp/dynwall-autumn-high/` — other quality modes.
- `/tmp/dynwall-autumn-gnome-rerun/` and its sibling `.log` — compositor evidence.

The first compositor run stopped because the default `python3` lacked Pillow;
the successful run used `env PATH="/usr/bin:/bin:$PATH" bash tests/smoke_gnome.sh`
so its subprocesses used the application's system Python. Headless portal,
PipeWire and session-service shutdown warnings are in the log; the harness exits 0.

No live-session extension files were installed or reloaded. To load this version,
run `./install.sh --no-render`, log out/in, and enable `dynwall@rucaradio` if needed.
Real lock/suspend cycles, physical hotplug and sustained desktop power remain
outside this isolated verification.
