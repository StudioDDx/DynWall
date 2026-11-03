import {sanitizeScene, weatherUniforms} from '../extension/state.js';
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
const now = 1800000000000;
const make = (name, spec, current) => ({name, uniforms: {
    ...sanitizeScene({schemaVersion: 1, generatedAt: now, spec, renderer: {enabled: true}}, now).uniforms,
    ...weatherUniforms({schemaVersion: 1, fetchedAt: now, provider: 'open-meteo', current}, now),
    u_daylight: spec.stars > 0 ? 0 : 1, u_quality: 1, u_time: 12, u_flow: [0.02, 0.002],
    u_leaves: [0, 0, 0, 0],
}});
const day = {gradient: ['#28466d', '#6597b6', '#d3d8cf'], accent: '#e0b36a', glow: {color: '#ffe5b9', x: .74, y: .34, size: 1.1, intensity: .85}, celestial: {type:'sun', x:.74, y:.34, size:.046}, mesh:{style:'none'}, grain:.01, vignette:.25};
const night = {gradient:['#080f24','#172740','#41596c'], accent:'#7c90b1', stars:450, celestial:{type:'moon', x:.77,y:.26,size:.039}, mesh:{style:'none'}, grain:.008, vignette:.3};
console.log(JSON.stringify([
    make('day',day,{cloudCover:48,windSpeedKmh:15,windDirection:265,rain:0}),
    make('overcast',day,{cloudCover:100,windSpeedKmh:30,windDirection:260,rain:0}),
    make('rain',day,{cloudCover:95,windSpeedKmh:24,windDirection:255,rain:5}),
    make('snow',day,{cloudCover:90,windSpeedKmh:9,windDirection:265,snowfall:1}),
    make('night',night,{cloudCover:48,windSpeedKmh:12,windDirection:265}),
    make('night-clear',night,{cloudCover:0}),
    make('night-overcast',night,{cloudCover:100}),
    ...JSON.parse(execFileSync('/usr/bin/python3', [new URL('./art-fixtures.py', import.meta.url).pathname], {encoding: 'utf8'}))
        .map(({name, spec}) => make(name, spec, {cloudCover: name === 'night-fallback' ? 12 : 18, windSpeedKmh: 14, windDirection: 260})),
    ...['halloween-day', 'halloween'].flatMap(name => {
        const spec = JSON.parse(readFileSync(new URL(`../themes/${name}.json`, import.meta.url), 'utf8'));
        return [
            make(name, spec, {cloudCover: 55, windSpeedKmh: 14, windDirection: 260}),
            make(`${name}-rain`, spec, {cloudCover: 95, windSpeedKmh: 24, windDirection: 255, rain: 5}),
            make(`${name}-snow`, spec, {cloudCover: 90, windSpeedKmh: 9, windDirection: 265, snowfall: 1}),
        ];
    }),
]));
