# Dynwall native renderer

GNOME Shell 50 extension, UUID `dynwall@rucaradio`. Install this directory as a unit. Installation and activation are separate; see the repository README.

## Rendering and ownership

- `weather.glsl` is the actual production fragment shader, shared verbatim with the isolated EGL harness. Layered procedural cloud density, directional lighting, rain, snow, stars and celestial light all run on the GPU. No video player, downloads, textures or picture-URI animation.
- Nonreactive monitor actors live inside GNOME's background group, above its static backgrounds and below desktop windows/icons. They must not be direct siblings of application windows: Mutter can restack those windows below arbitrary non-window siblings. Logical monitor offsets use one continuous virtual canvas, including negative origins. Physical monitor layout/hotplug still needs compositor validation.
- Low/balanced/high use 1/2/3 cloud layers and 4/5/6 noise octaves. The controller defaults to balanced at 30 FPS; accepted FPS is 15–60. Idle-priority frame callbacks do not accumulate missed frames.
- Disable and JavaScript errors release actors, frame/idle sources, file monitors and signal handlers. Lock, suspend, overview and disabled desktop animations stop the frame source and reveal the original static wallpaper. The extension does not change GNOME background settings.
- Global display standby/suspend/off also stops frame scheduling, using an asynchronous Mutter DisplayConfig proxy; unknown power state keeps rendering. Transparent fullscreen applications retain animation: fullscreen alone is not proof that the background is invisible.
- Unchanged float32 uniforms are not uploaded repeatedly, and steady scene interpolation reuses immutable state. Zero-strength stars and grain skip their shader work. These optimizations retain the configured FPS, resolution and cloud detail.

## Inputs and interpretation

`spec.landscape` controls five static panoramic ridges, a clustered treeline and
atmospheric color separation near the bottom of the canvas. `u_landscape` carries
enabled/height/mist; defaults are `[1, .2, .5]`, height is bounded to .1–.3, and
mist to 0–1. The scene writer maps `landscape_enabled: false` to `style: "none"`.
The renderer applies this control immediately rather than interpolating its
enabled flag through the slower weather transition. Rain, snow and leaves render
in front of terrain; celestial discs remain behind it. Terrain uses continuous
canvas coordinates and never follows wind or frame time.

Already-imported older controllers leave the new uniform zeroed. The shader
treats that absent-height value as the default landscape, while an explicit
`[0, .2, .5]` still disables terrain. This preserves the visual upgrade when only
the shader can reload; the new JS/settings controls require their updated modules.

`renderer.seasonalEffects` defaults to true and controls the autumn event clock
in `seasonal.js`. The clock advances from the existing active frame delta, so
lock, overview, reduced motion and display sleep also pause events. It has no
timer of its own. Disabling seasonal effects resets the clock; re-enabling starts
quietly. Events use the local calendar and the live snapshot's hemisphere, with
a northern-calendar fallback when location is missing. They never modify weather
observations: the gust adds only decorative cloud advection and a dedicated
`u_leaves` uniform. Two procedural leaf layers share the continuous monitor canvas;
zero-strength gusts skip leaf rendering. No seasonal texture downloads are needed.

`$XDG_CACHE_HOME/dynwall/scene.json` supplies schema version 1, art-directed `spec`, and `renderer`. `$XDG_CACHE_HOME/topweather/current.json` supplies the live snapshot. Missing/invalid/older-than-two-hour weather does **not** fall back to the embedded scene snapshot, so changing location cannot resurrect an invalidated observation.

The gradient, glow, grain, mesh and optional celestial design remain controller-owned. Missing celestial artwork gets a decorative sun/moon; fresh coordinates use an approximate solar ephemeris without fixed clock-hour or timezone assumptions. Reported `isNight` is a fallback when coordinates are unknown. Solar lighting, star visibility, and sun/moon type override stale day/night artwork while preserving explicit disc position/size; the palette itself is not rewritten. Moon position/phase are decorative, not astronomical claims.

Cloud coverage is observed percent. Wind is converted from km/h and meteorological FROM direction. Rain and snow use exported canonical rates when available. When rates are unavailable, known `wttr` or `openmeteo` condition codes can select a **visual particle preset**, not an invented measurement; explicit zero rates win. Freezing drizzle/rain use liquid streaks; snow, sleet and ice-pellet condition codes share a solid-particle visual preset. Unknown providers do not get WMO code interpretation. Total precipitation is never assumed to be rain, and snow depth is never assumed to be water equivalent.

## Reproduction without enabling GNOME extensions

```sh
node --test tests/renderer-*.test.mjs
python3 tests/render_shader.py --device 0 --width 3840 --height 1080 \
  --output /tmp/dynwall-shader-nvidia
# Also exercise the other bounded shader paths:
python3 tests/render_shader.py --device 0 --quality low --output /tmp/dynwall-low
python3 tests/render_shader.py --device 0 --quality high --output /tmp/dynwall-high
```

Requires Python Pillow, Node, and system EGL/OpenGL. `--device 0` selects NVIDIA on the target machine; device ordering is environment-specific. Without `--device`, EGL may choose software rendering even when GLX uses NVIDIA. The harness emits weather PNGs, an autumn gust GIF and `measurements.json`; it asserts visible animation, cloud occlusion of stars, leaf travel with both wind directions, zero-strength transparency, and split-monitor rendering equivalence. Its GPU draw timings exclude GNOME compositing and do not prove real-desktop FPS or idle power.

Living-environment controls are published in the additive `scene.living` contract.
`living.js` keeps environmental history, season/event selection and performance
policy pure and testable; `presentation.js` isolates synthetic previews and
preserves discrete material selectors. GNOME 50 pack foregrounds use
`St.ImageContent` and a spanned transparent actor behind application windows.
The landscape update adds terrain materials even with seasonal controls zeroed;
upper-sky pixels remain identical to the preceding renderer. Seasonal trees use
fixed global-canvas coordinates, tapered branches, clustered foliage and conifers.
Settings and the renderer share the existing TopWeather cache; no fetcher or
permanent service was added. See the repository's living-environment verification
report for behavior, artifacts, and host-session limits. Updated modules require
normal GNOME session discovery; installation never forces a logout or restart.
