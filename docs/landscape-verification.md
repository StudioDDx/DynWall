# Landscape update verification

## Result

Smoky Mountain Ridges replaces the old three smooth bands with five overlapping
ranges, small erosion folds, blue atmospheric distance, wooded contours and
wind-driven valley mist. The existing `ridges` selection key is retained.
Seasonal scenery replaces the repeated fork symbol with tapered branching,
overlapping leaf clusters, irregular groves and conifers. Winter exposes the
branching; accumulated snow catches crown edges and pine boughs. Shapes remain
anchored across the continuous virtual desktop.

Alpine gains layered rock faces, snow gullies and a broken snowline. Dunes gain
curved fine ripples, slope shading and sand grain. Ocean gains crossing swells,
perspective wavelets, deeper water color and broken light reflections. The
static Pillow fallback also gains five depth-separated layers and scene-specific
surface detail. It is an illustrative still, not an exact GPU frame.

The sky palette, solar placement, clouds, rain, falling snow, seasonal leaf
particles and weather inputs are unchanged. No new artwork downloads or runtime
dependencies are required. Open Sky remains the original sky-only renderer.
The settings thumbnails are freshly rendered production GLSL, not mockups.

[Before/after landscape detail](previews/landscape-before-after.jpg) ·
[Smokies-inspired autumn panorama](previews/smokies-autumn.jpg) ·
[Day/dusk/night gallery](previews/background-library.jpg)

## Importer and schema findings

The checked-in UI has **Custom landscapes → Import folder / Import ZIP**, not a
separate complete-scene importer. It accepts foreground packs with a v1 manifest
and a PNG. An AI art-direction spec and generated `scene.json` are different
formats; putting their fields into a manifest does not create weather or shaders.
The [pack instructions](../packs/README.md) now state that boundary and the exact
Import → Preview → Save workflow. The machine-readable contract is
[manifest.schema.json](../packs/manifest.schema.json).

The importer previously ignored unknown fields and invalid optional metadata,
accepted ambiguous duplicate JSON fields and ZIP path aliases, and silently used
the first frame of an animated PNG. Validation now rejects those inputs before
publication. Nested extra manifests are rejected, hidden import staging folders
are not catalogued, and native/Python PNG path handling agrees. The schema and
runtime agree on integral numeric version `1`, including JSON `1.0`, but reject
booleans and strings. Transparent authored cutouts survive import; opaque photos
already correctly cut out the sky above the declared horizon, and that behavior
is retained. Valid existing v1 packs still import and export normally.

## Checks

- 105 non-GUI Python tests passed, including static scenes, pack import/export,
  malformed archives, preview contracts, controller bridge and installer checks.
- 66 Node renderer tests passed.
- The complete weather EGL harness passed at 1280×720, Balanced quality. It
  covers cloud shadow/mist motion, rain and leaf direction, snow advection,
  star twinkle/occlusion and monitor continuity.
- A focused final production-shader run at 1920×540 rendered 16 day/dusk/night
  and seasonal fixtures. All 16 upper-60%-sky crops matched the pre-change shader
  byte-for-byte. All 13 non-ocean scenes stayed stationary with weather motion
  disabled. Both monitor partitions of every fixture matched; the largest mean
  per-channel difference was below 0.00007 on the 0–255 scale.
- The JSON Schema was checked against the runtime validator using valid and
  invalid boundary cases. Image bytes, archive limits and symlinks are checked
  by the importer in addition to the portable JSON structure.

[Landscape measurements](previews/landscape-measurements.json) ·
[Weather measurements](previews/landscape-weather-measurements.json)

Rendering here used Mesa llvmpipe (software OpenGL). EGL timings are not desktop
FPS or hardware-GPU measurements. The current environment lacks the GTK 4
namespace, so the two GUI test groups and a real GNOME session were not exercised.
No user's wallpaper, settings, services or installed extensions were changed.

## Reproduce

```sh
/usr/bin/python3 -m unittest test_dynwall test_backgrounds test_ding_menu \
  test_integration.CliTests test_integration.InstallerTests test_living \
  test_living_bridge test_preview_contract test_themes test_weather
node --test tests/renderer-*.test.mjs
EGL_PLATFORM=surfaceless python3 tests/render_shader.py \
  --width 1280 --height 720 --timing-runs 3 --output /tmp/dynwall-weather
EGL_PLATFORM=surfaceless python3 tests/render_landscapes.py \
  --width 1920 --height 540 --output /tmp/dynwall-landscapes
```

For a sky comparison, render the old shader with `--shader /path/to/old.glsl`
into a separate directory, then add `--reference-dir /path/to/baseline` to the
focused final run. The focused harness saves its exact shader and SHA-256.
Install through the existing `install.sh`; reload the installed extension to
pick up GLSL changes. A normal GNOME logout/login loads changed JS modules.
