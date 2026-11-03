#!/usr/bin/env bash
# Install dynwall: symlink CLI + settings app, install systemd user units + .desktop entry.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENABLE_GPU=false
RENDER=true
for arg in "$@"; do
    case "$arg" in
        --enable-gpu) ENABLE_GPU=true ;;
        --no-render) RENDER=false ;;
        *) echo "usage: $0 [--enable-gpu] [--no-render]" >&2; exit 2 ;;
    esac
done

# Validate the package before touching binaries, services, or the installed extension.
for file in dynwall dynwall-settings dynwall-settings.desktop dynwall_weather.py .env.example systemd/dynwall.service \
    systemd/dynwall.timer systemd/dynwall-play.service extension/metadata.json \
    extension/extension.js extension/state.js extension/lifecycle.js extension/seasonal.js \
    extension/shader.js extension/uniforms.js extension/weather.glsl dynwall_ding_menu.py; do
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

# Pre-flight: fail fast before installing anything if python deps are missing.
if ! python3 -c "import PIL, requests" 2>/dev/null; then
    echo "error: missing python deps — install them first, e.g.:" >&2
    echo "  sudo apt install python3-pil python3-requests   # Debian/Ubuntu/Fedora (python3-pillow)" >&2
    exit 1
fi

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

EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/dynwall@rucaradio"
mkdir -p "$EXTENSION_DIR"
cp -a "$REPO/extension/." "$EXTENSION_DIR/"

if $RENDER; then
    echo ">> rendering fallback wallpaper and publishing GPU state..."
    "$HOME/.local/bin/dynwall"
fi

if $ENABLE_GPU; then
    if ! gnome-extensions enable dynwall@rucaradio; then
        echo ">> GNOME has not discovered the new extension yet. Log out/in, then run:"
        echo "   gnome-extensions enable dynwall@rucaradio"
    fi
else
    echo ">> GPU extension installed but not enabled. After GNOME discovers it, run:"
    echo "   gnome-extensions enable dynwall@rucaradio"
fi
echo ">> Install the updated TopWeather too; its next successful refresh supplies live weather."
echo ">> Roll back animation instantly: gnome-extensions disable dynwall@rucaradio"
