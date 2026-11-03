#!/usr/bin/env bash
# Run inside tests/smoke_gnome.sh's INNER block, after its application fixture exits.
# Contract: OUT/ROOT and the private HOME/XDG/DBus/Wayland environment must be inherited.
set -euo pipefail

fail() {
    printf 'Desktop regression setup error: %s\n' "$*" >&2
    exit 1
}

: "${OUT:?Run inside tests/smoke_gnome.sh so OUT is set}"
: "${ROOT:?Run inside tests/smoke_gnome.sh so ROOT is set}"
[[ "$HOME" == "$OUT/home" ]] || fail "HOME is not the private smoke home"
[[ "${XDG_CONFIG_HOME:-}" == "$OUT/config" ]] || fail "XDG_CONFIG_HOME is not private"
[[ "${XDG_DATA_HOME:-}" == "$OUT/data" ]] || fail "XDG_DATA_HOME is not private"
[[ "${XDG_CACHE_HOME:-}" == "$OUT/cache" ]] || fail "XDG_CACHE_HOME is not private"
[[ "${XDG_RUNTIME_DIR:-}" == "$OUT/runtime" ]] || fail "XDG_RUNTIME_DIR is not private"
[[ "${WAYLAND_DISPLAY:-}" == "dynwall-smoke" ]] || fail "not connected to the smoke Wayland display"
[[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] || fail "not running in the private Wayland session"
[[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]] || fail "private session bus is missing"

shell_eval() {
    gdbus call --session \
        --dest org.gnome.Shell \
        --object-path /org/gnome/Shell \
        --method org.gnome.Shell.Eval "$1"
}

unsafe_state=$(shell_eval 'global.context.unsafe_mode')
[[ "$unsafe_state" == "(true, 'true')" ]] || fail "private Shell.Eval instrumentation is unavailable: $unsafe_state"

# Fix the test desktop location before DING starts; never consult the login home.
mkdir -p "$HOME/Desktop"
cat >"$XDG_CONFIG_HOME/user-dirs.dirs" <<EOF
XDG_DESKTOP_DIR="$HOME/Desktop"
EOF
rm -f "$HOME/Desktop/Dynwall-visible-fixture.txt"

# Keep DING deterministic and remove its optional built-in icons from the pixel baseline.
gsettings set org.gnome.shell.extensions.ding show-home false
gsettings set org.gnome.shell.extensions.ding show-trash false
gsettings set org.gnome.shell.extensions.ding show-volumes false
gsettings set org.gnome.shell.extensions.ding show-network-volumes false
gsettings set org.gnome.shell.extensions.ding start-corner 'top-left'

gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Extensions.EnableExtension ding@rastersoft.com \
    >"$OUT/ding-enable.txt"

ding_ready=false
for _ in $(seq 1 120); do
    shell_eval '(() => {const d=Main.extensionManager.lookup("ding@rastersoft.com"); const actors=global.get_window_actors().filter(a=>a.meta_window?.get_title()?.startsWith("Desktop Icons ")); const managed=d?.stateObj?.data?.x11Manager?._windowList?.length??0; return {state:d?.state??null,process:!!d?.stateObj?.data?.currentProcess?.subprocess,windows:Math.max(actors.length,managed)};})()' \
        >"$OUT/ding-state.txt"
    if grep -q '"state":1' "$OUT/ding-state.txt" && \
       grep -q '"process":true' "$OUT/ding-state.txt" && \
       grep -Eq '"windows":[1-9][0-9]*' "$OUT/ding-state.txt"; then
        ding_ready=true
        break
    fi
    sleep .25
done
[[ "$ding_ready" == true ]] || fail "DING did not create a desktop window: $(cat "$OUT/ding-state.txt")"

# Create and move the private virtual pointer before taking a baseline. A new pointer
# starts at the hot corner, so explicitly leave Overview and wait for the move to land.
POINTER_X=1500
POINTER_Y=700
shell_eval "(() => {const t=Main.extensionManager.lookup('dynwall-smoke@test').stateObj; t._desktopPointerState='loading'; Promise.all([import('gi://Clutter'),import('gi://GLib')]).then(([clutterModule,glibModule])=>{const Clutter=clutterModule.default;t._desktopClutter=Clutter;t._desktopGLib=glibModule.default;const seat=Clutter.get_default_backend().get_default_seat();t._desktopPointer ??= seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);seat.warp_pointer($POINTER_X,$POINTER_Y);t._desktopPointer.notify_absolute_motion(t._desktopGLib.get_monotonic_time(),$POINTER_X,$POINTER_Y);t._desktopPointerState='moved';}).catch(error=>{t._desktopPointerState='error: '+error.message;});return true;})()" \
    >"$OUT/desktop-pointer-setup.txt"
grep -q "^(true," "$OUT/desktop-pointer-setup.txt" || fail "Shell rejected virtual-pointer setup: $(cat "$OUT/desktop-pointer-setup.txt")"
pointer_ready=false
for _ in $(seq 1 60); do
    shell_eval "(() => {Main.overview.hide(); const t=Main.extensionManager.lookup('dynwall-smoke@test').stateObj; return {state:t._desktopPointerState,pointer:global.get_pointer(),overview:Main.overview.visible,animating:Main.overview.animationInProgress};})()" >"$OUT/desktop-pointer-state.txt"
    grep -q 'error:' "$OUT/desktop-pointer-state.txt" && fail "virtual-pointer setup failed: $(cat "$OUT/desktop-pointer-state.txt")"
    if grep -q '"state":"moved"' "$OUT/desktop-pointer-state.txt" && \
       grep -q '"pointer":\[1500,700,' "$OUT/desktop-pointer-state.txt" && \
       grep -q '"overview":false' "$OUT/desktop-pointer-state.txt" && \
       grep -q '"animating":false' "$OUT/desktop-pointer-state.txt"; then
        pointer_ready=true
        break
    fi
    sleep .1
done
[[ "$pointer_ready" == true ]] || fail "virtual pointer did not settle outside Overview: $(cat "$OUT/desktop-pointer-state.txt")"

# Freeze only Dynwall's private frame timer. The weather actor stays mapped and visible,
# which preserves the occlusion regression while making screenshots comparable.
shell_eval '(() => {const e=Main.extensionManager.lookup("dynwall@rucaradio")?.stateObj; if(!e?._group?.is_visible()) throw new Error("Dynwall weather actor is not visible"); e._stopFrame(); return {visible:e._group.is_visible(),running:!!e._frameSource};})()' \
    >"$OUT/desktop-weather-state.txt"
grep -q '"visible":true' "$OUT/desktop-weather-state.txt" || fail "weather actor is not visible"
grep -q '"running":false' "$OUT/desktop-weather-state.txt" || fail "weather frame timer did not stop"
sleep .5

gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell/Screenshot \
    --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/desktop-empty.png" \
    >"$OUT/desktop-empty-screenshot.txt"

printf 'Dynwall desktop fixture\n' >"$HOME/Desktop/Dynwall-visible-fixture.txt"

icon_visible=false
for _ in $(seq 1 40); do
    sleep .25
    gdbus call --session \
        --dest org.gnome.Shell \
        --object-path /org/gnome/Shell/Screenshot \
        --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/desktop-icon.png" \
        >"$OUT/desktop-icon-screenshot.txt"
    if /usr/bin/python3 - "$OUT/desktop-empty.png" "$OUT/desktop-icon.png" <<'PY'
from pathlib import Path
import sys
from PIL import Image, ImageChops

before = Image.open(Path(sys.argv[1])).convert('RGB')
after = Image.open(Path(sys.argv[2])).convert('RGB')
diff = ImageChops.difference(before, after)
r, g, b = diff.split()
maximum = ImageChops.lighter(ImageChops.lighter(r, g), b)
maximum = maximum.crop((0, 40, min(300, maximum.width), maximum.height))
changed = sum(maximum.histogram()[18:])
raise SystemExit(0 if changed >= 250 else 1)
PY
    then
        icon_visible=true
        break
    fi
done
[[ "$icon_visible" == true ]] || fail "desktop fixture never became visibly rendered"

shell_eval "(() => {const t=Main.extensionManager.lookup('dynwall-smoke@test').stateObj; const now=t._desktopGLib.get_monotonic_time(); t._desktopPointer.notify_button(now,3,t._desktopClutter.ButtonState.PRESSED); t._desktopPointer.notify_button(now+1,3,t._desktopClutter.ButtonState.RELEASED); t._desktopClick='sent'; return {sent:true,pointer:global.get_pointer(),overview:Main.overview.visible};})()" \
    >"$OUT/desktop-right-click.txt"
grep -q '"sent":true' "$OUT/desktop-right-click.txt" || fail "virtual-pointer click failed: $(cat "$OUT/desktop-right-click.txt")"
grep -q '"overview":false' "$OUT/desktop-right-click.txt" || fail "secondary click unexpectedly opened Overview: $(cat "$OUT/desktop-right-click.txt")"

popup_visible=false
for _ in $(seq 1 40); do
    shell_eval '(() => {const windows=global.display.list_all_windows(); const e=Main.extensionManager.lookup("dynwall@rucaradio")?.stateObj; return {pointer:global.get_pointer(),weather:{visible:e?._group?.is_visible()??false,parent:e?._group?.get_parent()?.get_name?.()??null},windows:windows.map(w=>({title:w.get_title(),type:w.get_window_type(),showing:w.showing_on_its_workspace()}))};})()' \
        >"$OUT/desktop-menu-state.txt"
    gdbus call --session \
        --dest org.gnome.Shell \
        --object-path /org/gnome/Shell/Screenshot \
        --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/desktop-menu.png" \
        >"$OUT/desktop-menu-screenshot.txt"
    if /usr/bin/python3 "$ROOT/tests/check_desktop.py" \
        "$OUT/desktop-empty.png" "$OUT/desktop-icon.png" "$OUT/desktop-menu.png" \
        --pointer-x "$POINTER_X" --pointer-y "$POINTER_Y" \
        >"$OUT/desktop-pixels.txt" 2>"$OUT/desktop-pixels-error.txt"; then
        popup_visible=true
        break
    fi
    sleep .25
done
[[ "$popup_visible" == true ]] || fail "secondary-click menu never became visibly rendered: $(cat "$OUT/desktop-pixels-error.txt")"

# DING's GTK3 popup is not exposed through AT-SPI in this headless session, so
# verify the user-visible result directly in the captured production popup.
command -v tesseract >/dev/null || fail "tesseract is required for desktop-menu text verification"
tesseract "$OUT/desktop-menu.png" stdout --psm 11 \
    >"$OUT/desktop-menu-text.txt" 2>"$OUT/desktop-menu-text-error.txt"
grep -Fq "Dynwall Settings" "$OUT/desktop-menu-text.txt" || \
    fail "Dynwall Settings is absent from the rendered desktop menu: $(cat "$OUT/desktop-menu-text.txt")"

cat "$OUT/ding-state.txt"
cat "$OUT/desktop-weather-state.txt"
cat "$OUT/desktop-menu-state.txt"
cat "$OUT/desktop-pixels.txt"
