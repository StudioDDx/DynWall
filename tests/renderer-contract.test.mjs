import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const api=await import('../extension/living.js').catch(()=>({}));
const python=(config,ms)=>JSON.parse(execFileSync('/usr/bin/python3',['-c',
 'import json,sys;from dynwall_living import normalize_living_config,resolve_selection;c=json.loads(sys.argv[1]);print(json.dumps({"config":normalize_living_config(c),"selection":resolve_selection(c,float(sys.argv[2])/1000)}))',JSON.stringify(config),String(ms)],{encoding:'utf8',env:{...process.env,TZ:'America/Detroit'}}));
process.env.TZ='America/Detroit';
test('Python publisher and native shader sanitize the same customization contract',()=>{
 for(const raw of [{},{scene_customization:{horizon:99,terrain_scale:-1,mist:2,warmth:-2,darkness:.8,animation_intensity:2}},
  {scene_customization:{horizon:true,mist:'1',warmth:null,darkness:false,animation_intensity:[]}}]) {
  const expected=python(raw,1800000000000).config;
  assert.deepEqual(api.sanitizeLiving(raw).scene_customization,expected.scene_customization);
 }
});
test('native schedules agree with Python through midnight, DST and rotation slots',()=>{
 const configs=[
  {background:'ridges',schedule:{enabled:true,entries:[{minute:420,background:'alpine'},{minute:1080,background:'ocean'}]}},
  {background:'ridges',favorites:[{background:'alpine'},{background:'dunes'}],schedule:{enabled:true,rotation_minutes:5}},
  {background:'ridges',favorites:[{background:'alpine'}],schedule:{enabled:true,entries:[{minute:0,background:'sky'}],rotation_minutes:5}},
 ];
 for(const cfg of configs)for(const ms of [new Date(2026,10,1,0,1).getTime(),new Date(2026,10,1,1,35).getTime(),new Date(2026,10,1,7,0).getTime(),new Date(2026,10,1,23,59).getTime()])
  assert.deepEqual(api.resolveSchedule(cfg,ms),python(cfg,ms).selection);
});
test('malformed and disabled scheduling leaves native authored art alone',()=>{
 for(const cfg of [{},{schedule:{enabled:false,entries:[{minute:0,background:'ocean'}]}},{schedule:{enabled:'true',entries:[]}}, {schedule:{enabled:true,entries:[{minute:-1,background:'ocean'}]}}])
  assert.equal(api.resolveSchedule(cfg,1800000000000),null);
});
test('a sub-minute malformed rotation cannot activate native favorites',()=>{
 const cfg={background:'ridges',favorites:[{background:'alpine'}],schedule:{enabled:true,rotation_minutes:.5}};
 assert.equal(python(cfg,1800000000000).config.schedule.rotation_minutes,0);
 assert.equal(api.resolveSchedule(cfg,1800000000000),null);
});
