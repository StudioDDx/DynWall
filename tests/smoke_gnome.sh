#!/usr/bin/env bash
# A private, headless GNOME session: never uses the user's bus, dconf, or runtime.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$(mktemp -d /tmp/dynwall-gnome-smoke.XXXXXX)}
mkdir -p "$OUT"/{home,config,data/gnome-shell/extensions/dynwall@rucaradio,cache/dynwall,cache/topweather,runtime}
chmod 700 "$OUT" "$OUT/runtime"
cp -a "$ROOT/extension/." "$OUT/data/gnome-shell/extensions/dynwall@rucaradio/"
# DING cleans up old processes matching its installation path. A private copy
# prevents its startup cleanup from touching the login session's desktop icons.
# Install through the production helper so the real right-click integration is
# exercised rather than a synthetic menu fixture.
/usr/bin/python3 "$ROOT/dynwall_ding_menu.py" \
    --source /usr/share/gnome-shell/extensions/ding@rastersoft.com \
    --target "$OUT/data/gnome-shell/extensions/ding@rastersoft.com"
mkdir -p "$OUT/data/applications"
cp "$ROOT/dynwall-settings.desktop" "$OUT/data/applications/"
# Test-only debug helper, installed solely inside this throwaway private session.
mkdir -p "$OUT/data/gnome-shell/extensions/dynwall-smoke@test"
cat > "$OUT/data/gnome-shell/extensions/dynwall-smoke@test/metadata.json" <<'JSON'
{"uuid":"dynwall-smoke@test","name":"Isolated test instrumentation","description":"Private smoke test only","shell-version":["50"]}
JSON
cat > "$OUT/data/gnome-shell/extensions/dynwall-smoke@test/extension.js" <<'JS'
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
export default class TestExtension extends Extension {
    enable() { global.context.unsafe_mode = true; }
    disable() { global.context.unsafe_mode = false; }
}
JS
OUT="$OUT" /usr/bin/python3 - <<'PY'
import json, os, time
from pathlib import Path
p=Path(os.environ['OUT']); now=int(time.time()*1000)
(p/'cache/dynwall/scene.json').write_text(json.dumps({'schemaVersion':1,'generatedAt':now,'spec':{'gradient':['#254b76','#abcddd'], 'stars':300,'mesh':{'style':'none'},'celestial':{'type':'sun','x':.7,'y':.25,'size':.05}},'renderer':{'enabled':True,'fps':30,'quality':'balanced'}}))
(p/'cache/topweather/current.json').write_text(json.dumps({'schemaVersion':1,'fetchedAt':now,'provider':'wttr','location':'Fixture','unit':'c','latitude':42,'longitude':-83,'current':{'cloudCover':65,'rain':1.5,'snowfall':0,'windSpeedKmh':12,'windDirection':240,'isNight':False}}))
PY
export OUT ROOT
# Start session services with our isolated environment, not the login session's.
env HOME="$OUT/home" XDG_CONFIG_HOME="$OUT/config" XDG_DATA_HOME="$OUT/data" \
    XDG_CACHE_HOME="$OUT/cache" XDG_RUNTIME_DIR="$OUT/runtime" \
    XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=GNOME \
    dbus-run-session -- bash <<'INNER'
set -euo pipefail
unset SESSION_MANAGER GNOME_DESKTOP_SESSION_ID DBUS_STARTER_ADDRESS DBUS_STARTER_BUS_TYPE
# Separate dconf instance on this private bus.
/usr/bin/gsettings set org.gnome.shell enabled-extensions "['dynwall@rucaradio']"
/usr/bin/gsettings set org.gnome.desktop.interface enable-animations true
gnome-shell --headless --wayland --no-x11 --virtual-monitor=1920x1080 --virtual-monitor=1920x1080 --wayland-display=dynwall-smoke --debug-control >"$OUT/shell.log" 2>&1 &
SHELL_PID=$!
APP_PID=
trap '[[ -z "$APP_PID" ]] || kill "$APP_PID" 2>/dev/null || true; kill "$SHELL_PID" 2>/dev/null || true; wait "$SHELL_PID" 2>/dev/null || true' EXIT
for n in $(seq 1 80); do
    if gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionInfo dynwall@rucaradio >"$OUT/info.txt" 2>/dev/null && grep -q "state" "$OUT/info.txt"; then break; fi
    kill -0 "$SHELL_PID"
    sleep .25
