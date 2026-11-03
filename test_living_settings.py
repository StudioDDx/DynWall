"""Native settings contracts without opening the user's desktop."""
import copy,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import dynwall_living_settings as ui
class Value:
 def __init__(self,value=None):self.value=value
 def get_value(self):return self.value
 def get_active(self):return self.value
 def get_selected(self):return self.value
 def set_subtitle(self,value):self.value=value
 def set_sensitive(self,value):self.sensitive=value
 def set_visible(self,value):self.visible=value
 def set_paintable(self,value):self.value=value
class SettingsContractTests(unittest.TestCase):
 def test_local_clock_boundaries(self):
  self.assertEqual(ui.clock_minute('00:00'),0);self.assertEqual(ui.clock_minute('23:59'),1439)
  for value in ('24:00','12:60','-1:00','08','1:2:3','NaN:10','８:00',None,True):
   with self.subTest(value=value),self.assertRaises(ValueError):ui.clock_minute(value)
 def test_preview_private_atomic_and_observations_untouched(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);weather=root/'current.json';weather.write_text('unchanged')
   cfg={'background':'alpine','api_key':'secret-test','scene_customization':{'mist':.8}};before=copy.deepcopy(cfg)
   result=ui.publish_preview(cfg,12,'snow',now=100,directory=root)
   self.assertEqual(result['generatedAt'],100000);self.assertEqual(result['selection']['background'],'alpine')
   self.assertNotIn('secret-test',json.dumps(result));self.assertEqual(json.loads((root/'preview.json').read_text()),result)
   self.assertEqual((root/'preview.json').stat().st_mode&0o777,0o600);self.assertEqual(weather.read_text(),'unchanged');self.assertEqual(cfg,before)
 def test_bad_preview_preserves_last_request(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'preview.json';path.write_text('last-good')
   for hour,scenario in [(float('nan'),'rain'),(float('inf'),'day'),(True,'day'),(12,'unknown')]:
    with self.subTest(hour=hour),self.assertRaises(ValueError):ui.publish_preview({},hour,scenario,directory=td)
    self.assertEqual(path.read_text(),'last-good')
 def test_return_live_and_reset_preserve_other_state(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'environment.json').write_text('environment');(root/'scene.json').write_text('scene')
   ui.publish_preview({},6,'sunrise',directory=root);ui.remove_preview(directory=root);ui.remove_preview(directory=root)
   self.assertFalse((root/'preview.json').exists());self.assertEqual((root/'scene.json').read_text(),'scene')
   ui.publish_reset(now=123,directory=root)
   self.assertEqual(json.loads((root/'environment-reset.json').read_text()),{'generatedAt':123000});self.assertEqual((root/'environment.json').read_text(),'environment')
 def test_collection_preserves_credentials_and_unknown_keys(self):
  w=types.SimpleNamespace(_living_packs=[{'id':'woodland'}],pack_row=Value(0),_living_custom_rows={k:Value(v)for k,v in {'horizon':.8,'terrain_scale':1,'mist':.8,'warmth':.2,'darkness':.1,'animation_intensity':.5}.items()},_living_presets={},_living_favorites=[],_living_schedule_entries=[],schedule_enabled_row=Value(False),rotation_row=Value(30),persistent_weather_row=Value(False),atmospheric_row=Value(0),battery_saver_row=Value(True))
  cfg={'background':'ridges','api_key':'secret-test','unknown':{'keep':True}};result=ui.collect_living(w,cfg)
  self.assertEqual(result['api_key'],'secret-test');self.assertEqual(result['unknown'],{'keep':True});self.assertEqual(result['landscape_pack'],'woodland');self.assertFalse(result['persistent_weather']);self.assertEqual(result['atmospheric_intensity'],0);self.assertNotIn('landscape_pack',cfg)
class PresetSafetyTests(unittest.TestCase):
 def test_preset_save_does_not_activate_unsaved_schedule(self):
  original=ui.normalize_living_config({'background':'ridges','api_key':'secret-test','schedule':{'enabled':False}});unsaved=copy.deepcopy(original);unsaved['background']='alpine';unsaved['schedule']['enabled']=True;saved=[]
  w=types.SimpleNamespace(cfg=copy.deepcopy(original),_collect=lambda:unsaved,preset_name_row=types.SimpleNamespace(get_text=lambda:'Evening'),_living_presets={},_living_persist_config=lambda value:saved.append(copy.deepcopy(value)),_toast=lambda message:None)
  with patch.object(ui,'_refresh_presets'):ui._save_preset(w)
  self.assertEqual(saved[0]['background'],'ridges');self.assertFalse(saved[0]['schedule']['enabled']);self.assertEqual(saved[0]['presets']['Evening']['background'],'alpine');self.assertEqual(saved[0]['api_key'],'secret-test')
 def test_failed_preset_save_keeps_last_good_config(self):
  original=ui.normalize_living_config({'background':'ridges'});messages=[]
  def fail(value):raise OSError('fixture failure')
  w=types.SimpleNamespace(cfg=copy.deepcopy(original),_collect=lambda:original,preset_name_row=types.SimpleNamespace(get_text=lambda:'Evening'),_living_presets={},_living_persist_config=fail,_toast=messages.append)
  with patch.object(ui,'_refresh_presets'):ui._save_preset(w)
  self.assertEqual(w.cfg,original);self.assertEqual(w._living_presets,{});self.assertTrue(any('failed' in message.lower()for message in messages))
class PreviewRaceTests(unittest.TestCase):
 def test_old_render_cannot_replace_new_generation(self):
  processes=[]
  class Process:
   def __init__(self,args):self.args=args
   def communicate_utf8_async(self,_input,_cancel,callback):self.callback=callback
   def communicate_utf8_finish(self,result):return True,None,''
   def get_successful(self):return True
  class Factory:
   @staticmethod
   def new(args,flags):
    process=Process(args);processes.append(process);return process
  gio=types.SimpleNamespace(Subprocess=Factory,SubprocessFlags=types.SimpleNamespace(STDOUT_SILENCE=1,STDERR_PIPE=2));gdk=types.SimpleNamespace(Texture=types.SimpleNamespace(new_from_filename=lambda path:path));picture=Value();status=Value()
  w=types.SimpleNamespace(_living_preview_source=0,_living_preview_generation=1,_living_preview_active=True,_living_preview_process=None,preview_weather_row=Value(1),preview_hour_scale=Value(12),_collect=lambda:{'background':'ridges'},living_preview_picture=picture,scene_preview=None,preview_status=status)
  with tempfile.TemporaryDirectory()as td,patch.object(ui,'Gio',gio),patch.object(ui,'Gdk',gdk),patch.object(ui,'cache_directory',return_value=Path(td)):
   ui._render_preview(w);w._living_preview_generation=2;ui._render_preview(w);first,second=processes
   self.assertNotEqual(first.args[-1],second.args[-1]);first.callback(first,None);self.assertIsNone(picture.value);second.callback(second,None);self.assertEqual(picture.value,second.args[-1]);self.assertIn('Preview',status.value)
