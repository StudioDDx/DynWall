# Dynwall

A time-aware sky wallpaper with **GPU-animated weather for GNOME 50**: layered,
wind-driven clouds, rain and snow, nighttime clouds, and stars visible through
gaps in the cloud cover. TopWeather supplies the weather; animation runs locally.

The environment includes a low panoramic landscape with mist-separated hills,
an irregular treeline, smooth sky gradients and softly lit sun/moon discs.
Five-stop offline palettes evolve through dawn, daylight, dusk and night, with
subtle seasonal color. [See the environment preview](docs/previews/environment-preview.jpg).

The existing Python/Pillow sky generator remains the static fallback. Optional
AI art direction still chooses its palette and composition. The native GNOME
extension renders the animated sky behind desktop windows and icons using GLSL.
It never cycles `picture-uri` to animate.

## Requirements

- GNOME Shell **50**, Wayland or X11. Other Shell versions are not declared supported.
- A working OpenGL driver. Start with **Balanced / 30 FPS**.
- Python 3 with Pillow and requests; GTK 4, libadwaita and PyGObject for settings.
- Updated [TopWeather](https://github.com/StudioDDx/TopWeather), running in GNOME,
  for live weather. No additional weather API key is required.

## Install / upgrade

```bash
# Install the updated TopWeather from your local checkout first.
cd /home/rucaradio/topweather
./install.sh

cd /home/rucaradio/dynwall
./install.sh
```

Installing copies the GPU extension but does **not** enable it implicitly. It
stops/disables the obsolete PNG player and retains the 30-minute static-sky timer.
`./install.sh --no-render` stages files without rendering; `--enable-gpu` also
attempts to enable an extension already discovered by GNOME.

**Log out and back in once after installing/updating extensions.** GNOME caches
imported extension modules for the session; disabling/re-enabling TopWeather is
not a reliable code reload. Then:

```bash
gnome-extensions enable topweather@rucaradio
gnome-extensions enable dynwall@rucaradio
dynwall-settings
```

Turn on **GPU weather animation**, choose quality/frame rate, and save. Saving
updates GPU state without an API call or changing the wallpaper. **Save &
Regenerate now** also rebuilds the fallback sky. Existing installations that
previously disabled animation retain that preference until you turn it on.

### Stop / roll back animation

```bash
gnome-extensions disable dynwall@rucaradio
```

The existing static GNOME wallpaper remains underneath. No logout is needed to
disable the effect. The extension releases its actors, timers and file monitors.
To also stop periodically regenerating the still:

```bash
systemctl --user disable --now dynwall.timer
```

## How weather drives the sky

TopWeather exports its last successful observation atomically to:

```
~/.cache/topweather/current.json
```

The private, versioned snapshot includes provider, location, fetch time, day/night,
cloud cover, wind speed/direction, and available precipitation measurements. The
renderer reads it independently of the animation frame clock. It does not issue
weather requests, and it does not read TopWeather's private Shell objects.

- Clouds move with wind and change coverage smoothly.
- The same moving cloud field casts soft shadows over the hills. Slope lighting
  follows the sun/moon direction; distant layers retain their misty depth.
  Art-directed ground mist drifts more slowly than the clouds. Calm weather
  leaves clouds and mist still, apart from enabled decorative autumn gusts.
- Stars scintillate independently, with stronger variation near the horizon
  and in wind; cloud cover naturally hides them. Snow uses integrated wind
  displacement, so a new wind observation does not teleport the flakes.
  These are local visual approximations, not a physical weather simulation.
- In autumn, occasional decorative gusts carry tumbling gold, rust and amber
  leaves across the desktop and briefly push the clouds. The first gust starts
  after 12–35 seconds of active animation; later gusts follow quiet intervals of
  90–240 seconds. Each lasts 10–18 seconds with a gradual build and fade.
  September–November is autumn in the northern hemisphere, March–May in the
  southern hemisphere; missing location uses the northern calendar. These are
  artistic events, separate from reported weather, and pause with the animation.
  Turn off **Seasonal effects** in settings to keep only the usual sky/weather.
  [See an animated gust preview](docs/previews/autumn-gust.gif).
- Rain/snow follow reported conditions. When a measured rate is unavailable,
  a **visual intensity preset** is used; it is not presented as a measurement.
- wttr's `precipMM` has no declared measurement period, so it is not mislabeled
  as mm/hour. Open-Meteo's prior-hour rain can supply a rate estimate. Snow depth
  is not converted to water equivalent using an invented density.
- Observations older than two hours, corrupt files, and unreasonable future
  timestamps are ignored. Missing weather does not replay an old location's rain.
- TopWeather still controls location/provider and polling (normally 30 minutes).
  “Current” means its latest successful observation, not a real-time rain sensor.
- Procedural clouds/stars are an artistic reconstruction, not satellite cloud
  geometry or an astronomical star catalogue.

`~/.cache/dynwall/scene.json` carries the sky spec and renderer controls. Both cache
paths honor `$XDG_CACHE_HOME`. Configuration honors `$XDG_CONFIG_HOME`.

## Settings

Open **Dynwall Settings** from the desktop's secondary-click menu or run
`dynwall-settings`. The top-level **Enable Dynwall** switch is applied when you
press **Save**. Turning it off stops the scheduled timer, disables the Dynwall
GNOME extension, and resets the wallpaper keys Dynwall owns to Ubuntu's packaged
defaults. Turning it back on re-enables the timer and extension and restores the
cached Dynwall wallpaper while a fresh update is prepared.

The desktop menu integration is a managed user-level copy of Ubuntu's DING
extension. Re-running `install.sh` refreshes it from the current system DING
version. The installer refuses to overwrite an unrelated user-managed DING copy.
As with other GNOME extension updates, log out and back in after installation to
load the menu integration.

### Background library

Open `dynwall-settings` and choose **Background → Scene**. Each built-in scene
works offline, evolves through dawn/day/dusk/night, and retains TopWeather's
clouds, precipitation, wind and the existing sun/moon placement:

- **Smoky Mountain Ridges** — overlapping blue ranges, valley mist, mixed woodland and seasonal trees inspired by the Smokies.
- **Alpine Stillness** — irregular snow-covered peaks and shaded mountain faces.
- **Amber Dunes** — warm sand, sweeping crests and fine surface ripples.
- **Tidal Light** — open water, a distant horizon and broken light reflections.
  Water advection follows integrated weather wind; slow swell continues in calm conditions.
- **Open Sky** — uninterrupted atmosphere with no terrain.
- **Automatic / art director** — retain the existing AI, offline fallback and
  seasonal theme behavior.

The picker includes illustrative daytime previews rendered by the production
shader. [Compare the scenes at day, dusk and night](docs/previews/background-library.jpg).
See the [landscape update and verification](docs/landscape-verification.md) for
before/after views, importer findings and reproducible checks.
Static fallback wallpapers use matching scene silhouettes and palettes; water
animation runs in the GPU extension. **Save** applies the selected GPU scene
without a network call; **Save & Regenerate now** also updates the static image.
Turn off **Landscape depth** to hide terrain/water in any scene.

The configuration key is `"background"`, accepting `"auto"` (default), `"ridges"`,
`"alpine"`, `"dunes"`, `"ocean"` or `"sky"`. An explicit built-in scene takes
precedence over AI and seasonal theme selection; choosing Automatic restores
those settings. Existing configurations keep Automatic. Built-in palettes use
local clock time; the existing GPU celestial positioning continues to use
available observation coordinates and day/night information.

After updating an existing GNOME installation, log out and back in to load the
updated scene sanitizer and shader before selecting the new terrain styles.

### Halloween: Witching Hour

The local `halloween` theme includes **Hollow Harvest** by day (smoky lavender,
pale amber sunlight, copper hills and mist) and **Witching Hour** by night
(ink-and-plum sky, an ember halo around a silver moon and violet shadows).
TopWeather's fresh day/night observation selects the version at each scene
refresh; without that observation, local hours 07:00–18:00 select daytime.
Clouds, wind, rain, snow and autumn leaves retain the existing weather and
seasonal animation. Both versions work without AI credentials.
Set `"theme": "halloween"` and `"theme_until": "2026-11-01"` in the configuration,
then run `dynwall` to apply it. The cutoff is exclusive and uses the local date;
normal art resumes on the first scheduled refresh on or after November 1.
Set `"theme": ""` to stop it early, or leave `theme_until` empty for no cutoff.
The settings app preserves these configuration fields when saving.
The presets live in `themes/halloween-day.json` and `themes/halloween.json`;
optional Halloween AI direction is available in `themes/halloween.txt`.
[See both versions rendered with clouds](docs/previews/halloween-day-night.jpg).

`~/.config/dynwall/config.json` (owner-only; may contain an AI API key):

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Master state for the timer, GNOME extension, and Dynwall wallpaper |
| `allow_animation` | `true` | Allow the installed GNOME extension to animate |
| `seasonal_effects` | `true` | Allow decorative autumn gusts and blowing leaves |
| `weather_fps` | `30` | Frame cap, 15–60; 30 recommended |
| `weather_quality` | `"balanced"` | `low`, `balanced`, or `high` cloud detail |
| `mesh_enabled` | `true` | Include the existing geometric sky treatment |
| `landscape_enabled` | `true` | Include layered hills and atmospheric depth; turn off for sky only |
| `background` | `"auto"` | Built-in scene selection; explicit scenes work offline and override AI/seasonal art |
| `width` / `height` | `3840` / `1080` | Static fallback canvas; GPU follows monitor geometry |
| `provider` | `"openai"` | AI art direction: `openai`, `openrouter`, or `none` |
| `api_key` / `model` | `""` | Optional AI configuration; the provider's environment API key takes precedence over a saved key |
| `prompt` | `""` | Empty uses `default_prompt.txt` |
| `allow_network` | `true` | Allow Dynwall's own network calls; local TopWeather data still works when false |
| `frames` / `frame_seconds` | `24` / `1.5` | Legacy PNG export settings; not GPU frame rate |

Settings saves atomically replace the configuration with an owner-only file;
failed writes preserve the previous save. Invalid numeric values use defaults,
and canvas dimensions are capped at 15360 pixels per axis in both the CLI and
settings app.

Animation pauses when GNOME disables animations or the session is locked. Quality
and frame-rate controls limit work; high settings can compete with games and other
GPU workloads. No claim of adaptive GPU utilization or a battery-power budget.

## CLI

```bash
dynwall                  # refresh sky spec, publish scene, render/apply one still
dynwall --refresh-scene  # publish cached sky + current local weather; no network/gsettings
dynwall --animate 24     # export legacy PNG frames only; not desktop animation
```

`dynwall --play` is deliberately retired: repeatedly changing GNOME's wallpaper
URI previously caused desktop/input stalls on Wayland. Settings no longer start
that service.

AI failure falls back to the deterministic palette; live weather animation does
not depend on AI availability. Logs:

```bash
journalctl --user -u dynwall.service
journalctl --user -b | grep -i dynwall
gnome-extensions info dynwall@rucaradio
```

The art-direction prompt keeps your custom instructions and appends the renderer's
JSON contract, actual canvas dimensions, local date/time and observed weather.
The default prompt lives in `default_prompt.txt`; its embedded fallback matches.
Changing the effective prompt or canvas invalidates the hourly art cache.
Art specs may include `landscape: {style: "hills", height: 0.2, mist: 0.5}`;
styles include `hills`, `alpine`, `dunes`, `ocean` and `none`. `none` omits the
landscape, and the settings switch overrides art direction.
Landscape height is bounded to 0.1–0.3 and mist to 0–1. Terrain is decorative,
not a reconstruction of the observation location.

## Verification

```bash
/usr/bin/python3 -m unittest discover -p 'test_*.py' -v
node --test tests/*.test.mjs
/usr/bin/python3 tests/render_shader.py --output /tmp/dynwall-preview
```

The shader harness compiles the **production GLSL** into an isolated EGL surface,
renders weather fixtures, checks visible motion, and records the actual renderer
and frame timings. Check its renderer string: software EGL results are not proof
of NVIDIA acceleration. See `docs/verification.md` for this implementation's
measured results and remaining desktop checks.

## License

MIT

## Living environment controls

The native settings app includes local landscape packs, a time/weather preview,
scene customization and named presets, favorites and optional schedules, artistic
persistent weather surfaces, seasonal scenery, rare atmospheric moments and
battery-aware rendering. These features work locally without a new weather
fetcher or an API key. TopWeather remains the observation authority.

Use **Return to live** to leave the temporary preview. Preview requests live in
`$XDG_CACHE_HOME/dynwall/preview.json` (normally `~/.cache/dynwall/preview.json`)
and expire after two hours. They never modify TopWeather's observations or the
persisted live surface state. The settings image is an illustrative offline still;
the GNOME desktop uses the production animated shader.

Landscape packs use a versioned manifest, a marked horizon and a local PNG
foreground. Import validates and canonicalizes the assets before selection;
opaque photographs are cut above their horizon. The original **Woodland River**
example is shipped in [packs/woodland](packs/woodland/). See the
[pack format and local authoring instructions](packs/README.md).

The surface snow and wetness are artistic history, not measured snow depth or
water levels. Reset and off controls are available in settings. State is stored
atomically with owner-only permissions in `~/.cache/dynwall/environment.json`;
stale observations and location changes cannot replay old precipitation.

Schedules are off by default. Timed entries use the local clock and wrap across
midnight; they take priority over favorite rotation. Clear timed entries to use
rotation, whose minimum interval is five minutes. Automatic selection retains
existing automatic/seasonal art. Preview takes priority until Return to live.

The FPS and quality controls describe configured workload, not GPU utilization.
Battery saver lowers the native frame cap and quality. A monitor covered by a
fullscreen application stops receiving shader updates; covering all monitors
pauses the frame source. Lock, suspend, display-off and reduced motion retain the
existing static fallback behavior. Unsupported power APIs safely retain the
configured workload.

Implementation evidence and remaining runtime limits are recorded in
[the living-environment verification report](docs/living-environment-verification.md).
