# dynwall

AI art-directed dynamic wallpaper for GNOME (dual-monitor ultrawide), with animation.

A small Python engine renders a 3840×1080 wallpaper locally with PIL — gradient,
glow, low-poly mesh, celestial bodies, starfield, film grain — and an OpenAI model
(cheap nano tier) acts as art director, choosing the palette and composition from
the current time of day and your live weather. It can also pre-render an animation
loop (twinkling stars, breathing glow, drifting celestial, shimmering grain) and
cycle the desktop background through the frames.

![example](docs/example.png)

## Features

- **AI art direction**: palette, glow, mesh style, stars, sun/moon, grain, vignette — re-composed every hour (~1 API call/hour, cached)
- **Weather-reactive**: pulls live conditions from `wttr.in` (IP-based location)
- **Time-aware**: dawn/day/dusk/night palettes; deterministic sun-elevation fallback when offline or API-less
- **Animation loop**: pre-rendered frames cycled via `gsettings` (no video player, no compositor hacks)
- **Spanned dual-monitor**: one 3840×1080 canvas across two 1920×1080 panels (`picture-options spanned`)

## Requirements

- GNOME on Wayland or X11
- Python 3 with `PIL` and `requests`
- For the settings app: Python 3 with PyGObject (`gi`), GTK 4 and libadwaita
- Optional: an API key for AI art direction — OpenAI (`OPENAI_API_KEY`) or
  OpenRouter (`OPENROUTER_API_KEY`), or set one in the Settings app. Without a
  key, dynwall falls back to a deterministic palette.

## Install

```bash
git clone https://github.com/rucaradio/dynwall.git
cd dynwall
./install.sh
```

`install.sh`:

1. Symlinks `dynwall` and `dynwall-settings` into `~/.local/bin`, and installs the
   `dynwall-settings.desktop` entry into `~/.local/share/applications`
2. Installs + enables the systemd user units:
   - `dynwall.timer` — regenerates the frame set every 30 min (2 min after login)
   - `dynwall-play.service` — cycles frames (~1.5 s/frame)
3. Copies `.env.example` → `~/.config/dynwall/env` (put your `OPENAI_API_KEY` there, or configure a key in Settings)

Then run `dynwall --animate 24` once to build the first frame set.

## Usage

```
dynwall              # render a single still, apply as wallpaper
dynwall --animate N  # render an N-frame loop to ~/.cache/dynwall/frames
dynwall --play       # cycle picture-uri through the frames (what the service runs)
```

Force a new AI composition (specs are cached per hour + weather):

```bash
rm ~/.cache/dynwall/spec.json && dynwall
```

Stop the animation / rotation:

```bash
systemctl --user disable --now dynwall-play.service dynwall.timer
```

## How it works

1. `weather-glyph --temp`-style context (conditions + temperature) is gathered from wttr.in
2. The OpenAI model returns a JSON spec: gradient stops + positions, accent, glow
   (color/x/y/size/intensity/pulse), celestial disc (sun/moon, drift), star count,
   mesh (lowpoly/lines/none, density, opacity), grain, vignette, plus a poetic title
3. The spec is validated/sanitized and rendered with PIL
4. Frames are cycled through `gsettings org.gnome.desktop.background picture-uri`

Specs and renders log to `journalctl --user -u dynwall.service` — a running gallery
of the titles it invents.

## Settings

`dynwall-settings` (installed alongside the CLI, and listed as "Dynwall Settings"
in your app launcher) is a GTK 4 + libadwaita settings window. It edits
`~/.config/dynwall/config.json`, writes it as pretty JSON with mode `600` (it can
hold your API key), and offers a **Regenerate now** button that runs
`dynwall --animate` in the background. Saving never requires the app: the file is
created on demand, missing keys fall back to defaults, and a missing or corrupt
file simply means "all defaults".

### `config.json` keys

| Key | Default | Meaning |
| --- | --- | --- |
| `provider` | `"openai"` | `"openai"`, `"openrouter"`, or `"none"` (no API, deterministic palette) |
| `api_key` | `""` | API key. Falls back to `$OPENAI_API_KEY` / `$OPENROUTER_API_KEY` when empty |
| `model` | `"gpt-5.4-nano"` | Model name. For OpenRouter use its slug form, e.g. `"openai/gpt-5.4-nano"` |
| `prompt` | `""` | Art-director prompt. Empty = built-in default; any non-empty value overrides it |
| `allow_network` | `true` | `false` disables both the API and the `wttr.in` weather fetch (pure fallback palette) |
| `allow_animation` | `true` | Enable/disable animation support |
| `frames` | `24` | Frame count (1–120); default for `--animate`/`--play`. CLI `--animate N` still overrides |
| `frame_seconds` | `1.5` | Dwell per frame (0.5–10 s) |
| `width` / `height` | `3840` / `1080` | Canvas size |
| `mesh_enabled` | `true` | Render the low-poly mesh layer |

### Prompt and "Revert to default"

The built-in art-director prompt lives in `default_prompt.txt` in the repo (single
source of truth). The Settings app shows the prompt in a multi-line editor with a
**Revert to default** button that reloads `default_prompt.txt` — it locates the
repo by resolving the `~/.local/bin/dynwall` symlink, falling back to a path
relative to the settings script itself. Set `prompt` back to `""` to use the
built-in default again.

### Providers

- **openai** — `https://api.openai.com/v1/chat/completions`
- **openrouter** — `https://openrouter.ai/api/v1/chat/completions` (same request
  shape; sends `HTTP-Referer: dynwall`)
- **none** — no API at all; deterministic fallback composition

## License

MIT
