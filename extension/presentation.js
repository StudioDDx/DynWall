// Pure presentation boundary: synthetic weather never enters the observation cache.
import {approachUniforms} from './state.js';
const phases = {
 night: {gradient:['#080f24','#172740','#41596c'], stars:450},
 sunrise: {gradient:['#29314f','#ad7978','#efbd91'], stars:0},
 day: {gradient:['#28466d','#6597b6','#d3d8cf'], stars:0},
 sunset: {gradient:['#262d4c','#9b6475','#d9a678'], stars:0},
};
export function phaseAt(hour) {
 return hour < 5 || hour >= 20 ? 'night' : hour < 8 ? 'sunrise' : hour >= 17 ? 'sunset' : 'day';
}
export function resolvePresentation(document, request, snapshot, now = Date.now()) {
 const result={document,snapshot,clock:now,preview:false};
 if (!document || !request || request.enabled !== true || !Number.isFinite(request.hour) ||
     request.hour < 0 || request.hour > 24 || !Number.isFinite(request.generatedAt) ||
     now-request.generatedAt > 7200000 || request.generatedAt-now > 300000 ||
     !['sunrise','day','night','rain','snow','storm'].includes(request.scenario)) return result;
 const clock=new Date(now); clock.setHours(Math.floor(request.hour), Math.round(request.hour%1*60),0,0);
 document=selectDocument(document,request.selection,clock.getTime());
 const phase=phaseAt(request.hour);
 const progress=Math.max(0,Math.min(1,(request.hour-6)/12));
 const night=phase==='night';
 const spec={...document.spec,...phases[phase],celestial:{...(document.spec.celestial??{}),
   type:night?'moon':'sun',x:night?.76:.15+progress*.7,y:night?.26:.83-Math.sin(progress*Math.PI)*.65,size:night?.032:.038}};
 const rain=request.scenario==='rain' ? 5 : request.scenario==='storm' ? 12 : 0;
 const snow=request.scenario==='snow' ? 1 : 0;
 // No coordinates: the preview's chosen local hour is authoritative. Live ephemeris
 // resumes using real coordinates immediately when the request is removed.
 const synthetic={schemaVersion:1,fetchedAt:clock.getTime(),provider:'open-meteo',location:'Preview',unit:'c',
   current:{isNight:phase==='night',cloudCover:rain||snow?95:20,rain,snowfall:snow,weatherCode:request.scenario==='storm'?95:snow?73:rain?63:0,windSpeedKmh:rain?24:8,windDirection:260}};
 return {document:{...document,spec},snapshot:synthetic,clock:clock.getTime(),preview:true,
   environment:{snow:snow?.65:0,wetness:rain?.8:0}};
}
export function transitionPresentation(previous, target, dt) {
 const result=approachUniforms(previous,target,dt);
 // Interpolating a material selector renders intervening unrelated materials.
 for (const name of ['u_landscape','u_mesh','u_celestial']) {
  if (!target[name] || !result[name]) continue;
  const index=name==='u_celestial'?3:0;
  if (result[name][index]!==target[name][index]) {
   result[name]=[...result[name]];result[name][index]=target[name][index];
  }
 }
 return result;
}
export function sanitizePack(value) {
 if (!value || typeof value.root!=='string' || !value.root.startsWith('/') ||
     value.root.includes('\\') || value.root.includes('\0') || value.root.split('/').slice(1).some(part=>!part||part==='..'||part==='.') ||
     typeof value.foreground!=='string' || !value.foreground.startsWith(`${value.root}/`) ||
     value.foreground.includes('\\') || value.foreground.includes('\0') || value.foreground.split('/').slice(1).some(part=>!part||part==='..'||part==='.') ||
     !value.foreground.toLowerCase().endsWith('.png') || !Number.isFinite(value.horizon) ||
     value.horizon<.1 || value.horizon>.95) return null;
 return {root:value.root,foreground:value.foreground,horizon:value.horizon};
}
export function selectDocument(document, selection, now) {
 if (!document || !selection) return document;
 let spec=selection.background==='auto' ? document.automaticSpec??document.spec :
  document.sceneLibrary?.[selection.background]?.[phaseAt(new Date(now).getHours())]??document.spec;
 if (document.living?.landscape_enabled===false) spec={...spec,landscape:{...spec.landscape,style:'none'}};
 return {...document,spec,living:{...document.living,...selection}};
}
export function shouldResetEnvironment(state, marker) {
 return Number.isFinite(marker) && (!Number.isFinite(state?.updatedAt) || state.updatedAt <= marker);
}
