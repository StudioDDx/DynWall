"""Behavioral checks inside smoke_gnome.sh's private session only."""
import ast
import copy
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(os.environ['ROOT']); OUT=Path(os.environ['OUT'])
sys.path.insert(0,str(ROOT))
from dynwall_weather import write_scene
from dynwall_living import normalize_living_config
cli=importlib.machinery.SourceFileLoader('living_smoke_cli',str(ROOT/'dynwall')).load_module()
scene=OUT/'cache/dynwall/scene.json'; preview=scene.with_name('preview.json')
original=json.loads(scene.read_text())
base=copy.deepcopy(original)
base['living']=normalize_living_config({'background':'ridges','scene_customization':{'warmth':.4,'mist':.7}})
base['sceneLibrary']=cli.build_scene_library();base['packs']=cli.build_pack_catalog()

def call(method,*args):
 return subprocess.check_output(['gdbus','call','--session','--dest','org.gnome.Shell','--object-path','/org/gnome/Shell','--method',method,*args],text=True)
def evaluate(source):
 raw=call('org.gnome.Shell.Eval',source)
 result=ast.literal_eval(raw.replace('(true,','(True,',1).replace('(false,','(False,',1))
 assert result[0],result
 return json.loads(result[1])
state_expr='''(() => {const e=Main.extensionManager.lookup('dynwall@rucaradio').stateObj;return {running:!!e?._frameSource,preview:!!e?._presentation?.preview,snow:e?._target?.u_snow,currentSnow:e?._current?.u_snow,currentCoverage:e?._current?.u_coverage,coverage:e?._target?.u_coverage,style:e?._target?.u_landscape?.[0],environment:e?._environment,interval:e?._interval,quality:e?._policy?.quality,fullscreen:e?._fullscreenMonitors(),windows:global.get_window_actors().filter(a=>a.meta_window.get_title()?.startsWith('Dynwall stacking test')).map(a=>({title:a.meta_window.get_title(),monitor:a.meta_window.get_monitor(),fullscreen:a.meta_window.is_fullscreen()})),visible:e?._effects?.map(({actor})=>actor.visible),custom:e?._effects?.[0]?.effect._uploads._values.get('u_tint'),pack:!!e?._packContent,packActors:e?._group?.get_children().filter(a=>a.name==='Dynwall landscape pack').length};})()'''
def state(): return evaluate(state_expr)
def until(predicate):
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  value=state()
  try:
   if predicate(value): return value
  except (KeyError,TypeError):
   pass
  time.sleep(.1)
 raise AssertionError(state())
def record(name,value): (OUT/f'living-{name}.json').write_text(json.dumps(value,indent=2))
def screenshot(name):
 subprocess.run(['gdbus','call','--session','--dest','org.gnome.Shell','--object-path','/org/gnome/Shell/Screenshot','--method','org.gnome.Shell.Screenshot.Screenshot','false','false',str(OUT/f'living-{name}.png')],check=True,stdout=subprocess.DEVNULL)
try:
 write_scene(scene,base)
 record('customization',until(lambda d:d['custom'] and abs(d['custom'][0]-.4)<.001))
 # Persist then restart the actual extension, retaining its location identity.
 value=state()['environment'];value.update(snow=.7,wetness=.8,updatedAt=int(time.time()*1000)-30000)
 write_scene(scene.with_name('environment.json'),value)
 call('org.gnome.Shell.Extensions.DisableExtension','dynwall@rucaradio')
 call('org.gnome.Shell.Extensions.EnableExtension','dynwall@rucaradio')
 record('restart',until(lambda d:d['running'] and d['environment']['snow']>.5))
 assert scene.with_name('environment.json').stat().st_mode&0o777==0o600
 observed=(OUT/'cache/topweather/current.json').read_bytes()
 persisted=scene.with_name('environment.json').read_bytes()
 write_scene(preview,{'enabled':True,'hour':12,'scenario':'snow','generatedAt':int(time.time()*1000),'selection':{'background':'alpine'}})
 record('preview',until(lambda d:d['preview'] and d['snow']>0 and abs(d['currentSnow']-d['snow'])<1e-6))
 assert scene.with_name('environment.json').read_bytes()==persisted
 assert (OUT/'cache/topweather/current.json').read_bytes()==observed
 screenshot('snow-preview')
 preview.unlink()
 record('live',until(lambda d:not d['preview'] and abs(d['coverage']-.65)<.001 and d['currentSnow']==0 and abs(d['currentCoverage']-.65)<.001))
 # Schedule material resolution happens in the live extension, without another publisher.
 scheduled=copy.deepcopy(base);scheduled['living']['schedule']={'enabled':True,'entries':[{'minute':0,'background':'ocean','landscape_pack':''}],'rotation_minutes':0}
 write_scene(scene,scheduled);record('schedule',until(lambda d:d['style']==4))
 # Real app windows cover one monitor, then both. Mutter supplies actual state.
 evaluate('''(() => {const w=global.get_window_actors().filter(a=>a.meta_window.get_title()?.startsWith('Dynwall stacking test')).map(a=>a.meta_window);const first=w.find(item=>item.get_title()==='Dynwall stacking test 1'),second=w.find(item=>item.get_title()==='Dynwall stacking test 2');first.move_to_monitor(0);second.move_to_monitor(1);first.make_fullscreen();return true;})()''')
 record('one-fullscreen',until(lambda d:d['fullscreen']==[True,False] and d['running'] and d['visible']==[False,True]))
 evaluate('''(() => {const w=global.get_window_actors().find(a=>a.meta_window.get_title()==='Dynwall stacking test 2').meta_window;w.move_to_monitor(1);w.activate(global.get_current_time());w.make_fullscreen();return true;})()''')
 record('all-fullscreen',until(lambda d:all(d['fullscreen']) and not d['running']))
 evaluate('''(() => {for(const a of global.get_window_actors())if(a.meta_window.get_title()?.startsWith('Dynwall stacking test'))a.meta_window.unmake_fullscreen();return true;})()''')
 until(lambda d:d['running'] and not any(d['fullscreen']))
 # Inject the power input solely into the private extension; never change host UPower.
 evaluate("(() => {const e=Main.extensionManager.lookup('dynwall@rucaradio').stateObj;e._onBattery=true;e._sync();return true;})()")
 record('battery',until(lambda d:d['interval']>=67 and d['quality']=='low'))
 evaluate("(() => {const e=Main.extensionManager.lookup('dynwall@rucaradio').stateObj;e._onBattery=false;e._sync();return true;})()")
 packed=copy.deepcopy(base);packed['living']['landscape_pack']='woodland'
 write_scene(scene,packed)
 record('pack',until(lambda d:d['pack'] and d['packActors']==1 and d['style']==0))
 time.sleep(.7);screenshot('woodland')
 # Reset is immediate and remains safe on restart; disabling effects clears uploads.
 write_scene(scene.with_name('environment-reset.json'),{'generatedAt':int(time.time()*1000)})
 record('reset',until(lambda d:d['environment']['snow']==0))
 packed['living']['persistent_weather']=False;write_scene(scene,packed)
 record('effects-off',until(lambda d:d['environment']['snow']==0 and d['environment']['wetness']==0))
 print('GNOME living features: preview/return, persistence/restart/reset, customization, schedules, pack, battery policy and per-monitor fullscreen: PASS')
finally:
 if preview.exists():preview.unlink()
 evaluate('''(() => {for(const a of global.get_window_actors())if(a.meta_window.get_title()?.startsWith('Dynwall stacking test'))a.meta_window.unmake_fullscreen();return true;})()''')
 write_scene(scene,original)
 time.sleep(.3)
