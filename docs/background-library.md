# Background library verification

This report describes the original scene-library implementation. For the current
landscape artwork, importer schema and fresh checks, see
[Landscape update verification](landscape-verification.md).

The scene library extends the existing procedural wallpaper and native GTK
settings. It preserves the weather, solar position, stars, precipitation and
seasonal effect paths. It adds explicit offline backgrounds and matching static
terrain: layered ridges, alpine peaks, dunes, ocean and open sky.

The scene selector precedes AI and seasonal art only when explicitly selected.
Automatic remains the default for existing configurations. Choosing a scene in
Settings and saving publishes its spec without an AI request or wallpaper URI
change; regeneration also rebuilds the static fallback.

## Checks

- `/usr/bin/python3 -m unittest discover -p 'test_*.py' -q`: 65 passed.
- `node --test tests/*.test.mjs`: 34 passed.
- Production shader rendered with isolated EGL at 1280×720, Balanced quality,
  on `Quadro M6000/PCIe/SSE2`, using three ten-frame timing samples per fixture.
  Day/dusk/night renders for every scene are included in the fixtures.
- Render assertions verify distinct terrain with the same palette, upper-sky
  preservation, still terrain in calm conditions and wind-driven ocean detail.
  Existing checks cover cloud shadows, mist, rain direction, snow advection,
  star twinkle, leaves and monitor continuity.
- A private GNOME 50 session exercised every scene code through the actual Cogl
  shader, scene-file replacement, two-monitor uniform uploads and settings
  selection. Existing desktop interaction, stacking and lifecycle checks passed.
- The final alpine shading uses spatially averaged face normals to avoid
  vertical lighting bands below peaks identified during independent review.

[Production-render gallery](previews/background-library.jpg) and
[EGL measurements](previews/background-measurements.json) are local artifacts.
The GTK picker uses JPEGs derived from these production renders. Preview weather
is illustrative; actual conditions continue to come from TopWeather.

## Runtime boundary

The local launchers already point to this checkout. The updated `state.js` and
`weather.glsl` were copied to the existing user extension directory and compared
byte-for-byte. GNOME caches imported modules: the user's current session needs
one normal logout/login to load the new scene mapping. Testing used a private
session and did not log out the user or change their selected wallpaper/config.

Built-in sky palettes follow local clock time, while the existing GPU celestial
placement uses available observation coordinates and day/night information.
Terrain and water are authored scenery, not a reconstruction of the location.
EGL timings exclude desktop compositor overhead.
