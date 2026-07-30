#!/usr/bin/env bash
# Install dynwall: symlink CLI + settings app, install systemd user units + .desktop entry.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

for unit in dynwall.service dynwall.timer dynwall-play.service; do
    cp "$REPO/systemd/$unit" "$HOME/.config/systemd/user/$unit"
done

if [ ! -f "$HOME/.config/dynwall/env" ]; then
    cp "$REPO/.env.example" "$HOME/.config/dynwall/env"
    chmod 600 "$HOME/.config/dynwall/env"
    echo ">> put your OPENAI_API_KEY in ~/.config/dynwall/env (optional)"
fi

systemctl --user daemon-reload
systemctl --user enable --now dynwall.timer dynwall-play.service

echo ">> building first frame set..."
"$HOME/.local/bin/dynwall" --animate 24
echo ">> done. Wallpaper is live."