done
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.EnableExtension dynwall-smoke@test >/dev/null
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.EnableExtension dynwall@rucaradio >/dev/null
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval 'Main.overview.hide()' >/dev/null
sleep 3
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval 'Main.overview.hide()' >"$OUT/hide.txt"
sleep 1
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionInfo dynwall@rucaradio >"$OUT/info.txt"
state() {
    gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "(() => {const e=Main.extensionManager.lookup('dynwall@rucaradio').stateObj; const count=a=>(a.name==='Dynwall GPU Weather'?1:0)+a.get_children().reduce((n,c)=>n+count(c),0); return {targetCoverage:e?._target?.u_coverage, scenePath:e?._scenePath, sceneEnabled:e?._scene?.enabled, scene:!!e?._scene, target:!!e?._target, locked:Main.screenShield.locked, suspended:e?._suspended, overview:Main.overview.visible, overviewAnimation:Main.overview.animationInProgress, animations:e?._settings?.get_boolean('enable-animations'), monitors:Main.layoutManager.monitors.length, running:!!e?._frameSource, effects:e?._effects?.length ?? 0, groups:count(global.window_group), visible:e?._group?.visible ?? false};})()"
}
state >"$OUT/running-state.txt"
# PowerSaveMode belongs to this private headless Shell. Never perform this test
# on the login session: it deliberately exercises compositor display-off/on.
gdbus call --session --dest org.gnome.Mutter.DisplayConfig --object-path /org/gnome/Mutter/DisplayConfig \
    --method org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode '<3>' >/dev/null
sleep 1
state >"$OUT/display-off-state.txt"
gdbus call --session --dest org.gnome.Mutter.DisplayConfig --object-path /org/gnome/Mutter/DisplayConfig \
    --method org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode '<0>' >/dev/null
sleep 1
state >"$OUT/display-on-state.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/desktop.png" >"$OUT/screenshot.txt"
# Map real Wayland application windows AFTER the wallpaper starts. Merely drawing
# an empty desktop misses Mutter's window-restack handling of non-window actors.
WAYLAND_DISPLAY=dynwall-smoke GDK_BACKEND=wayland /usr/bin/python3 - >"$OUT/window-app.log" 2>&1 <<'PYWINDOW' &
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio
app = Gtk.Application(application_id='org.dynwall.StackingSmoke', flags=Gio.ApplicationFlags.NON_UNIQUE)
def activate(app):
    for number in (1, 2):
        window = Gtk.ApplicationWindow(application=app, title=f'Dynwall stacking test {number}')
        window.set_default_size(640, 480)
        area = Gtk.DrawingArea()
        def draw(_area, context, _width, _height):
            context.set_source_rgb(1, 0, 1)
            context.paint()
        area.set_draw_func(draw)
        window.set_child(area)
        window.present()
app.connect('activate', activate)
app.run(None)
PYWINDOW
APP_PID=$!
for n in $(seq 1 80); do
    gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
        'global.get_window_actors().filter(a=>a.meta_window.get_title()?.startsWith("Dynwall stacking test")).length' >"$OUT/window-count.txt"
    if grep -q "'2'" "$OUT/window-count.txt"; then break; fi
    kill -0 "$APP_PID"
    sleep .25
done
stacking() {
    # Compare the actors' first divergent ancestors: this checks actual paint
    # order whether weather is a sibling of windows or nested in the background.
    gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
        '(() => {const e=Main.extensionManager.lookup("dynwall@rucaradio").stateObj; const path=a=>{const p=[];while(a){p.unshift(a);a=a.get_parent();}return p;};const below=(a,b)=>{const x=path(a),y=path(b);let i=0;while(i<x.length&&i<y.length&&x[i]===y[i])i++;if(!i||i===x.length||i===y.length)return false;const siblings=x[i-1].get_children();return siblings.indexOf(x[i])<siblings.indexOf(y[i]);};const windows=global.get_window_actors().filter(a=>a.meta_window.get_title()?.startsWith("Dynwall stacking test"));return {windows:windows.length,weatherVisible:!!e?._group?.is_visible(),belowAll:!!e?._group&&windows.every(a=>below(e._group,a)),focused:global.display.focus_window?.get_title()?.startsWith("Dynwall stacking test")??false};})()'
}
sleep 1
stacking >"$OUT/window-mapped-state.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/windows.png" >"$OUT/windows-screenshot.txt"
# Exercise a second restack rather than relying on initial insertion order.
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
    'global.get_window_actors().find(a=>a.meta_window.get_title()==="Dynwall stacking test 1").meta_window.activate(global.get_current_time())' >/dev/null
