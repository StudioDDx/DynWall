"""Behavioral tests for local scene selections and landscape-pack storage."""
import copy
from datetime import datetime
import importlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image, ImageChops

try:
 import dynwall_living as living
except ImportError:
 living = None

class ConfigTests(unittest.TestCase):
 def test_normalization_preserves_private_and_unknown_keys(self):
  cfg={'api_key':'saved','extension_setting':{'x':1},'scene_customization':{'warmth':float('nan'),'terrain_scale':99}}
  result=living.normalize_living_config(cfg)
  self.assertEqual(result['api_key'],'saved'); self.assertEqual(result['extension_setting'],{'x':1})
  self.assertEqual(result['scene_customization']['warmth'],0); self.assertEqual(result['scene_customization']['terrain_scale'],2)
  self.assertFalse(result['schedule']['enabled']);self.assertNotIn('schedule',cfg)
 def test_nonfinite_bool_and_wrong_config_types_default_safely(self):
  for value in (None, [], {'scene_customization':True,'persistent_weather':'no','atmospheric_intensity':float('inf')}):
   result=living.normalize_living_config(value)
   self.assertEqual(result['scene_customization']['horizon'],.8)
   self.assertTrue(result['persistent_weather']);self.assertEqual(result['atmospheric_intensity'],.5)
 def test_preset_round_trip_changes_scene_without_credentials(self):
  cfg={'api_key':'secret','background':'alpine','scene_customization':{'mist':.8}}
  result=living.save_preset(cfg,'High peaks')
  self.assertNotIn('api_key',result['presets']['High peaks'])
  result['background']='ocean';result['api_key']='new secret'
  restored=living.load_preset(result,'High peaks')
  self.assertEqual(restored['background'],'alpine');self.assertEqual(restored['api_key'],'new secret')
  self.assertEqual(restored['scene_customization']['mist'],.8)
 def test_invalid_preset_name_is_rejected_without_mutating_input(self):
  cfg={'api_key':'saved'}
  with self.assertRaises(ValueError):living.save_preset(cfg,'  ')
  self.assertEqual(cfg,{'api_key':'saved'})
 def test_favorites_deduplicate_and_do_not_store_secrets(self):
  cfg={'background':'dunes','api_key':'secret'}
  result=living.add_favorite(cfg)
  result=living.add_favorite(result)
  self.assertEqual(len(result['favorites']),1);self.assertNotIn('api_key',result['favorites'][0])
  self.assertEqual(living.remove_favorite(result,0)['favorites'],[])
 def test_schedule_wraps_midnight_and_has_entry_priority_over_rotation(self):
  cfg={'schedule':{'enabled':True,'entries':[{'minute':480,'background':'alpine'},{'minute':1200,'background':'ocean'}],'rotation_minutes':5},'favorites':[{'background':'dunes'}]}
  at=lambda hour:datetime(2026,11,1,hour,0).timestamp()
  self.assertEqual(living.resolve_selection(cfg,at(1))['background'],'ocean')
  self.assertEqual(living.resolve_selection(cfg,at(8))['background'],'alpine')
 def test_rotation_is_bounded_and_disabled_by_default(self):
  cfg={'background':'ridges','favorites':[{'background':'alpine'},{'background':'ocean'}],'schedule':{'enabled':False,'rotation_minutes':5}}
  now=datetime(2026,11,1,0,7).timestamp()
  self.assertEqual(living.resolve_selection(cfg,now)['background'],'ridges')
  cfg['schedule']['enabled']=True
  self.assertEqual(living.resolve_selection(cfg,now)['background'],'ocean')
 def test_malformed_schedule_entries_and_duplicate_minutes_are_sanitized(self):
  result=living.normalize_living_config({'schedule':{'enabled':True,'entries':[None,{'minute':True},{'minute':-1},{'minute':1440},{'minute':60,'background':'alpine'},{'minute':60,'background':'ocean'}]}})
  self.assertEqual(result['schedule']['entries'],[{'minute':60,'background':'ocean','landscape_pack':'','scene_customization':living.DEFAULT_CUSTOMIZATION.copy()}])
 def test_preview_copy_does_not_change_observations_or_live_document(self):
  scene={'spec':{'gradient':['#123456','#abcdef']},'weather':{'current':{'rain':2}}}; original=copy.deepcopy(scene)
  out=living.preview_scene(scene,{'enabled':True,'hour':0,'scenario':'snow','generatedAt':1800000000000},now=1800000000)
  self.assertTrue(out['preview']);self.assertEqual(scene,original)
  self.assertEqual(out['weather'],scene['weather'])

