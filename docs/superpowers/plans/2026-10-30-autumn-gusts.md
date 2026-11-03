# Autumn gusts

Goal: implement the requested random autumn wind and blowing leaves inside the
existing GNOME GPU renderer. The user's request authorizes this local feature;
installation and activation are separate operations.

Use the existing JS/GLSL/Python architecture. Keep observed weather unchanged.
No additional weather calls, textures, actors, services or frame timers.

1. Add `extension/seasonal.js` and `tests/renderer-seasonal.test.mjs`.
   An injectable random source drives a bounded event clock advanced only by
   active animation seconds. First gust after 12–35 seconds; subsequent quiet
   intervals 90–240 seconds; gust lasts 10–18 seconds with soft attack/release.
   September–November north of the equator, March–May south; absent location
   uses the northern calendar. Wind direction follows weather when available.
   Disable resets the event, so re-enabling starts quietly. Tests prove timing,
   fade, direction, pause, invalid deltas and hemisphere boundaries before code.
2. Thread default-on `seasonal_effects` through CLI/settings config, scene writer,
   scene sanitizer and the settings switch. Test false round-trip and invalid
   inputs. Installer preflight includes the new runtime module.
3. Integrate the clock into `extension.js`'s existing frame callback. Add the
   decorative wind to cloud advection only; pass a dedicated leaf uniform to the
   production shader. Two bounded procedural depth layers render colored,
   rotating leaves with veins. Inactive effects skip all leaf shader work.
4. Extend the production EGL harness: visible leaves and motion, zero-strength
   equivalence, both wind directions, monitor continuity, and an animated preview.
   Run Python/Node suites and isolated GNOME smoke testing where available.
   Record actual renderer/timing and separate isolated results from live desktop.

Acceptance: occasional recognizable autumn leaves; gradual gust/fade; no replay
while paused; toggle persists; quiet/non-autumn rendering matches original;
continuous multi-monitor coordinates; prior weather and lifecycle tests pass.

Completed: all four tasks. Final evidence and operational boundaries are recorded
in `docs/autumn-gust-verification.md`. Self-review found no unresolved blocking
issues; installation/activation remain separate from this local implementation.
