#!/usr/bin/env bash
# Install DynWall as a user-owned systemd wallpaper service (no Shell extension).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENDER=true
for arg in "$@"; do
    case "$arg" in
        --no-render) RENDER=false ;;
        -h|--help) echo "usage: $0 [--no-render]"; exit 0 ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

for file in dynwall dynwall-settings dynwall_slideshow.py dynwall_weather.py \
            dynwall_living.py dynwall_living_settings.py \
            systemd/dynwall.service systemd/dynwall.timer; do
    [ -f "$REPO/$file" ] || { echo "missing: $file" >&2; exit 1; }
done
python3 -c 'import PIL, requests' || {
    echo "Install python3-pil and python3-requests" >&2; exit 1;
}

mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user" \
         "$HOME/.config/dynwall" "$HOME/.local/share/applications"
ln -sfn "$REPO/dynwall" "$HOME/.local/bin/dynwall"
ln -sfn "$REPO/dynwall-settings" "$HOME/.local/bin/dynwall-settings"
cp "$REPO/dynwall-settings.desktop" "$HOME/.local/share/applications/dynwall-settings.desktop"
for unit in dynwall.service dynwall.timer; do
    cp "$REPO/systemd/$unit" "$HOME/.config/systemd/user/$unit"
done
if [ ! -f "$HOME/.config/dynwall/env" ]; then
    cp "$REPO/.env.example" "$HOME/.config/dynwall/env"
    chmod 600 "$HOME/.config/dynwall/env"
fi

# Explicit migration away from the old Shell actor and PNG cycling service.
systemctl --user disable --now dynwall-play.service 2>/dev/null || true
if command -v gnome-extensions >/dev/null 2>&1; then
    gnome-extensions disable dynwall@rucaradio 2>/dev/null || true
fi
systemctl --user daemon-reload
enabled="$(python3 - "$HOME/.config/dynwall/config.json" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        print("yes" if json.load(f).get("enabled", True) is not False else "no")
except (OSError, ValueError, AttributeError):
    print("yes")
PY
)"
if [ "$enabled" = yes ]; then
    systemctl --user enable --now dynwall.timer
    if "$RENDER"; then
        # Render synchronously so installation errors are visible.
        systemctl --user start dynwall.service
    fi
else
    systemctl --user disable --now dynwall.timer
fi
echo "DynWall uses systemd and GNOME's native background slideshow."
echo "Check with: systemctl --user status dynwall.service dynwall.timer"
echo "Logs: journalctl --user -u dynwall.service -n 60 --no-pager"