sleep 1
stacking >"$OUT/window-raised-state.txt"
# The periodic static-wallpaper refresh must not cover weather or change its
# relationship to applications when GNOME replaces its native backgrounds.
python3 - <<'PYSTATIC'
import os
from pathlib import Path
from PIL import Image
Image.new('RGB', (32, 32), (0, 255, 0)).save(Path(os.environ['OUT'])/'static-refresh.png')
PYSTATIC
/usr/bin/gsettings set org.gnome.desktop.background picture-uri "file://$OUT/static-refresh.png"
/usr/bin/gsettings set org.gnome.desktop.background picture-uri-dark "file://$OUT/static-refresh.png"
sleep 1
stacking >"$OUT/window-background-refresh-state.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/background-refreshed.png" >/dev/null
/usr/bin/gsettings set org.gnome.desktop.interface enable-animations false
sleep 1
state >"$OUT/paused-state.txt"
/usr/bin/gsettings set org.gnome.desktop.interface enable-animations true
sleep 1
state >"$OUT/resumed-state.txt"
# Atomic scene-control reload must remove and recreate the actor without extension reload.
python3 - <<'PYSCENE'
import json,os
from pathlib import Path
p=Path(os.environ['OUT'])/'cache/dynwall/scene.json'; d=json.loads(p.read_text()); d['renderer']['enabled']=False
q=p.with_suffix('.tmp');q.write_text(json.dumps(d));q.replace(p)
PYSCENE
sleep 1
state >"$OUT/scene-disabled-state.txt"
python3 - <<'PYSCENE'
import json,os
from pathlib import Path
p=Path(os.environ['OUT'])/'cache/dynwall/scene.json'; d=json.loads(p.read_text()); d['renderer']['enabled']=True
q=p.with_suffix('.tmp');q.write_text(json.dumps(d));q.replace(p)
PYSCENE
sleep 1
state >"$OUT/scene-enabled-state.txt"
stacking >"$OUT/window-recreated-state.txt"
# Stale observations must stop driving weather, even if a scene once contained them.
cp "$OUT/cache/topweather/current.json" "$OUT/weather-backup.json"
python3 - <<'PYWEATHER'
import json,os,time
from pathlib import Path
p=Path(os.environ['OUT'])/'cache/topweather/current.json';d=json.loads(p.read_text());d['fetchedAt']=int((time.time()-7300)*1000)
q=p.with_suffix('.tmp');q.write_text(json.dumps(d));q.replace(p)
PYWEATHER
sleep 1
state >"$OUT/stale-state.txt"
cp "$OUT/weather-backup.json" "$OUT/cache/topweather/current.json"
sleep 1
state >"$OUT/fresh-state.txt"
# Construct the real settings UI in this private session, never on the user's display.
WAYLAND_DISPLAY=dynwall-smoke GDK_BACKEND=wayland /usr/bin/python3 - <<'PYGTK'
import importlib.machinery,os,subprocess
from gi.repository import GLib
from pathlib import Path
m=importlib.machinery.SourceFileLoader('settings_smoke',str(Path(os.environ['ROOT'])/'dynwall-settings')).load_module()
app=m.DynwallSettingsApp();app.register(None);window=m.SettingsWindow(app)
cfg=window._collect();assert cfg['weather_fps']==30 and cfg['weather_quality']=='balanced'
assert cfg['enabled'] is True
assert window.master_row.get_title() == 'Enable Dynwall'
assert cfg['seasonal_effects'] is True
assert cfg['landscape_enabled'] is True
assert cfg['background'] == 'auto'
for index, background in enumerate(m.BACKGROUNDS):
 window.background_row.set_selected(index)
 assert window._collect()['background'] == background
 assert window.scene_description.get_text().startswith(m.BACKGROUND_DESCRIPTIONS[index])
 assert window.scene_preview.get_visible()
 assert window.scene_preview.get_paintable() is not None
window.background_row.set_selected(m.BACKGROUNDS.index('alpine'))
window.present()
loop=GLib.MainLoop()
def capture_settings():
 subprocess.run(['gdbus','call','--session','--dest','org.gnome.Shell','--object-path',
                 '/org/gnome/Shell/Screenshot','--method','org.gnome.Shell.Screenshot.Screenshot',
                 'false','false',str(Path(os.environ['OUT'])/'settings.png')],check=True)
 loop.quit()
 return False
