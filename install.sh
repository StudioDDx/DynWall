#!/usr/bin/env bash
# Install dynwall: symlink CLI + settings app, install systemd user units + .desktop entry.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENABLE_GPU=false
RENDER=true
PACK_ONLY=false
UUID='dynwall@rucaradio'
for arg in "$@"; do
    case "$arg" in
        --enable-gpu) ENABLE_GPU=true ;;
        --no-render) RENDER=false ;;
        --pack-only) PACK_ONLY=true ;;
        -h|--help) echo "usage: $0 [--enable-gpu] [--no-render] [--pack-only]"; exit 0 ;;
        *) echo "usage: $0 [--enable-gpu] [--no-render] [--pack-only]" >&2; exit 2 ;;
    esac
done

# Validate the package before touching binaries, services, or the installed extension.
for file in dynwall dynwall-settings dynwall-settings.desktop dynwall_weather.py .env.example systemd/dynwall.service \
    systemd/dynwall.timer systemd/dynwall-play.service extension/metadata.json \
    extension/extension.js extension/state.js extension/lifecycle.js \
    extension/shader.js extension/uniforms.js extension/presentation.js extension/living.js \
    extension/weather.glsl extension/valley-fog.glsl dynwall_ding_menu.py; do
    if [ ! -f "$REPO/$file" ]; then
        echo "error: incomplete Dynwall package: missing $file" >&2
        exit 1
    fi
done
python3 - "$REPO/extension/metadata.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    metadata = json.load(f)
if metadata.get('uuid') != 'dynwall@rucaradio' or '50' not in metadata.get('shell-version', []):
    raise SystemExit('error: invalid Dynwall extension metadata')
PY

# Package and validate before mutating the existing installation.
command -v gnome-extensions >/dev/null || {
    echo "error: gnome-extensions is required" >&2; exit 1;
}
TMP_BUNDLE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dynwall-extension.XXXXXXXX")"
trap 'rm -rf -- "$TMP_BUNDLE_DIR"' EXIT
# GNOME includes only extension.js, metadata.json and a few optional
# standard files by default. Relative JS imports and GLSL sources MUST each
# be passed explicitly, or the resulting archive is missing runtime modules.
EXTRA_SOURCES=()
shopt -s nullglob
for source in "$REPO"/extension/*.js "$REPO"/extension/*.glsl; do
    case "${source##*/}" in
        extension.js|prefs.js) continue ;;
    esac
    EXTRA_SOURCES+=("--extra-source=${source##*/}")
done
shopt -u nullglob
gnome-extensions pack --force --out-dir "$TMP_BUNDLE_DIR" \
    "${EXTRA_SOURCES[@]}" "$REPO/extension"

