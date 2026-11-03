"""Actual GTK controls and asynchronous preview in the private session."""
import json,subprocess,time
from pathlib import Path
from gi.repository import GLib,Gtk
import dynwall_living_settings as ui

def exercise(window,output):
 output=Path(output);weather=output/'cache/topweather/current.json';observed=weather.read_bytes()
 assert not window.schedule_enabled_row.get_active()
 window.pack_row.set_selected(next(i for i,p in enumerate(window._living_packs)if p['id']=='woodland'));window._living_custom_rows['mist'].set_value(.8)
 window.preset_name_row.set_text('Private fixture');ui._save_preset(window)
 saved=json.loads((output/'config/dynwall/config.json').read_text())
 assert saved['background']=='auto' and not saved['schedule']['enabled'];assert saved['presets']['Private fixture']['landscape_pack']=='woodland'
 ui._favorite_add(window);window.schedule_time_row.set_text('00:00');ui._schedule_add(window)
 cfg=window._collect();assert len(cfg['favorites'])==1 and cfg['schedule']['entries'][0]['minute']==0
 assert not cfg['schedule']['enabled'] and cfg['scene_customization']['mist']==.8
 window.preview_weather_row.set_selected(4);window.preview_hour_scale.set_value(12);window._living_start_preview()
 loop=GLib.MainLoop();deadline=time.monotonic()+12;done=[]
 def ready():
  if window.living_preview_picture.get_paintable()is not None and window._living_preview_process is None:done.append(True);loop.quit();return False
  if time.monotonic()>deadline:loop.quit();return False
  return True
 GLib.timeout_add(50,ready);loop.run();assert done,'Real GTK preview failed to render'
 request=json.loads((output/'cache/dynwall/preview.json').read_text());assert request['scenario']=='snow' and request['selection']['landscape_pack']=='woodland';assert weather.read_bytes()==observed
 def settle():
  loop=GLib.MainLoop();GLib.timeout_add(250,lambda:(loop.quit(),False)[1]);loop.run()
 def capture(name,group):
  def widgets(root):
   yield root
   child=root.get_first_child()
   while child is not None:
    yield from widgets(child);child=child.get_next_sibling()
  scrollers=[widget for widget in widgets(window) if isinstance(widget,Gtk.ScrolledWindow)]
  adjustment=max((widget.get_vadjustment() for widget in scrollers),key=lambda item:item.get_upper()-item.get_page_size())
  ok,bounds=group.compute_bounds(window);assert ok
  adjustment.set_value(max(0,min(adjustment.get_value()+bounds.get_y()-12,adjustment.get_upper()-adjustment.get_page_size())));settle()
  subprocess.run(['gdbus','call','--session','--dest','org.gnome.Shell','--object-path','/org/gnome/Shell/Screenshot','--method','org.gnome.Shell.Screenshot.Screenshot','false','false',str(output/name)],check=True,stdout=subprocess.DEVNULL)
 capture('settings-living-preview.png',window._living_preview_group);capture('settings-living-customization.png',window._living_custom_group);capture('settings-living-schedules.png',window._living_schedule_group)
 window._living_return_live();assert not (output/'cache/dynwall/preview.json').exists();assert weather.read_bytes()==observed;assert not window.living_preview_picture.get_visible()
 window.persistent_weather_row.set_active(False);assert not window.environment_reset_button.get_sensitive();window.persistent_weather_row.set_active(True)
 print('GTK living controls: real preview/return, pack, isolated preset save, favorites, schedule, reset sensitivity: PASS')