GLib.timeout_add(1000,capture_settings)
loop.run()
import sys
sys.path.insert(0,str(Path(os.environ['ROOT'])/'tests'))
from check_living_settings_gnome import exercise
exercise(window,Path(os.environ['OUT']))
window.landscape_row.set_active(False)
assert window._collect()['landscape_enabled'] is False
window.seasonal_row.set_active(False)
assert window._collect()['seasonal_effects'] is False
window.destroy();print('GTK settings construction: PASS')
PYGTK
"/usr/bin/python3" "$ROOT/tests/check_living_gnome.py"
# Trigger a deterministic event only inside the private Shell, independent of
# the real season/random delay. Exercise production frame uploads on both actors.
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
    '(() => {const e=Main.extensionManager.lookup("dynwall@rucaradio").stateObj; e._stopFrame(); e._autumnEnabled=true; e._gusts._wait=0; for(let i=0;i<30;i++)e._draw(.1); return {leavesVisible:e._effects.every(({effect})=>effect._uploads._values.get("u_leaves")?.[1]>.9),observedCoverage:e._target.u_coverage};})()' \
    >"$OUT/gust-active-state.txt"
grep -q '"leavesVisible":true' "$OUT/gust-active-state.txt"
grep -q '"observedCoverage":0.65' "$OUT/gust-active-state.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/autumn-gust.png" >/dev/null
python3 - <<'PYSEASON'
import json,os
from pathlib import Path
p=Path(os.environ['OUT'])/'cache/dynwall/scene.json';d=json.loads(p.read_text());d['renderer']['seasonalEffects']=False
q=p.with_suffix('.tmp');q.write_text(json.dumps(d));q.replace(p)
PYSEASON
sleep 1
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
    '(() => {const e=Main.extensionManager.lookup("dynwall@rucaradio").stateObj; return {seasonalDisabled:!e._scene.seasonalEffects,leavesHidden:e._effects.every(({effect})=>effect._uploads._values.get("u_leaves")?.[1]===0),weatherRunning:!!e._frameSource,observedCoverage:e._target.u_coverage};})()' \
    >"$OUT/gust-disabled-state.txt"
for expected in '"seasonalDisabled":true' '"leavesHidden":true' '"weatherRunning":true' '"observedCoverage":0.65'; do
    grep -q "$expected" "$OUT/gust-disabled-state.txt"
done
echo 'GNOME autumn gust uploads and seasonal off switch: PASS'
# Landscape control must remove terrain without disabling ordinary sky animation.
python3 - <<'PYLANDSCAPE'
import json,os
from pathlib import Path
p=Path(os.environ['OUT'])/'cache/dynwall/scene.json';d=json.loads(p.read_text());d['spec']['landscape']={'style':'none'}
q=p.with_suffix('.tmp');q.write_text(json.dumps(d));q.replace(p)
PYLANDSCAPE
sleep 2
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
    '(() => {const e=Main.extensionManager.lookup("dynwall@rucaradio").stateObj; return {landscapeOff:e._effects.every(({effect})=>effect._uploads._values.get("u_landscape")?.[0]===0),weatherRunning:!!e._frameSource};})()' \
    >"$OUT/landscape-disabled-state.txt"
grep -q '"landscapeOff":true' "$OUT/landscape-disabled-state.txt"
grep -q '"weatherRunning":true' "$OUT/landscape-disabled-state.txt"
echo 'GNOME landscape off switch: PASS'
# Exercise every terrain type through the actual running Cogl shader, using
# atomic scene replacement and the same discrete selector as the settings app.
for scene_style in hills alpine dunes ocean none; do
SCENE_STYLE="$scene_style" python3 - <<'PYBACKGROUND'
import json,os
from pathlib import Path
p=Path(os.environ['OUT'])/'cache/dynwall/scene.json';d=json.loads(p.read_text())
d['spec']['landscape']={'style':os.environ['SCENE_STYLE'],'height':.28,'mist':.5}
q=p.with_suffix('.tmp');q.write_text(json.dumps(d));q.replace(p)
PYBACKGROUND
sleep 1
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval \
    '(() => {const e=Main.extensionManager.lookup("dynwall@rucaradio").stateObj; return {style:e._target.u_landscape[0],uploaded:e._effects.map(({effect})=>effect._uploads._values.get("u_landscape")?.[0]),running:!!e._frameSource};})()' \
    >"$OUT/background-$scene_style.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Screenshot --method org.gnome.Shell.Screenshot.Screenshot false false "$OUT/background-$scene_style.png" >/dev/null