shopt -s nullglob
BUNDLES=("$TMP_BUNDLE_DIR"/*.zip)
shopt -u nullglob
if [ "${#BUNDLES[@]}" -ne 1 ]; then
    echo "error: expected exactly one GNOME extension ZIP" >&2
    exit 1
fi
BUNDLE="${BUNDLES[0]}"
python3 - "$BUNDLE" "$UUID" "$REPO/extension" <<'PY'
import json, sys, zipfile
from collections import Counter
from pathlib import Path

source = Path(sys.argv[3])
required = {'metadata.json', 'extension.js'}
required.update(path.name for pattern in ('*.js', '*.glsl')
                for path in source.glob(pattern) if path.is_file())
with zipfile.ZipFile(sys.argv[1]) as archive:
    names = archive.namelist()
    duplicate = sorted(name for name, count in Counter(names).items() if count > 1)
    missing = sorted(required.difference(names))
    if missing or duplicate:
        if missing:
            print('error: extension ZIP missing: ' + ', '.join(missing), file=sys.stderr)
        if duplicate:
            print('error: extension ZIP has duplicate entries: ' + ', '.join(duplicate),
                  file=sys.stderr)
        raise SystemExit(1)
    metadata = json.loads(archive.read('metadata.json'))
    if metadata.get('uuid') != sys.argv[2] or archive.testzip() is not None:
        raise SystemExit('error: invalid extension archive or UUID')
PY

if $PACK_ONLY; then
    mkdir -p "$REPO/dist"
    OUTPUT="$REPO/dist/${UUID}.shell-extension.zip"
    cp -- "$BUNDLE" "$OUTPUT"
    printf 'Packaged GNOME extension: %s\n' "$OUTPUT"
    exit 0
fi

if ! python3 -c "import PIL, requests" 2>/dev/null; then
    echo "error: missing python deps; install python3-pil and python3-requests" >&2
    exit 1
fi

# Use GNOME's installer instead of copying directly into live extension sources.
gnome-extensions install --force "$BUNDLE"
EXTENSION_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$UUID"
for file in metadata.json extension.js weather.glsl valley-fog.glsl; do
    if [ ! -f "$EXTENSION_DIR/$file" ]; then
        echo "error: installed extension is incomplete: $file" >&2
        exit 1
    fi
done
printf 'Installed GNOME extension at %s\n' "$EXTENSION_DIR"

mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user" "$HOME/.config/dynwall" \
    "$HOME/.local/share/applications"
ln -sf "$REPO/dynwall" "$HOME/.local/bin/dynwall"

# Settings app (GTK4 + libadwaita); non-fatal if not present in this checkout.
if [ -f "$REPO/dynwall-settings" ]; then
    ln -sf "$REPO/dynwall-settings" "$HOME/.local/bin/dynwall-settings"
fi
if [ -f "$REPO/dynwall-settings.desktop" ]; then
    cp "$REPO/dynwall-settings.desktop" "$HOME/.local/share/applications/dynwall-settings.desktop"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" || true
    fi
fi

DING_SOURCE="/usr/share/gnome-shell/extensions/ding@rastersoft.com"
DING_TARGET="$HOME/.local/share/gnome-shell/extensions/ding@rastersoft.com"
if [ -d "$DING_SOURCE" ]; then
    python3 "$REPO/dynwall_ding_menu.py" --source "$DING_SOURCE" --target "$DING_TARGET"
fi

for unit in dynwall.service dynwall.timer dynwall-play.service; do
    cp "$REPO/systemd/$unit" "$HOME/.config/systemd/user/$unit"
done

if [ ! -f "$HOME/.config/dynwall/env" ]; then
    cp "$REPO/.env.example" "$HOME/.config/dynwall/env"
    chmod 600 "$HOME/.config/dynwall/env"
    echo ">> put your OPENAI_API_KEY in ~/.config/dynwall/env (optional)"
fi

systemctl --user daemon-reload
# Retire image-swapping playback even when upgrading an older installation.
systemctl --user disable --now dynwall-play.service || true
if python3 - "$HOME/.config/dynwall/config.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as config_file:
        enabled = json.load(config_file).get('enabled', True)
except (OSError, ValueError, AttributeError):
    enabled = True
raise SystemExit(0 if enabled is not False else 1)
PY
then
    systemctl --user enable --now dynwall.timer
else
    systemctl --user disable --now dynwall.timer
fi

if $RENDER; then
    echo ">> rendering fallback wallpaper and publishing GPU state..."
    "$HOME/.local/bin/dynwall"
fi

if $ENABLE_GPU; then
    if ! gnome-extensions enable "$UUID"; then
        echo ">> GNOME has not discovered the new extension yet. Log out/in, then run:"
        echo "   gnome-extensions enable dynwall@rucaradio"
    fi
else
    echo ">> GPU extension installed but not enabled. After GNOME discovers it, run:"
    echo "   gnome-extensions enable dynwall@rucaradio"
fi
echo ">> Log out and back in to load updated GNOME extension JavaScript."
echo ">> Install the updated TopWeather too; its next successful refresh supplies live weather."
echo ">> Roll back animation instantly: gnome-extensions disable dynwall@rucaradio"
