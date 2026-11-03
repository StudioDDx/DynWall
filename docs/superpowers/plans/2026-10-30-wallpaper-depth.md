# Wallpaper depth and art direction

Goal: carry out the user's request to improve the entire wallpaper, building on
the approved autumn effects and preserving existing settings and user edits.

Design: a calm panoramic landscape with three low ridgelines, atmospheric mist,
gentler cloud lighting, broader celestial light, smoother gradients and richer
time-aware offline palettes. Keep the sky dominant and desktop icons readable.
Add a Landscape depth switch; preserve sky-only rendering when disabled. Seasonal
leaves remain foreground decoration, and observations remain authoritative.

Architecture: existing Python/Pillow fallback and JS/GLSL renderer; no new service,
downloaded assets, timers or dependencies. A bounded `landscape` art spec carries
style (`hills`/`none`), height (0.1–0.3), and mist (0–1). Both renderers honor the
landscape switch. The production GLSL remains shared with the EGL harness.

1. Prompt and palettes (`default_prompt.txt`, `dynwall`, `test_dynwall.py`).
   Write tests for richer deterministic day-phase palettes, date/canvas context,
   custom prompt plus renderer contract, effective-prompt cache invalidation,
   and embedded/file default agreement. Implement artistic instructions, a single
   engine contract appended to custom/default prompts, and smooth five-stop
   fallback palettes with light and landscape art direction. No paid test calls.
2. Landscape contract and static rendering (`dynwall_weather.py`, `dynwall`,
   `dynwall-settings`, `extension/state.js`, Python and JS tests).
   RED tests cover limits, disabled landscape, immutable specs, setting round-trip,
   and visible depth only near the lower edge of a small Pillow render. Implement
   three deterministic hills, matching controls and the settings switch.
3. GPU composition (`extension/weather.glsl`, renderer fixtures/harness).
   Add bounded lower-screen terrain/mist and atmospheric celestial lighting;
   keep precipitation/leaves in front. Tests prove visible depth below the skyline,
   transparent off control, opaque hills occluding celestial light, static terrain,
   all existing weather/leaf behaviors and continuous monitor coordinates.
   Produce day/dawn/dusk/night/weather previews, inspect actual rendered output,
   measure NVIDIA rendering at ultrawide and other quality modes as relevant.
4. Verify final Python/JS suites, shell checks and isolated GNOME settings,
   stacking and pause controls. Self-review runtime paths and preserve user config.
   Stage final extension files with a backup under the user's earlier reload
   authorization; refresh the scene without forcing logout or claiming hot-reload
   loaded cached JS. Record exact deployment/runtime limits and preview paths.

Acceptance: a visibly cohesive sky/landscape across daylight, twilight, night and
weather; useful offline output; custom creative prompts retain valid renderer
instructions; landscape off works in both renderers; no frame timer/service or
observed-weather changes. Installation does not imply new JS loaded in live Shell.

Completed: all four implementation/verification stages. The final result and
runtime limits are recorded in `docs/environment-verification.md`. A reproduced
static-vignette dimming defect and a compositor-tested control delay were repaired
within this visual pass. Production AI authentication returns HTTP 401; credentials
and the configured model were preserved and the offline composition is active.