class PackTests(unittest.TestCase):
 def make_pack(self,root,*,name='test-pack',rgba=True):
  root=Path(root);root.mkdir()
  image=Image.new('RGBA' if rgba else 'RGB',(200,100),(30,80,60,255) if rgba else (30,80,60))
  if rgba:
   for y in range(60):
    for x in range(200):image.putpixel((x,y),(0,0,0,0))
  image.save(root/'foreground.png')
  (root/'manifest.json').write_text(json.dumps({'schemaVersion':1,'id':name,'name':'Test pack','horizon':.6,'foreground':'foreground.png'}))
  return root
 def test_import_export_restart_and_private_permissions(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source')
   installed=living.import_pack(source,base/'store')
   self.assertEqual(installed['id'],'test-pack')
   self.assertEqual(living.load_pack(base/'store/test-pack')['horizon'],.6)
   self.assertEqual(stat.S_IMODE((base/'store/test-pack/manifest.json').stat().st_mode),0o600)
   archive=living.export_pack(installed,base/'landscape.dynwall')
   restored=living.import_pack(archive,base/'second')
   self.assertEqual(restored['id'],'test-pack')
 def test_traversal_symlink_corrupt_and_missing_assets_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');manifest=json.loads((source/'manifest.json').read_text())
   for relative in ('../outside.png','/etc/passwd','folder/../../outside.png'):
    (source/'manifest.json').write_text(json.dumps({**manifest,'foreground':relative}))
    with self.assertRaises(ValueError):living.load_pack(source)
   (source/'manifest.json').write_text(json.dumps(manifest));(source/'foreground.png').unlink();(source/'foreground.png').symlink_to('/etc/passwd')
   with self.assertRaises(ValueError):living.load_pack(source)
   (source/'foreground.png').unlink();(source/'foreground.png').write_bytes(b'corrupt')
   with self.assertRaises(ValueError):living.load_pack(source)
 def test_zip_traversal_rejected_before_publication(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);archive=base/'bad.zip'
   with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape','bad')
   with self.assertRaises(ValueError):living.import_pack(archive,base/'store')
   self.assertFalse((base/'escape').exists())
 def test_failed_publication_leaves_no_partial_pack(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source')
   with patch('dynwall_living.os.rename',side_effect=OSError('injected failure')):
    with self.assertRaises(OSError):living.import_pack(source,base/'store')
   self.assertFalse((base/'store/test-pack').exists())
   self.assertEqual(list((base/'store').iterdir()),[])
 def test_existing_pack_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');living.import_pack(source,base/'store')
   before=(base/'store/test-pack/foreground.png').read_bytes()
   with self.assertRaises(FileExistsError):living.import_pack(source,base/'store')
   self.assertEqual((base/'store/test-pack/foreground.png').read_bytes(),before)
 def test_photographic_opaque_foreground_is_cut_at_marked_horizon(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source',rgba=False)
   pack=living.import_pack(source,base/'store')
   with Image.open(pack['foreground']) as foreground:
    self.assertEqual(foreground.mode,'RGBA');self.assertEqual(foreground.getpixel((20,10))[3],0)
   sky=Image.new('RGB',(400,200),(100,150,200));out=living.composite_pack(sky,pack,{})
   self.assertEqual(out.getpixel((20,10)),sky.getpixel((20,10)))
   self.assertNotEqual(out.getpixel((20,190)),sky.getpixel((20,190)))
 def test_horizon_and_scale_change_actual_composition(self):
  with tempfile.TemporaryDirectory() as td:
   pack=living.load_pack(self.make_pack(Path(td)/'source'))
   sky=Image.new('RGB',(400,200),(100,150,200))
   normal=living.composite_pack(sky,pack,{})
   shifted=living.composite_pack(sky,pack,{'horizon':.7,'terrain_scale':1.3})
   self.assertIsNotNone(ImageChops.difference(normal,shifted).getbbox())
 def test_shipped_woodland_is_real_transparent_art(self):
  pack=living.load_pack(living.pack_directory('woodland'))
  with Image.open(pack['foreground']) as image:
   self.assertGreaterEqual(image.width,1280);self.assertEqual(image.mode,'RGBA')
   self.assertEqual(image.getpixel((0,0))[3],0)
   self.assertGreater(image.getextrema()[1][1]-image.getextrema()[1][0],30)

class PackBoundaryTests(unittest.TestCase):
 make_pack = PackTests.make_pack
 def test_manifest_version_matches_json_schema_numeric_integer_semantics(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');path=source/'manifest.json';manifest=json.loads(path.read_text())
   path.write_text(json.dumps({**manifest,'schemaVersion':1.0}));result=living.import_pack(source,base/'store')
   self.assertIs(type(result['schemaVersion']),int)
   self.assertIs(type(json.loads((Path(result['root'])/'manifest.json').read_text())['schemaVersion']),int)
   for version in (True,False,0,2,1.1,'1',None):
    path.write_text(json.dumps({**manifest,'schemaVersion':version}))
    with self.subTest(version=version),self.assertRaises(ValueError):living.load_pack(source)
 def test_manifest_schema_rejects_unknown_capabilities_and_invalid_metadata(self):
  with tempfile.TemporaryDirectory() as td:
   source=self.make_pack(Path(td)/'source');path=source/'manifest.json';manifest=json.loads(path.read_text())
   for changes in ({'layers':[]},{'weather':{}},{'author':17},{'license':None},{'description':'x'*1001},{'$schema':True}):
    path.write_text(json.dumps({**manifest,**changes}))
    with self.subTest(changes=str(changes)[:50]),self.assertRaises(ValueError):living.load_pack(source)
 def test_duplicate_manifest_fields_rejected_before_publication(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');path=source/'manifest.json';text=path.read_text()
   path.write_text(text[:-1]+',"horizon":0.7}')
   with self.assertRaisesRegex(ValueError,'corrupt'):living.import_pack(source,base/'store')
   self.assertFalse((base/'store').exists())
 def test_declared_schema_path_contract_matches_importer(self):
  import re
  schema=json.loads((Path(__file__).parent/'packs/manifest.schema.json').read_text())
  self.assertEqual(set(schema['required']),{'schemaVersion','id','name','horizon','foreground'})
  self.assertFalse(schema['additionalProperties'])
  pattern=re.compile(schema['properties']['foreground']['pattern'])
  for name,valid in [('foreground.png',True),('assets/HILL.PNG',True),('../hill.png',False),('./hill.png',False),('assets//hill.png',False),('/hill.png',False),('assets/./hill.png',False),('assets/../hill.png',False),('a\\hill.png',False),('hill.png\x00',False),('hill.png\n',False)]:
   with self.subTest(name=name):
    self.assertEqual(bool(pattern.fullmatch(name)),valid)
    if valid:self.assertEqual(str(living._relative_asset(name)),name)
    else:
     with self.assertRaises(ValueError):living._relative_asset(name)
 def test_nested_uppercase_png_is_imported_canonically(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');(source/'assets').mkdir();(source/'foreground.png').rename(source/'assets/HILL.PNG');path=source/'manifest.json'
   path.write_text(json.dumps({**json.loads(path.read_text()),'foreground':'assets/HILL.PNG','$schema':'../manifest.schema.json'}))
   result=living.import_pack(source,base/'store');self.assertEqual(Path(result['foreground']).name,'foreground.png');self.assertNotIn('$schema',result)
 def test_animated_png_rejected_instead_of_silently_taking_first_frame(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');first=Image.new('RGBA',(200,100),(30,80,60,255));second=Image.new('RGBA',(200,100),(80,30,60,255))
   first.save(source/'foreground.png',save_all=True,append_images=[second],duration=100,loop=0)
   with self.assertRaisesRegex(ValueError,'static PNG'):living.import_pack(source,base/'store')
   self.assertFalse((base/'store').exists())
 def test_archive_rejects_aliased_paths_and_extra_nested_manifests(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source')
   for bad in ('./unused.png','assets//unused.png','extra/nested/manifest.json'):
    archive=base/'bad.zip'
    with zipfile.ZipFile(archive,'w') as z:
     z.write(source/'manifest.json','manifest.json');z.write(source/'foreground.png','foreground.png');z.writestr(bad,'{}')
    with self.subTest(path=bad),self.assertRaises(ValueError):living.import_pack(archive,base/'store')
    self.assertFalse((base/'store').exists())
 def test_archive_accepts_one_enclosing_folder(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');archive=base/'wrapped.zip'
   with zipfile.ZipFile(archive,'w') as z:
    z.write(source/'manifest.json','landscape/manifest.json');z.write(source/'foreground.png','landscape/foreground.png')
   self.assertEqual(living.import_pack(archive,base/'store')['id'],'test-pack')
 def test_pack_catalog_ignores_unpublished_staging_folders(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);self.make_pack(base/'.pack-inflight',name='unpublished')
   with patch.object(living,'pack_store',return_value=base):self.assertNotIn('unpublished',[p['id']for p in living.list_packs()])
 def test_nonfinite_boolean_and_huge_horizons_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   source=self.make_pack(Path(td)/'source');manifest=json.loads((source/'manifest.json').read_text())
   for value in (True,float('nan'),float('inf'),10**400):
    (source/'manifest.json').write_text(json.dumps({**manifest,'horizon':value}))
    with self.subTest(value=str(value)[:20]),self.assertRaises(ValueError):living.load_pack(source)
 def test_zip_symlink_member_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);archive=base/'symlink.zip'
   item=zipfile.ZipInfo('foreground.png');item.create_system=3;item.external_attr=(stat.S_IFLNK|0o777)<<16
   with zipfile.ZipFile(archive,'w') as z:z.writestr(item,'/etc/passwd')
   with self.assertRaises(ValueError):living.import_pack(archive,base/'store')
 def test_export_failure_preserves_previous_archive(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');out=base/'out.zip';out.write_bytes(b'previous')
   with patch('dynwall_living.os.replace',side_effect=OSError('injected failure')):
    with self.assertRaises(OSError):living.export_pack(source,out)
   self.assertEqual(out.read_bytes(),b'previous')
   self.assertEqual(list(base.glob('.pack-export-*')),[])
 def test_oversized_png_header_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   source=self.make_pack(Path(td)/'source')
   with patch('dynwall_living.MAX_PIXELS',100):
    with self.assertRaises(ValueError):living.load_pack(source)

class MetadataTests(unittest.TestCase):
 make_pack=PackTests.make_pack
 def test_pack_attribution_survives_import_export(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);source=self.make_pack(base/'source');manifest=json.loads((source/'manifest.json').read_text())
   (source/'manifest.json').write_text(json.dumps({**manifest,'author':'Local artist','license':'CC0-1.0','description':'A meadow'}))
   installed=living.import_pack(source,base/'store')
   archive=living.export_pack(installed,base/'pack.zip')
   restored=living.import_pack(archive,base/'next')
   self.assertEqual(restored['author'],'Local artist');self.assertEqual(restored['license'],'CC0-1.0')
 def test_invalid_preset_lookup_is_a_validation_error(self):
  for value in (None,[],{}):
   with self.subTest(value=value),self.assertRaises(ValueError):living.load_preset({},value)
