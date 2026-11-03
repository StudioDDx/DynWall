// GI-independent count of the exact UniformUploadCache decision path.
// This measures avoided set_uniform_float calls, not GNOME or GPU frame time.
import assert from 'node:assert/strict';
import {UniformUploadCache} from '../extension/uniforms.js';

const staticUniforms = {
    u_canvas: [3840, 1080], u_view: [0, 0, 1920, 1080], u_quality: 1,
    u_color0: [.1, .2, .3], u_color1: [.2, .3, .4], u_color2: [.3, .4, .5],
    u_color3: [.4, .5, .6], u_color4: [.5, .6, .7], u_positions: [0, .5, 1, 1],
    u_position4: 1, u_stopCount: 3, u_accent: [.5, .5, .5], u_glowColor: [1, 1, 1],
    u_glow: [.68, .3, .8, .8], u_glowPulse: .15, u_celestial: [.3, .25, .07, 1],
    u_celestialDrift: .02, u_stars: 0, u_grain: .025, u_vignette: .7,
    u_mesh: [1, 18, .08], u_coverage: .65, u_rain: .2, u_snow: 0,
    u_wind: [1, 2], u_daylight: 1,
};

const frames = 300;
const monitors = 2;
let uploads = 0;
for (let monitor = 0; monitor < monitors; monitor++) {
    const cache = new UniformUploadCache();
    for (let frame = 0; frame < frames; frame++) {
        for (const [name, value] of Object.entries(staticUniforms))
            uploads += cache.prepare(name, value) ? 1 : 0;
        uploads += cache.prepare('u_time', frame / 30) ? 1 : 0;
        uploads += cache.prepare('u_flow', [frame / 3000, frame / 6000]) ? 1 : 0;
    }
}
const baseline = monitors * frames * (Object.keys(staticUniforms).length + 2);
const expectedCached = monitors * (Object.keys(staticUniforms).length + frames * 2);
assert.equal(baseline, 16800);
assert.equal(uploads, expectedCached);
console.log(JSON.stringify({frames, monitors, baseline_set_uniform_float_calls: baseline,
    cached_set_uniform_float_calls: uploads, avoided_calls: baseline - uploads,
    avoided_percent: Number(((baseline - uploads) / baseline * 100).toFixed(2)),
    note: 'GI-independent upload-call count; not a GNOME or GPU timing claim.'}, null, 2));
