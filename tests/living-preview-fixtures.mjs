import {resolvePresentation} from '../extension/presentation.js';
import {sanitizeScene,withCelestial,weatherUniforms} from '../extension/state.js';
import {sanitizeLiving,livingUniforms,seasonState} from '../extension/living.js';
const now=new Date(2026,10,1,12).getTime();
const document={schemaVersion:1,generatedAt:now,spec:{gradient:['#28466d','#6597b6','#d3d8cf'],accent:'#e0b36a',mesh:{style:'none'},landscape:{style:'hills',height:.2,mist:.5}},renderer:{enabled:true}};
console.log(JSON.stringify([['sunrise',6],['day',12],['night',0],['rain',12],['snow',12],['storm',19]].map(([scenario,hour])=>{
 const p=resolvePresentation(document,{enabled:true,hour,scenario,generatedAt:now},null,now);
 const base=sanitizeScene(p.document,now).uniforms;
 return {name:`preview-${scenario}`,uniforms:{...withCelestial(base,p.snapshot,p.clock),...weatherUniforms(p.snapshot,p.clock),
  ...livingUniforms(sanitizeLiving({}),p.environment,seasonState(now,42),null),
  u_time:12,u_flow:[.02,.002],u_leaves:[0,0,0,0]}};
})));
