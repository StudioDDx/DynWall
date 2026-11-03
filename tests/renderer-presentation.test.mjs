import test from 'node:test';
import assert from 'node:assert/strict';
const api = await import('../extension/presentation.js').catch(() => ({}));
const now = new Date(2026, 10, 1, 22, 0).getTime();
const spec = {gradient:['#102030','#8090a0'], landscape:{style:'hills'}, stars:0};
const doc = {schemaVersion:1, generatedAt:now, spec, renderer:{enabled:true}};
test('preview is separate from authoritative observations and returning live restores solar time', () => {
 const weather={schemaVersion:1,fetchedAt:now,latitude:42,longitude:-83,current:{rain:2,isNight:true}};
 const before=JSON.stringify(weather);
 const preview=api.resolvePresentation(doc,{enabled:true,hour:12,scenario:'snow',generatedAt:now},weather,now);
 assert.equal(preview.preview,true);
 assert.equal(preview.snapshot.current.snowfall,1);
 assert.equal(new Date(preview.clock).getHours(),12);
 assert.equal(preview.snapshot.latitude,undefined);
 assert.equal(JSON.stringify(weather),before);
 const live=api.resolvePresentation(doc,null,weather,now);
 assert.equal(live.preview,false);assert.equal(live.clock,now);assert.equal(live.snapshot,weather);
});
test('malformed expired and disabled previews leave live state intact', () => {
 for(const value of [null,{}, {enabled:false}, {enabled:true,hour:NaN}, {enabled:true,hour:12,scenario:'rain',generatedAt:now-7200001}])
  assert.equal(api.resolvePresentation(doc,value,null,now).preview,false);
});
test('preview scenario has day and night consistent celestial uniforms', () => {
 for(const [scenario,hour,day] of [['night',0,false],['day',12,true],['sunrise',6,true]]) {
 const result=api.resolvePresentation(doc,{enabled:true,hour,scenario,generatedAt:now},null,now);
 assert.equal(result.snapshot.current.isNight,!day);
 assert.equal(result.document.spec.stars>0,!day);
 }
});
test('material identifiers switch without interpolation while colors transition', () => {
 const previous={u_landscape:[1,.2,.5],u_color0:[0,0,0]};
 const next={u_landscape:[4,.3,.8],u_color0:[1,1,1]};
 const mixed=api.transitionPresentation(previous,next,.1);
 assert.equal(mixed.u_landscape[0],4);assert.ok(mixed.u_color0[0]>0 && mixed.u_color0[0]<1);
});
test('scheduled scene chooses an offline material while disabled scheduling preserves authored art',()=>{
 const input={...doc,living:{background:'auto'},sceneLibrary:{ocean:{night:{gradient:['#001122','#334455'],landscape:{style:'ocean'}}}}};
 assert.equal(typeof api.selectDocument,'function');
 assert.equal(api.selectDocument(input,null,now),input);
 const result=api.selectDocument(input,{background:'ocean'},now);
 assert.equal(result.spec.landscape.style,'ocean');
 assert.equal(input.spec.landscape.style,'hills');
});
test('preview moves the sun from dawn horizon to noon altitude',()=>{
 const dawn=api.resolvePresentation(doc,{enabled:true,hour:6,scenario:'sunrise',generatedAt:now},null,now);
 const noon=api.resolvePresentation(doc,{enabled:true,hour:12,scenario:'day',generatedAt:now},null,now);
 assert.ok(dawn.document.spec.celestial.y>noon.document.spec.celestial.y);
 assert.equal(dawn.document.spec.celestial.type,'sun');
});
test('unsaved preview selection reaches rendered material without changing live selection',()=>{
 const input={...doc,living:{background:'ridges'},sceneLibrary:{ocean:{day:{gradient:['#102030','#8090a0'],landscape:{style:'ocean'}}}}};
 const result=api.resolvePresentation(input,{enabled:true,hour:12,scenario:'day',generatedAt:now,selection:{background:'ocean',scene_customization:{warmth:.6}}},null,now);
 assert.equal(result.document.spec.landscape.style,'ocean');
 assert.equal(result.document.living.scene_customization.warmth,.6);
 assert.equal(input.living.background,'ridges');
 assert.equal(api.resolvePresentation(input,null,null,now).document,input);
});
test('scheduled automatic selection retains the published AI or seasonal art',()=>{
 const input={...doc,sceneLibrary:{auto:{night:{gradient:['#000000','#111111'],landscape:{style:'hills'}}}}};
 assert.equal(api.selectDocument(input,{background:'auto'},now).spec,input.spec);
});
test('a schedule cannot turn terrain back on after landscape is disabled',()=>{
 const input={...doc,living:{landscape_enabled:false},sceneLibrary:{ocean:{night:{gradient:['#112233','#445566'],landscape:{style:'ocean'}}}}};
 assert.equal(api.selectDocument(input,{background:'ocean'},now).spec.landscape.style,'none');
});
test('preview surface history is illustrative and confined to the preview result',()=>{
 const preview=api.resolvePresentation(doc,{enabled:true,hour:12,scenario:'snow',generatedAt:now},null,now);
 assert.equal(preview.environment.snow,.65);assert.equal(preview.environment.wetness,0);
 assert.equal(api.resolvePresentation(doc,null,null,now).environment,undefined);
});
