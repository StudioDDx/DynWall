// Pure living-environment boundaries shared by GNOME and deterministic tests.
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const bound=(v,fallback,lo,hi)=>finite(v)?Math.max(lo,Math.min(hi,v)):fallback;
const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
const backgrounds=new Set(['auto','ridges','alpine','dunes','ocean','sky']);
const packId=v=>typeof v==='string'&&/^[a-z0-9][a-z0-9_-]{0,63}$/.test(v)?v:'';
function customization(raw) {
 const c=object(raw)?raw:{};
 return {horizon:bound(c.horizon,.8,.5,.95),terrain_scale:bound(c.terrain_scale,1,.5,2),mist:bound(c.mist,.5,0,1),warmth:bound(c.warmth,0,-1,1),darkness:bound(c.darkness,0,0,1),animation_intensity:bound(c.animation_intensity,1,0,2)};
}
function selection(raw) {
 if(!object(raw))return null;
 return {background:backgrounds.has(raw.background)?raw.background:'auto',landscape_pack:packId(raw.landscape_pack),scene_customization:customization(raw.scene_customization)};
}
export function sanitizeLiving(raw) {
 raw=object(raw)?raw:{};
 const schedule=object(raw.schedule)?raw.schedule:{},byMinute=new Map();
 for(const entry of Array.isArray(schedule.entries)?schedule.entries.slice(0,24):[])
  if(object(entry)&&Number.isInteger(entry.minute)&&entry.minute>=0&&entry.minute<1440)byMinute.set(entry.minute,{...selection(entry),minute:entry.minute});
 const entries=[...byMinute.values()].sort((a,b)=>a.minute-b.minute),favorites=[];
 for(const item of Array.isArray(raw.favorites)?raw.favorites.slice(0,24):[]) {
  const chosen=selection(item);
  if(chosen&&!favorites.some(previous=>JSON.stringify(previous)===JSON.stringify(chosen)))favorites.push(chosen);
 }
 return {...selection(raw),persistent_weather:raw.persistent_weather!==false,atmospheric_intensity:bound(raw.atmospheric_intensity,.5,0,1),battery_saver:raw.battery_saver!==false,seasonal_effects:raw.seasonal_effects!==false,landscape_enabled:raw.landscape_enabled!==false,favorites,
  schedule:{enabled:schedule.enabled===true,entries,rotation_minutes:finite(schedule.rotation_minutes)&&Math.floor(schedule.rotation_minutes)>0?Math.max(5,Math.floor(bound(schedule.rotation_minutes,0,0,1440))):0}};
}
export function resolveSchedule(raw,now=Date.now()) {
 if(!finite(now)||!Number.isFinite(new Date(now).getTime()))return null;
 const cfg=sanitizeLiving(raw),schedule=cfg.schedule;
 if(!schedule.enabled)return null;
 const date=new Date(now),minute=date.getHours()*60+date.getMinutes();
 if(schedule.entries.length) {
  let chosen=schedule.entries.at(-1);
  for(const entry of schedule.entries){if(entry.minute>minute)break;chosen=entry;}
  const {minute:unused,...result}=chosen;return result;
 }
 if(schedule.rotation_minutes&&cfg.favorites.length)return cfg.favorites[Math.floor(minute/schedule.rotation_minutes)%cfg.favorites.length];
 return null;
}
export function seasonState(now=Date.now(),latitude=45) {
 if(!finite(now)||!Number.isFinite(new Date(now).getTime()))now=0;
 const date=new Date(now),year=date.getUTCFullYear(),start=Date.UTC(year,0,1),span=Date.UTC(year+1,0,1)-start;
 const phase=((now-start)/span-14/365+(finite(latitude)&&latitude<0?.5:0)+1)%1,result={phase};
 for(const [name,centre]of Object.entries({winter:0,spring:.25,summer:.5,autumn:.75})) {
  const distance=Math.min(Math.abs(phase-centre),1-Math.abs(phase-centre));result[name]=Math.max(0,1-distance*4);
 }
 result.foliage=Math.max(0,Math.min(1,result.spring*.8+result.summer+result.autumn*.5));return result;
}
function weather(snapshot,now) {
 if(!object(snapshot)||snapshot.schemaVersion!==1||!finite(snapshot.fetchedAt)||now-snapshot.fetchedAt>7200000||snapshot.fetchedAt>now+300000||!object(snapshot.current))return null;
 const current=snapshot.current,wttr=snapshot.provider==='wttr',known=wttr||['openmeteo','open-meteo'].includes(snapshot.provider);
 const rainCodes=wttr?[176,185,200,263,266,281,284,293,296,299,302,305,308,311,314,353,356,359,386,389]:[51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99];
 const snowCodes=wttr?[179,182,227,230,317,320,323,326,329,332,335,338,350,362,365,368,371,374,377,392,395]:[71,73,75,77,85,86];
 const rain=finite(current.rain)?1-Math.exp(-bound(current.rain,0,0,200)/4):known&&rainCodes.includes(Number(current.weatherCode))?.38:0;
 const snow=finite(current.snowfall)?1-Math.exp(-bound(current.snowfall,0,0,200)/2):known&&snowCodes.includes(Number(current.weatherCode))?.42:0;
 let temp=finite(current.temp)?current.temp:null;
 if(temp!==null&&snapshot.unit==='f')temp=(temp-32)*5/9;
 if(!['c','f'].includes(snapshot.unit))temp=null;
 return {rain,snow,temp,location:JSON.stringify([snapshot.provider??'',snapshot.location??'',snapshot.latitude??null,snapshot.longitude??null])};
}
export function advanceEnvironment(previous,snapshot,now=Date.now()) {
 now=finite(now)?now:0;
 const observed=weather(snapshot,now);
 if(!observed)return {location:'',updatedAt:now,snow:0,wetness:0};
 const same=object(previous)&&previous.location===observed.location;
 const state={location:observed.location,updatedAt:now,snow:same?bound(previous.snow,0,0,1):0,wetness:same?bound(previous.wetness,0,0,1):0};
 const minutes=same&&finite(previous.updatedAt)?Math.max(0,Math.min(60000,now-previous.updatedAt))/60000:0;
 // Artistic coverage, not measured snow depth/water levels. Never replay hours on resume.
 const thaw=observed.temp===null?.002:observed.temp>0?.003*(1+Math.min(20,observed.temp)/5):.0002;
 state.snow=bound(state.snow+(observed.snow*.024-thaw*(1-observed.snow))*minutes,0,0,1);
 state.wetness=bound(state.wetness+(observed.rain*.055+Math.max(0,thaw)*state.snow-.006*(1-observed.rain))*minutes,0,0,1);
 return state;
}
const hash=n=>{const v=Math.sin(n*127.1+311.7)*43758.5453123;return v-Math.floor(v);};
export function rareMoments(now=Date.now(),context={}) {
 const empty={shootingStar:0,lightning:0,fireflies:0,pollen:0,birds:0,phase:0,seed:0};
 context=object(context)?context:{};
 const intensity=bound(context.intensity,.5,0,1);
 if(!finite(now)||!intensity||context.enabled===false||context.reducedMotion===true)return empty;
 const block=Math.floor(now/120000),seed=hash(block+bound(context.seed,0,-100000,100000));
 if(hash(block+19)>intensity*.62)return empty;
 const second=((now%120000)+120000)%120000/1000,start=15+seed*80,duration=7+hash(block+7)*3,phase=(second-start)/duration;
 if(phase<0||phase>1)return empty;
 const daylight=bound(context.daylight,1,0,1),rain=bound(context.rain,0,0,1),coverage=bound(context.coverage,0,0,1),season=object(context.season)?context.season:{},choices=[];
 if(daylight<.2&&coverage<.8)choices.push('shootingStar');
 if(rain>.25&&coverage>.7)choices.push('lightning');
 if(daylight<.3&&rain<.1&&bound(season.summer,0,0,1)>.35)choices.push('fireflies');
 if(daylight>.4&&rain<.1&&bound(season.spring,0,0,1)>.35)choices.push('pollen');
 if(daylight>.3&&rain<.2)choices.push('birds');
 if(!choices.length)return empty;
 const type=choices[Math.min(choices.length-1,Math.floor(hash(block+53)*choices.length))];
 return {...empty,[type]:Math.sin(Math.PI*phase)*intensity,phase,seed};
}
export function performancePolicy(flags={}) {
 flags=object(flags)?flags:{};
 let fps=Math.round(bound(flags.fps,30,15,60));
 let quality=['low','balanced','high'].includes(flags.quality)?flags.quality:'balanced';
 const visibleMonitors=Array.isArray(flags.fullscreenMonitors)?flags.fullscreenMonitors.map(value=>value!==true):[];
 if(flags.onBattery===true&&flags.batterySaver!==false){fps=Math.min(fps,15);quality='low';}
 const covered=visibleMonitors.length>0&&visibleMonitors.every(value=>!value);
 return {fps,quality,paused:!!(covered||flags.locked||flags.suspended||flags.displayAsleep||flags.reducedMotion),visibleMonitors};
}
export function livingUniforms(config,environment,season,moments) {
 const cfg=sanitizeLiving(config),c=cfg.scene_customization;
 environment=cfg.persistent_weather&&object(environment)?environment:{};
 season=cfg.seasonal_effects&&object(season)?season:{};
 moments=object(moments)?moments:{};
 const unit=value=>bound(value,0,0,1);
 return {u_custom:[c.horizon-.8,c.terrain_scale-1,c.mist-.5,c.animation_intensity-1],u_tint:[c.warmth,c.darkness],u_surface:[unit(environment.snow),unit(environment.wetness)],u_season:[unit(season.winter),unit(season.spring),unit(season.summer),unit(season.autumn)],u_moments:[unit(moments.shootingStar),unit(moments.lightning),unit(moments.fireflies),unit(moments.pollen)],u_birds:[unit(moments.birds),unit(moments.phase),unit(moments.seed)]};
}
