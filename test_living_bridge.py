"""Production bridge acceptance: controls must reach published and fallback scenes."""
import copy
import importlib.machinery
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dynwall_weather import build_scene_document

ROOT=Path(__file__).resolve().parent
class LivingBridgeTests(unittest.TestCase):
 def test_scene_carries_controls_without_mutating_config_or_art(self):
  cfg={'background':'alpine','persistent_weather':False,'scene_customization':{'warmth':.7},'api_key':'private-test'}
  spec={'gradient':['#123456','#abcdef']}; before=copy.deepcopy((cfg,spec))
  scene=build_scene_document(spec,None,cfg,now=1800000000)
  self.assertEqual(scene['living']['scene_customization']['warmth'],.7)
  self.assertIs(scene['living']['persistent_weather'],False)
  self.assertNotIn('api_key',json.dumps(scene))
  self.assertEqual((cfg,spec),before)
 def test_cli_preserves_living_controls_when_loading(self):
  m=importlib.machinery.SourceFileLoader('living_cli_bridge',str(ROOT/'dynwall')).load_module()
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'config.json';path.write_text(json.dumps({'background':'ridges','persistent_weather':False,'scene_customization':{'mist':.9}}))
   with patch.object(m,'CONFIG_FILE',path): cfg=m.load_config()
  self.assertFalse(cfg['persistent_weather']);self.assertEqual(cfg['scene_customization']['mist'],.9)
 def test_native_library_has_distinct_scene_materials_and_preview_phases(self):
  m=importlib.machinery.SourceFileLoader('living_library_bridge',str(ROOT/'dynwall')).load_module()
  library=m.build_scene_library()
  self.assertEqual(library['alpine']['day']['landscape']['style'],'alpine')
  self.assertEqual(library['ocean']['night']['landscape']['style'],'ocean')
  self.assertGreater(library['sky']['night']['stars'],0)
  self.assertNotEqual(library['ridges']['day']['gradient'],library['ridges']['night']['gradient'])
 def test_customization_changes_static_spec_without_mutating_source(self):
  m=importlib.machinery.SourceFileLoader('living_static_bridge',str(ROOT/'dynwall')).load_module()
  spec={'gradient':['#123456','#abcdef'],'landscape':{'style':'hills','height':.2,'mist':.5}}
  result=m.customize_fallback_spec(spec,{'horizon':.6,'terrain_scale':1.2,'mist':.8,'warmth':.5,'darkness':.3})
  self.assertNotEqual(result['gradient'],spec['gradient'])
  self.assertGreater(result['landscape']['height'],.2)
  self.assertEqual(result['landscape']['mist'],.8)
  self.assertEqual(spec['landscape']['height'],.2)
 def test_static_preview_scenarios_show_rain_snow_and_storm(self):
  from PIL import Image,ImageChops
  m=importlib.machinery.SourceFileLoader('living_preview_image_bridge',str(ROOT/'dynwall')).load_module()
  plain=Image.new('RGB',(320,180),'#506070')
  for scenario in ('rain','snow','storm'):
   with self.subTest(scenario=scenario):
    image=m.preview_weather_image(plain,scenario)
    self.assertIsNotNone(ImageChops.difference(plain,image).getbbox())
  self.assertIs(m.preview_weather_image(plain,'day'),plain)
 def test_neutral_customization_preserves_builtin_materials(self):
  from datetime import datetime
  m=importlib.machinery.SourceFileLoader('living_neutral_bridge',str(ROOT/'dynwall')).load_module()
  for style in ('hills','alpine','dunes','ocean','none'):
   spec=m.fallback_spec(datetime(2026,10,31,12),'clear',style)
   result=m.customize_fallback_spec(spec,{})
   self.assertEqual(result['gradient'],spec['gradient'])
   self.assertAlmostEqual(result['landscape']['height'],spec['landscape']['height'])
   self.assertAlmostEqual(result['landscape']['mist'],spec['landscape']['mist'])
 def test_real_sample_pack_reaches_native_scene_catalog(self):
  m=importlib.machinery.SourceFileLoader('living_pack_catalog_bridge',str(ROOT/'dynwall')).load_module()
  pack=m.build_pack_catalog()['woodland']
  self.assertTrue(Path(pack['foreground']).is_file())
  self.assertTrue(pack['foreground'].startswith(pack['root']+'/'))
  self.assertGreater(pack['horizon'],.1)
 def test_malformed_optional_landscape_retains_static_rendering(self):
  m=importlib.machinery.SourceFileLoader('living_bad_landscape',str(ROOT/'dynwall')).load_module()
  for value in (None,[],'invalid'):
   with self.subTest(value=value):
    result=m.customize_fallback_spec({'gradient':['#123456','#abcdef'],'landscape':value},{})
    self.assertIsInstance(result['landscape'],dict)
 def test_executable_uses_system_python_when_path_python_is_unusable(self):
  import os,subprocess
  with tempfile.TemporaryDirectory()as td:
   base=Path(td);fake=base/'bin';fake.mkdir();bad=fake/'python3';bad.write_text('#!/bin/sh\nexit 97\n');bad.chmod(0o700)
   config=base/'config/dynwall';config.mkdir(parents=True);(config/'config.json').write_text(json.dumps({'provider':'none','allow_network':False,'width':160,'height':90}))
   output=base/'preview.png';env={**os.environ,'PATH':str(fake)+':/usr/bin:/bin','XDG_CONFIG_HOME':str(base/'config'),'XDG_CACHE_HOME':str(base/'cache')}
   result=subprocess.run([str(ROOT/'dynwall'),'--preview-output',str(output)],env=env,capture_output=True,text=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(output.is_file())