done
python3 - <<'PYBACKGROUND'
import os
from pathlib import Path
p=Path(os.environ['OUT'])
for style,code in [('hills',1),('alpine',2),('dunes',3),('ocean',4),('none',0)]:
 text=(p/f'background-{style}.txt').read_text()
 assert f'"style":{code}' in text and f'"uploaded":[{code},{code}]' in text and '"running":true' in text, text
print('GNOME scene selector and all terrain uniforms: PASS')
PYBACKGROUND
cat "$OUT/info.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionErrors dynwall@rucaradio | tee "$OUT/errors.txt"
gdbus introspect --session --dest org.gnome.Shell --object-path /org/gnome/Mutter/DebugControl >"$OUT/debug-control.txt" || true
# Enable/disable round trip through the actual Shell extension manager.
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.DisableExtension dynwall@rucaradio >"$OUT/disable.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionInfo dynwall@rucaradio >"$OUT/disabled-info.txt"
state >"$OUT/disabled-state.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.EnableExtension dynwall@rucaradio >"$OUT/enable.txt"
sleep 2
stacking >"$OUT/window-reenabled-state.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionInfo dynwall@rucaradio >"$OUT/reenabled-info.txt"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionErrors dynwall@rucaradio | tee "$OUT/reenabled-errors.txt"
python3 - <<'PY'
import os,re
from pathlib import Path
p=Path(os.environ['OUT'])
for name,want in [('info.txt',1),('disabled-info.txt',2),('reenabled-info.txt',1)]:
 s=(p/name).read_text(); assert re.search(r"'state': <(?:uint32 )?"+str(want)+r'[.>]',s),(name,s)
for name in ['errors.txt','reenabled-errors.txt']:
 assert (p/name).read_text().strip() in ['(@as [],)', '([],)' ],(name,(p/name).read_text())
for name,running,groups in [('running-state.txt',True,1),('display-off-state.txt',False,1),('display-on-state.txt',True,1),('paused-state.txt',False,1),('resumed-state.txt',True,1),('disabled-state.txt',False,0),('scene-disabled-state.txt',False,0),('scene-enabled-state.txt',True,1)]:
 s=(p/name).read_text(); assert s.startswith('(true,'),(name,s)
 assert f'"running":{str(running).lower()}' in s,(name,s)
 assert f'"groups":{groups}' in s,(name,s)
assert '"effects":2' in (p/'running-state.txt').read_text()
assert '"targetCoverage":0,' in (p/'stale-state.txt').read_text()
assert '"targetCoverage":0.65,' in (p/'fresh-state.txt').read_text()
assert (p/'desktop.png').exists()
for name in ['window-mapped-state.txt', 'window-raised-state.txt', 'window-background-refresh-state.txt', 'window-recreated-state.txt', 'window-reenabled-state.txt']:
 s=(p/name).read_text(); assert s.startswith('(true,'),(name,s)
 for expected in ['"windows":2', '"weatherVisible":true', '"belowAll":true', '"focused":true']:
  assert expected in s,(name,s)
from PIL import Image
im=Image.open(p/'windows.png').convert('RGB')
visible_pixels=sum(r>240 and g<15 and b>240 for r,g,b in im.getdata())
assert visible_pixels>100000, f'Application windows are covered: only {visible_pixels} magenta pixels'
refreshed=Image.open(p/'background-refreshed.png').convert('RGB')
green_pixels=sum(r<15 and g>240 and b<15 for r,g,b in refreshed.getdata())
assert green_pixels<1000, f'Static background covered weather: {green_pixels} green pixels'
print('Real application map/raise/recreate/re-enable stacking and visible pixels: PASS')
print('GNOME drawing/pause/resume/disable/re-enable: PASS')
PY
# Exercise actual desktop icons and a secondary-click menu with applications out
# of the way, while the weather actor remains visible in this private session.
kill "$APP_PID"
wait "$APP_PID" || true
APP_PID=
WAYLAND_DISPLAY=dynwall-smoke GDK_BACKEND=wayland "$ROOT/tests/check_desktop.sh"
INNER
printf 'Artifacts: %s\n' "$OUT"
