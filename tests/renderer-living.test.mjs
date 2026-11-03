import test from 'node:test';
import assert from 'node:assert/strict';
import * as api from '../extension/living.js';
const now=Date.UTC(2026,0,15,12);
const snapshot=(current={},extra={})=>({schemaVersion:1,fetchedAt:now,provider:'open-meteo',location:'A',unit:'c',latitude:42,longitude:-83,current:{rain:0,snowfall:0,temp:0,...current},...extra});
test('living configuration bounds finite controls',()=>{
 const c=api.sanitizeLiving({scene_customization:{horizon:Infinity,mist:-1,warmth:NaN,terrain_scale:99},atmospheric_intensity:true});
 assert.equal(c.scene_customization.horizon,.8);assert.equal(c.scene_customization.mist,0);assert.equal(c.scene_customization.warmth,0);assert.equal(c.scene_customization.terrain_scale,2);assert.equal(c.atmospheric_intensity,.5);assert.equal(c.schedule.enabled,false);
});
test('snow accumulates gradually with bounded resume and no negative-time integration',()=>{
 const w=snapshot({snowfall:2,temp:-4}),first=api.advanceEnvironment(null,w,now),next=api.advanceEnvironment(first,w,now+60000);
 assert.ok(next.snow>0&&next.snow<.03);assert.equal(api.advanceEnvironment(first,{...w,fetchedAt:now+3600000},now+3600000).snow,next.snow);assert.equal(api.advanceEnvironment(next,w,now).snow,next.snow);
});
test('wet terrain dries and Celsius/Fahrenheit melting agree',()=>{
 const first=api.advanceEnvironment(null,snapshot({rain:8}),now),wet=api.advanceEnvironment(first,snapshot({rain:8}),now+60000);
 assert.ok(wet.wetness>0);assert.ok(api.advanceEnvironment(wet,snapshot({temp:10}),now+120000).wetness<wet.wetness);
 const snowy={...first,snow:.8};const c=api.advanceEnvironment(snowy,snapshot({temp:10}),now+60000),f=api.advanceEnvironment(snowy,snapshot({temp:50},{unit:'f'}),now+60000);
 assert.equal(c.snow,f.snow);assert.ok(c.snow<.8);
});
test('invalid weather and new locations cannot replay persisted precipitation',()=>{
 const first=api.advanceEnvironment(null,snapshot({snowfall:2}),now),loaded={...first,snow:.8,wetness:.7};
 assert.equal(api.advanceEnvironment(loaded,snapshot({},{location:'B'}),now+60000).snow,0);assert.equal(api.advanceEnvironment(loaded,snapshot({},{fetchedAt:now-7200001}),now).snow,0);assert.equal(api.advanceEnvironment(loaded,null,now).wetness,0);
 const bad=api.advanceEnvironment({...first,snow:Infinity,wetness:NaN},snapshot(),now+60000);assert.ok(Number.isFinite(bad.snow)&&Number.isFinite(bad.wetness));
});
test('condition-code accumulation remains artistic and measured zero wins',()=>{
 const w=snapshot({snowfall:null,weatherCode:338},{provider:'wttr'}),first=api.advanceEnvironment(null,w,now);
 assert.ok(api.advanceEnvironment(first,w,now+60000).snow>0);assert.equal(api.advanceEnvironment(first,{...w,current:{...w.current,snowfall:0}},now+60000).snow,0);
 const unknown={...w,provider:'unknown'},neutral=api.advanceEnvironment(null,unknown,now);assert.equal(api.advanceEnvironment(neutral,unknown,now+60000).snow,0);
});
test('seasons vary continuously and invert across hemispheres',()=>{
 assert.ok(api.seasonState(now,42).winter>.95);assert.ok(api.seasonState(now,-42).summer>.95);assert.ok(api.seasonState(Date.UTC(2026,6,15,12),-42).winter>.95);
 assert.ok(Math.abs(api.seasonState(Date.UTC(2026,2,31,23,59),42).foliage-api.seasonState(Date.UTC(2026,3,1,0,1),42).foliage)<.001);
});
test('rare moments are deterministic sparse and obey context and off controls',()=>{
 const context={intensity:1,daylight:1,coverage:0,rain:0,season:{spring:1}};let active=0;
 for(let second=0;second<1800;second++) {
  const a=api.rareMoments(now+second*1000,context);assert.deepEqual(a,api.rareMoments(now+second*1000,context));if(a.pollen||a.birds)active++;
  assert.equal(a.shootingStar+a.lightning+a.fireflies,0);
 }
 assert.ok(active>0&&active<100);
 for(const flags of [{enabled:false},{reducedMotion:true},{intensity:0}])for(let second=0;second<180;second++) {
  const m=api.rareMoments(now+second*1000,{...context,...flags});assert.equal(m.pollen+m.birds+m.lightning+m.fireflies+m.shootingStar,0);
 }
});
test('all five atmospheric moments occur in suitable contexts',()=>{
 for(const [name,context]of [['shootingStar',{daylight:0,coverage:0,rain:0}],['lightning',{daylight:.5,coverage:1,rain:1}],['fireflies',{daylight:0,coverage:.6,rain:0,season:{summer:1}}],['pollen',{daylight:1,rain:0,season:{spring:1}}],['birds',{daylight:1,rain:0}]]) {
  let found=false;for(let second=0;second<3600;second++)if(api.rareMoments(now+second*1000,{intensity:1,...context})[name]>0){found=true;break;}assert.ok(found,name);
 }
});
test('performance distinguishes partially covered monitors and battery workload',()=>{
 const p=api.performancePolicy({fps:60,quality:'high',fullscreenMonitors:[true,false]});assert.equal(p.paused,false);assert.deepEqual(p.visibleMonitors,[false,true]);assert.equal(api.performancePolicy({fullscreenMonitors:[true,true]}).paused,true);
 const b=api.performancePolicy({fps:60,quality:'high',onBattery:true});assert.equal(b.fps,15);assert.equal(b.quality,'low');assert.equal(api.performancePolicy({fps:60,onBattery:true,batterySaver:false}).fps,60);
 for(const flag of ['locked','suspended','displayAsleep','reducedMotion'])assert.equal(api.performancePolicy({[flag]:true}).paused,true);
});
test('schedules wrap midnight and bound optional favorite rotation',()=>{
 const local=(h,m=0)=>new Date(2026,10,1,h,m).getTime(),cfg={schedule:{enabled:true,entries:[{minute:480,background:'ridges'},{minute:1200,background:'ocean'}]}};
 assert.equal(api.resolveSchedule(cfg,local(2)).background,'ocean');assert.equal(api.resolveSchedule(cfg,local(8)).background,'ridges');assert.equal(api.resolveSchedule({...cfg,schedule:{...cfg.schedule,enabled:false}},local(8)),null);
 const rotating={favorites:[{background:'alpine'},{background:'dunes'}],schedule:{enabled:true,rotation_minutes:30}};
 assert.equal(api.resolveSchedule(rotating,local(0)).background,'alpine');assert.equal(api.resolveSchedule(rotating,local(0,30)).background,'dunes');
});
test('null and disabled states give neutral shader uniforms',()=>{
 for(const value of Object.values(api.livingUniforms({},null,null,null)))assert.ok(value.every(v=>v===0));
 const off=api.livingUniforms({persistent_weather:false,seasonal_effects:false},{snow:1,wetness:1},{winter:1},{birds:.5});assert.deepEqual(off.u_surface,[0,0]);assert.deepEqual(off.u_season,[0,0,0,0]);assert.equal(off.u_birds[0],.5);
});

test('cloudy autumn nights still offer occasional atmospheric moments',()=>{
 let active=0;
 for(let second=0;second<1800;second++) {
 const m=api.rareMoments(now+second*1000,{intensity:.5,daylight:0,coverage:.6,rain:0,season:{autumn:1}});
 if(m.shootingStar)active++;
 }
 assert.ok(active>0);
});
