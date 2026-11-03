"""Native controls for DynWall's local living-environment presentation."""
import copy,math,os,time
from pathlib import Path
import gi
gi.require_version('Gtk','4.0');gi.require_version('Gdk','4.0');gi.require_version('Adw','1')
from gi.repository import Adw,Gdk,Gio,GLib,Gtk
from dynwall_living import normalize_living_config,list_packs,load_pack,pack_directory,import_pack,export_pack,save_preset,load_preset,add_favorite,remove_favorite
from dynwall_weather import write_scene
SCENES=['auto','ridges','alpine','dunes','ocean','sky']
SCENARIOS=['sunrise','day','night','rain','snow','storm']
CUSTOM=[('horizon','Horizon height',.5,.95,.01),('terrain_scale','Terrain scale',.5,2,.05),('mist','Mist',0,1,.05),('warmth','Warmth',-1,1,.05),('darkness','Darkness',0,1,.05),('animation_intensity','Animation intensity',0,2,.05)]
def cache_directory():return Path(os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')/'dynwall'
def clock_minute(text):
 if not isinstance(text,str):raise ValueError('Use a time in HH:MM format')
 parts=text.strip().split(':')
 if len(parts)!=2 or not all(p.isascii() and p.isdigit() for p in parts):raise ValueError('Use a time in HH:MM format')
 hour,minute=map(int,parts)
 if not 0<=hour<=23 or not 0<=minute<=59:raise ValueError('Time must be between 00:00 and 23:59')
 return hour*60+minute
def presentation_selection(cfg):
 cfg=normalize_living_config(cfg)
 return {key:copy.deepcopy(cfg[key])for key in ('background','landscape_pack','scene_customization')}
def publish_preview(selection,hour,scenario,*,now=None,directory=None):
 if isinstance(hour,bool) or not isinstance(hour,(int,float)) or not 0<=hour<=24 or not math.isfinite(hour):raise ValueError('Preview hour must be finite and between 0 and 24')
 if scenario not in SCENARIOS:raise ValueError('Unknown preview weather scenario')
 request={'enabled':True,'hour':hour,'scenario':scenario,'generatedAt':int((time.time()if now is None else now)*1000),'selection':presentation_selection(selection)}
 write_scene((cache_directory()if directory is None else Path(directory))/'preview.json',request)
 return request
def remove_preview(*,directory=None):
 target=(cache_directory()if directory is None else Path(directory))/'preview.json'
 try:target.unlink()
 except FileNotFoundError:pass
def publish_reset(*,now=None,directory=None):
 write_scene((cache_directory()if directory is None else Path(directory))/'environment-reset.json',{'generatedAt':int((time.time()if now is None else now)*1000)})
def _message(window,text):window._toast(str(text))
def _button(label,callback):
 button=Gtk.Button(label=label,valign=Gtk.Align.CENTER);button.connect('clicked',callback);return button
def _combo(title,labels,index=0):
 row=Adw.ComboRow(title=title,model=Gtk.StringList.new(labels));row.set_selected(max(0,index));return row
def _selection(window):return presentation_selection(window._collect())
def _refresh_scene():
 try:Gio.Subprocess.new(['/usr/bin/python3',str(Path(__file__).resolve().parent/'dynwall'),'--refresh-scene'],Gio.SubprocessFlags.STDOUT_SILENCE|Gio.SubprocessFlags.STDERR_SILENCE)
 except GLib.Error:pass
def _reload_packs(window,selected=None):
 selected=selected if selected is not None else window.cfg.get('landscape_pack','')
 window._living_packs=[{'id':'','name':'Built-in terrain'}]+list_packs()
 if selected and not any(p['id']==selected for p in window._living_packs):window._living_packs.append({'id':selected,'name':f'Unavailable: {selected}'})
 window.pack_row.set_model(Gtk.StringList.new([p['name']for p in window._living_packs]));window.pack_row.set_selected(next((i for i,p in enumerate(window._living_packs)if p['id']==selected),0))
def _import_dialog(window,folder):
 dialog=Gtk.FileDialog(title='Import landscape folder'if folder else 'Import landscape ZIP')
 def chosen(dialog,result):
  try:
   file=dialog.select_folder_finish(result)if folder else dialog.open_finish(result)
   if file is None or file.get_path()is None:return
   pack=import_pack(file.get_path());_reload_packs(window,pack['id']);_refresh_scene();_message(window,f"Imported {pack['name']}");_queue_preview(window)
  except (GLib.Error,OSError,ValueError,TypeError)as error:
   if not isinstance(error,GLib.Error)or not error.matches(Gio.io_error_quark(),Gio.IOErrorEnum.CANCELLED):_message(window,f'Import failed: {error}')
 if folder:dialog.select_folder(window,None,chosen)
 else:dialog.open(window,None,chosen)
def _export_dialog(window):
 identifier=window._living_packs[window.pack_row.get_selected()]['id']
 if not identifier:_message(window,'Select a landscape pack to export');return
 dialog=Gtk.FileDialog(title='Export landscape pack',initial_name=f'{identifier}.dynwall.zip')
 def chosen(dialog,result):
  try:
   file=dialog.save_finish(result)
   if file is None or file.get_path()is None:return
   export_pack(load_pack(pack_directory(identifier)),file.get_path());_message(window,'Landscape pack exported')
  except (GLib.Error,OSError,ValueError,TypeError)as error:
   if not isinstance(error,GLib.Error)or not error.matches(Gio.io_error_quark(),Gio.IOErrorEnum.CANCELLED):_message(window,f'Export failed: {error}')
 dialog.save(window,None,chosen)
def _preview_stop_process(window):
 process=getattr(window,'_living_preview_process',None);window._living_preview_process=None
 if process is not None:
  try:process.force_exit()
  except GLib.Error:pass
def _queue_preview(window):
 if not getattr(window,'_living_ready',False)or not window._living_preview_active:return
 window._living_preview_generation+=1;_preview_stop_process(window)
 if window._living_preview_source:GLib.Source.remove(window._living_preview_source)
 window._living_preview_source=GLib.timeout_add(180,lambda:_render_preview(window))
def _render_preview(window):
 window._living_preview_source=0;generation=window._living_preview_generation
 scenario=SCENARIOS[window.preview_weather_row.get_selected()];hour=window.preview_hour_scale.get_value()
 try:
  publish_preview(_selection(window),hour,scenario)
  output=cache_directory()/f'settings-preview-{os.getpid()}-{generation}.png'
  process=Gio.Subprocess.new(['/usr/bin/python3',str(Path(__file__).resolve().parent/'dynwall'),'--preview-output',str(output)],Gio.SubprocessFlags.STDOUT_SILENCE|Gio.SubprocessFlags.STDERR_PIPE)
  window._living_preview_process=process
 except (OSError,ValueError,TypeError,GLib.Error)as error:_message(window,f'Preview failed: {error}');return GLib.SOURCE_REMOVE
 def finished(process,result):
  try:
   _ok,_stdout,stderr=process.communicate_utf8_finish(result)
   if generation!=window._living_preview_generation or not window._living_preview_active:return
   if not process.get_successful():_message(window,'Preview failed: '+((stderr or '').strip()[-240:]or'renderer exited'));return
   texture=Gdk.Texture.new_from_filename(str(output));window.living_preview_picture.set_paintable(texture);window.living_preview_picture.set_visible(True)
   if getattr(window,'scene_preview',None)is not None:window.scene_preview.set_paintable(texture)
   minute=round(hour*60)%1440;window.preview_status.set_subtitle(f'Preview · {minute//60:02d}:{minute%60:02d} · {scenario.title()} — live observations are untouched')
  except (GLib.Error,OSError,ValueError)as error:
   if generation==window._living_preview_generation and window._living_preview_active:_message(window,f'Preview failed: {error}')
  finally:
   if window._living_preview_process is process:window._living_preview_process=None
   try:output.unlink()
   except OSError:pass
 process.communicate_utf8_async(None,None,finished);return GLib.SOURCE_REMOVE
def _start_preview(window):
 if not window._living_preview_active and getattr(window,'scene_preview',None)is not None:window._living_live_paintable=window.scene_preview.get_paintable()
 window._living_preview_active=True;window.preview_status.set_subtitle('Preview active — rendering the selected time and weather');window.return_live_button.set_sensitive(True);_queue_preview(window)
def close_preview(window):
 window._living_preview_active=False;window._living_preview_generation+=1
 if window._living_preview_source:GLib.Source.remove(window._living_preview_source);window._living_preview_source=0
 _preview_stop_process(window)
 try:remove_preview()
 except OSError as error:_message(window,f'Could not return to live: {error}');return False
 window.preview_status.set_subtitle('Live · current local time and TopWeather observations');window.return_live_button.set_sensitive(False);window.living_preview_picture.set_visible(False)
 if getattr(window,'_living_live_paintable',None)is not None:window.scene_preview.set_paintable(window._living_live_paintable)
 return False
def _scenario_changed(window):
 if not window._living_ready:return
 scenario=SCENARIOS[window.preview_weather_row.get_selected()]
 if scenario in ('sunrise','day','night'):window.preview_hour_scale.set_value({'sunrise':6,'day':12,'night':0}[scenario])
 _queue_preview(window)
def _apply_selection(window,selection):
 value=presentation_selection(selection);window.background_row.set_selected(SCENES.index(value['background']));_reload_packs(window,value['landscape_pack'])
 for key,row in window._living_custom_rows.items():row.set_value(value['scene_customization'][key])
 _queue_preview(window)
def _refresh_presets(window):
 window._living_preset_names=sorted(window._living_presets);window.preset_row.set_model(Gtk.StringList.new(window._living_preset_names or['No saved presets']));window.preset_row.set_selected(0);window.preset_load_button.set_sensitive(bool(window._living_preset_names))
def _save_preset(window):
 try:
  name=window.preset_name_row.get_text().strip()
  if not name:raise ValueError('Enter a preset name')
  snapshot=save_preset(window._collect(),name);persisted=copy.deepcopy(window.cfg);persisted['presets']=copy.deepcopy(snapshot['presets'])
  window._living_persist_config(persisted);window.cfg=persisted;window._living_presets=copy.deepcopy(persisted['presets']);_refresh_presets(window);_message(window,f'Saved preset {name}')
 except (OSError,ValueError,TypeError)as error:_message(window,f'Preset failed: {error}')
def _load_preset(window):
 if not window._living_preset_names:return
 name=window._living_preset_names[window.preset_row.get_selected()]
 try:_apply_selection(window,load_preset(window._collect(),name));_message(window,f'Loaded {name}; Save applies it to live wallpaper')
 except (ValueError,TypeError,KeyError)as error:_message(window,f'Preset failed: {error}')
def _selection_title(selection):
 name=str(selection.get('background','auto')).title();pack=selection.get('landscape_pack');return f'{name} · {pack}'if pack else name
def _refresh_favorites(window):
 window.favorite_row.set_model(Gtk.StringList.new([_selection_title(s)for s in window._living_favorites]or['No favorites']));window.favorite_row.set_selected(0);window.favorite_remove_button.set_sensitive(bool(window._living_favorites));window.favorite_use_button.set_sensitive(bool(window._living_favorites))
def _favorite_add(window):
 try:window._living_favorites=copy.deepcopy(add_favorite(window._collect())['favorites']);_refresh_favorites(window);_message(window,'Added current scene to favorites; Save stores the collection')
 except (ValueError,TypeError)as error:_message(window,error)
def _favorite_remove(window):
 if window._living_favorites:window._living_favorites=copy.deepcopy(remove_favorite(window._collect(),window.favorite_row.get_selected())['favorites']);_refresh_favorites(window)
def _favorite_use(window):
 if window._living_favorites:_apply_selection(window,window._living_favorites[window.favorite_row.get_selected()])
def _refresh_schedule(window):
 for row in window._living_schedule_rows:window._living_schedule_group.remove(row)
 window._living_schedule_rows=[]
 for index,item in enumerate(window._living_schedule_entries):
  minute=item['minute'];row=Adw.ActionRow(title=f'{minute//60:02d}:{minute%60:02d} · {_selection_title(item)}');row.add_suffix(_button('Remove',lambda _button,i=index:_schedule_remove(window,i)));window._living_schedule_group.add(row);window._living_schedule_rows.append(row)
def _schedule_remove(window,index):window._living_schedule_entries.pop(index);_refresh_schedule(window)
def _schedule_add(window):
 try:
  minute=clock_minute(window.schedule_time_row.get_text());entry={'minute':minute,**_selection(window)};entries=[item for item in window._living_schedule_entries if item['minute']!=minute]+[entry]
  if len(entries)>24:raise ValueError('A schedule supports at most 24 entries')
  window._living_schedule_entries=sorted(entries,key=lambda item:item['minute']);_refresh_schedule(window);_message(window,'Scheduled the current scene; Save stores this change')
 except (ValueError,TypeError)as error:_message(window,error)
def collect_living(window,cfg):
 cfg=dict(cfg);cfg['landscape_pack']=window._living_packs[window.pack_row.get_selected()]['id'];cfg['scene_customization']={key:row.get_value()for key,row in window._living_custom_rows.items()};cfg['presets']=copy.deepcopy(window._living_presets);cfg['favorites']=copy.deepcopy(window._living_favorites)
 cfg['schedule']={'enabled':window.schedule_enabled_row.get_active(),'entries':copy.deepcopy(window._living_schedule_entries),'rotation_minutes':int(window.rotation_row.get_value())};cfg['persistent_weather']=window.persistent_weather_row.get_active();cfg['atmospheric_intensity']=window.atmospheric_row.get_value();cfg['battery_saver']=window.battery_saver_row.get_active();return normalize_living_config(cfg)
def add_living_controls(window,page):
 window._living_page=page
 cfg=normalize_living_config(window.cfg);window.cfg=cfg;window._living_ready=False;window._living_preview_active=False;window._living_preview_generation=0;window._living_preview_source=0;window._living_preview_process=None;window._living_live_paintable=None
 window._living_presets=copy.deepcopy(cfg['presets']);window._living_favorites=copy.deepcopy(cfg['favorites']);window._living_schedule_entries=copy.deepcopy(cfg['schedule']['entries']);window._living_schedule_rows=[]
 packs=Adw.PreferencesGroup(title='Custom landscapes',description='Local illustrated or photographic foregrounds with animated sky above the marked horizon. No downloads or API key.');page.add(packs)
 window.pack_row=_combo('Landscape pack',['Built-in terrain']);packs.add(window.pack_row);_reload_packs(window)
 actions=Adw.ActionRow(title='Local pack files')
 for label,callback in [('Import ZIP',lambda _button:_import_dialog(window,False)),('Import folder',lambda _button:_import_dialog(window,True)),('Export',lambda _button:_export_dialog(window))]:actions.add_suffix(_button(label,callback))
 packs.add(actions)
 custom=Adw.PreferencesGroup(title='Scene customization',description='Adjust the composition. Neutral values preserve built-in art.');page.add(custom);window._living_custom_group=custom;window._living_custom_rows={}
 for key,title,minimum,maximum,step in CUSTOM:
  row=Adw.SpinRow.new_with_range(minimum,maximum,step);row.set_title(title);row.set_digits(2);row.set_value(cfg['scene_customization'][key]);custom.add(row);window._living_custom_rows[key]=row
 window.preset_row=_combo('Named preset',['No saved presets']);custom.add(window.preset_row);preset_actions=Adw.ActionRow(title='Recall saved composition');window.preset_load_button=_button('Load preset',lambda _button:_load_preset(window));preset_actions.add_suffix(window.preset_load_button);custom.add(preset_actions)
 window.preset_name_row=Adw.EntryRow(title='Preset name');window.preset_name_row.add_suffix(_button('Save preset',lambda _button:_save_preset(window)));custom.add(window.preset_name_row);_refresh_presets(window)
 preview=Adw.PreferencesGroup(title='Time and weather preview',description='Temporary, separate from TopWeather. The native wallpaper follows preview while animation is enabled. Closing settings returns to live.');page.add(preview);window._living_preview_group=preview
 window.preview_status=Adw.ActionRow(title='Presentation mode',subtitle='Live · current local time and TopWeather observations');preview.add(window.preview_status)
 hour_row=Adw.ActionRow(title='Time of day');window.preview_hour_scale=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,24,.25);window.preview_hour_scale.set_digits(2);window.preview_hour_scale.set_draw_value(True);window.preview_hour_scale.set_size_request(220,-1);window.preview_hour_scale.set_valign(Gtk.Align.CENTER)
 current=time.localtime();hour=current.tm_hour+current.tm_min/60;window.preview_hour_scale.set_value(hour);hour_row.add_suffix(window.preview_hour_scale);preview.add(hour_row)
 scenario=2 if hour<5 or hour>=20 else 0 if hour<8 else 1
 window.preview_weather_row=_combo('Weather scenario',[name.title()for name in SCENARIOS],scenario);preview.add(window.preview_weather_row)
 preview_actions=Adw.ActionRow(title='Temporary presentation');preview_actions.add_suffix(_button('Preview',lambda _button:_start_preview(window)));window.return_live_button=_button('Return to live',lambda _button:close_preview(window));window.return_live_button.set_sensitive(False);preview_actions.add_suffix(window.return_live_button);preview.add(preview_actions)
 window.living_preview_picture=Gtk.Picture(can_shrink=True);window.living_preview_picture.set_content_fit(Gtk.ContentFit.CONTAIN);window.living_preview_picture.set_size_request(-1,150);window.living_preview_picture.set_visible(False);preview.add(window.living_preview_picture)
 effects=Adw.PreferencesGroup(title='Living environment',description='Snow, wet ground and puddles are artistic persistence, not measured accumulation. TopWeather remains authoritative.');page.add(effects)
 window.persistent_weather_row=Adw.SwitchRow(title='Retain snow and wetness',subtitle='Accumulate gradually, then dry and melt; safe across pause and resume');window.persistent_weather_row.set_active(cfg['persistent_weather']);effects.add(window.persistent_weather_row)
 reset_row=Adw.ActionRow(title='Reset accumulated environment')
 def reset(_button):
  try:publish_reset();_message(window,'Snow and wetness reset')
  except (OSError,ValueError,TypeError)as error:_message(window,f'Reset failed: {error}')
 window.environment_reset_button=_button('Reset',reset);window.environment_reset_button.set_sensitive(cfg['persistent_weather']);reset_row.add_suffix(window.environment_reset_button);effects.add(reset_row)
 window.persistent_weather_row.connect('notify::active',lambda row,_pspec:window.environment_reset_button.set_sensitive(row.get_active()))
 window.atmospheric_row=Adw.SpinRow.new_with_range(0,1,.1);window.atmospheric_row.set_title('Rare atmospheric moments');window.atmospheric_row.set_subtitle('0 turns off shooting stars, distant lightning, fireflies, pollen and birds');window.atmospheric_row.set_digits(1);window.atmospheric_row.set_value(cfg['atmospheric_intensity']);effects.add(window.atmospheric_row)
 if getattr(window,'seasonal_row',None)is not None:window.seasonal_row.set_title('Seasonal scenery and autumn gusts');window.seasonal_row.set_subtitle('Hemisphere-aware foliage and occasional blowing leaves')
 window.battery_saver_row=Adw.SwitchRow(title='Battery-aware rendering',subtitle='Lower frame cap and quality on battery; fully covered monitors pause');window.battery_saver_row.set_active(cfg['battery_saver']);effects.add(window.battery_saver_row)
 effects.add(Adw.ActionRow(title='Frame budget and quality',subtitle='Frame-rate cap and weather quality set configured GPU workload. No GPU-utilization estimate is shown.'))
 favorites=Adw.PreferencesGroup(title='Favorites',description='Keep local scene, pack and customization combinations. Save stores changes.');page.add(favorites);window.favorite_row=_combo('Favorite scene',['No favorites']);favorites.add(window.favorite_row)
 favorite_actions=Adw.ActionRow(title='Favorite collection');favorite_actions.add_suffix(_button('Add current',lambda _button:_favorite_add(window)));window.favorite_use_button=_button('Use',lambda _button:_favorite_use(window));window.favorite_remove_button=_button('Remove',lambda _button:_favorite_remove(window));favorite_actions.add_suffix(window.favorite_use_button);favorite_actions.add_suffix(window.favorite_remove_button);favorites.add(favorite_actions);_refresh_favorites(window)
 schedule=Adw.PreferencesGroup(title='Schedules and rotation',description='Local entries wrap midnight and take priority over favorite rotation. Preview overrides the schedule. Scheduling starts only when enabled and saved.');page.add(schedule);window._living_schedule_group=schedule
 window.schedule_enabled_row=Adw.SwitchRow(title='Enable scene schedule');window.schedule_enabled_row.set_active(cfg['schedule']['enabled']);schedule.add(window.schedule_enabled_row)
 window.schedule_time_row=Adw.EntryRow(title='Local time (HH:MM)');window.schedule_time_row.set_text('08:00');window.schedule_time_row.add_suffix(_button('Add current scene',lambda _button:_schedule_add(window)));schedule.add(window.schedule_time_row)
 window.rotation_row=Adw.SpinRow.new_with_range(0,1440,15);window.rotation_row.set_title('Favorite rotation interval (minutes)');window.rotation_row.set_subtitle('0 is off; minimum enabled interval is 5 minutes');window.rotation_row.set_value(cfg['schedule']['rotation_minutes']);schedule.add(window.rotation_row);_refresh_schedule(window)
 window._living_ready=True;window._living_start_preview=lambda:_start_preview(window);window._living_return_live=lambda:close_preview(window);window._living_queue_preview=lambda:_queue_preview(window)
 window.preview_hour_scale.connect('value-changed',lambda _scale:_queue_preview(window));window.preview_weather_row.connect('notify::selected',lambda _row,_pspec:_scenario_changed(window));window.pack_row.connect('notify::selected',lambda _row,_pspec:_queue_preview(window));window.background_row.connect('notify::selected',lambda _row,_pspec:_queue_preview(window))
 for row in window._living_custom_rows.values():row.connect('notify::value',lambda _row,_pspec:_queue_preview(window))
 window.connect('close-request',lambda _window:close_preview(window))
