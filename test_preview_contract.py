import importlib.machinery,json,tempfile,time,unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
import dynwall_living as living
ROOT=Path(__file__).resolve().parent
class PreviewContractTests(unittest.TestCase):
 def test_metadata_rejects_invalid_hours_and_huge_timestamps(self):
  now=1800000000
  for hour in (None,True,'12',-1,25,float('inf'),float('nan'),10**400):
   with self.subTest(hour=str(hour)[:20]):self.assertFalse(living.preview_scene({},dict(enabled=True,hour=hour,scenario='rain',generatedAt=now*1000),now)['preview'])
  self.assertFalse(living.preview_scene({},dict(enabled=True,hour=12,scenario='rain',generatedAt=10**400),now)['preview'])
 def test_hour_twenty_four_means_next_local_midnight(self):
  now=datetime(2026,11,1,12).timestamp();value=living.preview_scene({},dict(enabled=True,hour=24,scenario='night',generatedAt=int(now*1000)),now)
  expected=datetime.fromtimestamp(now).replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
  self.assertEqual(value['previewClock'],int(expected.timestamp()*1000))
 def test_cli_malformed_preview_renders_same_as_live(self):
  m=importlib.machinery.SourceFileLoader('preview_contract_cli',str(ROOT/'dynwall')).load_module()
  fixed=datetime(2026,11,1,12)
  class Clock(datetime):
   @classmethod
   def now(cls,tz=None):return fixed
  original_fallback=m.fallback_spec
  def deterministic(*args,**kwargs):
   spec=original_fallback(*args,**kwargs);spec['grain']=0;return spec
  cfg=living.normalize_living_config(dict(m.DEFAULTS,provider='none',allow_network=False,width=96,height=54))
  with tempfile.TemporaryDirectory()as td:
   base=Path(td);output=base/'preview.png'
   with patch.object(m,'load_config',return_value=cfg),patch.object(m,'CACHE_DIR',base),patch.object(m,'load_weather',return_value=None),patch.object(m,'datetime',Clock),patch.object(m,'fallback_spec',side_effect=deterministic),patch.object(m.time,'time',return_value=fixed.timestamp()):
    self.assertEqual(m.main(['--preview-output',str(output)]),0);expected=output.read_bytes()
    for request in (dict(enabled=True,hour=None,scenario='rain',generatedAt=int(fixed.timestamp()*1000)),dict(enabled=True,hour=12,scenario='rain',generatedAt=10**400)):
     (base/'preview.json').write_text(json.dumps(request));self.assertEqual(m.main(['--preview-output',str(output)]),0);self.assertEqual(output.read_bytes(),expected)
