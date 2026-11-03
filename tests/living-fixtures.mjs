import {sanitizeScene} from '../extension/state.js';
const now=Date.UTC(2026,0,15,12);
const day={gradient:['#28466d','#6597b6','#d3d8cf'],accent:'#b7c9ba',landscape:{style:'hills',height:.2,mist:.5},mesh:{style:'none'},grain:.008,vignette:.2};
const night={...day,gradient:['#070e20','#172940','#48596b'],stars:400,celestial:{type:'moon',x:.76,y:.24,size:.035}};
const base=(name,spec,more={})=>({name,uniforms:{...sanitizeScene({schemaVersion:1,generatedAt:now,spec,renderer:{enabled:true}},now).uniforms,u_daylight:spec.stars?0:1,u_coverage:.12,u_rain:0,u_snow:0,u_wind:[2,0],u_quality:1,u_time:12,u_flow:[.01,0],u_leaves:[0,0,0,0],u_custom:[0,0,0,0],u_tint:[0,0],u_surface:[0,0],u_season:[0,0,0,0],u_moments:[0,0,0,0],u_birds:[0,.5,.37],...more}});
const change=(name,more,spec=day,reference='living-day')=>({...base(name,spec,more),reference});
const ocean={...day,landscape:{style:'ocean',height:.2,mist:.5}};
console.log(JSON.stringify([
 base('living-day',day),base('living-night',night),
 change('living-wet',{u_surface:[0,.95]}),change('living-accumulated-snow',{u_surface:[.95,0]}),
 ...['winter','spring','summer','autumn'].map((name,index)=>change(`living-${name}`,{u_season:[0,0,0,0].map((_,i)=>i===index?1:0)})),
 change('living-customization',{u_custom:[-.12,.3,.3,0],u_tint:[.7,.25]}),
 change('living-shooting-star',{u_moments:[1,0,0,0]},night,'living-night'),
 change('living-lightning',{u_moments:[0,1,0,0]}),
 change('living-fireflies',{u_moments:[0,0,1,0]},night,'living-night'),
 change('living-pollen',{u_moments:[0,0,0,1]}),change('living-birds',{u_birds:[1,.5,.37]}),
 base('living-ocean',ocean),change('living-ocean-wet',{u_surface:[0,.95]},ocean,'living-ocean'),
]));
