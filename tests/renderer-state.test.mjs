import test from 'node:test';
import assert from 'node:assert/strict';
const state = await import('../extension/state.js').catch(() => ({}));
const now = 1800000000000;
const scene = (overrides = {}) => ({schemaVersion: 1, generatedAt: now, spec: {gradient: ['#204060', '#90b0c0'], stars: 0}, renderer: {enabled: true, fps: 30, quality: 'balanced'}, ...overrides});
const weather = (current = {}, time = now) => ({schemaVersion: 1, fetchedAt: time, provider: 'open-meteo', location: 'Detroit', current});
test('named landscapes map to distinct discrete renderer styles', () => {
    for (const [style, code] of [['hills', 1], ['alpine', 2], ['dunes', 3], ['ocean', 4], ['none', 0], ['unknown', 1], ['toString', 1], ['__proto__', 1]]) {
        const input = scene({spec: {gradient: ['#123456', '#abcdef'], landscape: {style}}});
        assert.equal(state.sanitizeScene(input, now).uniforms.u_landscape[0], code);
    }
});
test('landscape art defaults to low hills and supports a bounded sky-only option', () => {
    assert.deepEqual(state.sanitizeScene(scene(), now).uniforms.u_landscape, [1, .2, .5]);
    const disabled = scene({spec: {gradient: ['#123456', '#abcdef'], landscape: {style: 'none'}}});
    assert.equal(state.sanitizeScene(disabled, now).uniforms.u_landscape[0], 0);
    const extreme = scene({spec: {gradient: ['#123456', '#abcdef'], landscape: {height: 10, mist: -1}}});
    assert.deepEqual(state.sanitizeScene(extreme, now).uniforms.u_landscape, [1, .3, 0]);
});
test('seasonal effects default on and respect an explicit off switch', () => {
    assert.equal(state.sanitizeScene(scene(), now).seasonalEffects, true);
    assert.equal(state.sanitizeScene(scene({renderer: {enabled: true, seasonalEffects: false}}), now).seasonalEffects, false);
    assert.equal(state.sanitizeScene(scene({renderer: {seasonalEffects: 'false'}}), now).seasonalEffects, true);
});
test('invalid scenes expose static fallback, never invented palettes', () => {
    assert.equal(typeof state.sanitizeScene, 'function');
    for (const input of [null, {}, scene({schemaVersion: 2}), scene({spec: {gradient: ['invalid', '#ffffff']}})])
        assert.equal(state.sanitizeScene(input, now), null);
});
test('untrusted renderer bounds and ordered palette stops are sanitized', () => {
    const result = state.sanitizeScene(scene({renderer: {enabled: 'yes', fps: Infinity, quality: 'ultra'}, spec: {gradient: ['#204060', '#90b0c0'], gradient_positions: [1, 0], celestial: {type: 'sun', size: -10}}}), now);
    assert.equal(result.enabled, false);
    assert.equal(result.fps, 30);
    assert.equal(result.quality, 'balanced');
    assert.deepEqual(result.uniforms.u_positions, [0, 1, 1, 1]);
    assert.equal(result.uniforms.u_celestial[2], 0.03);
});
test('missing and expired weather stay unknown; no fake precipitation', () => {
    for (const input of [null, weather({}, now - 7200001), weather({}, now + 300001), weather({cloudCover: NaN, rain: '9'})]) {
        const result = state.weatherUniforms(input, now);
        assert.equal(result.u_coverage, 0);
        assert.equal(result.u_rain, 0);
        assert.equal(result.u_snow, 0);
    }
});
test('canonical observations drive cloud cover and wind without unit confusion', () => {
    const result = state.weatherUniforms(weather({cloudCover: 80, windSpeedKmh: 36, windDirection: 270, rain: 2.5, snowfall: 0}), now);
    assert.equal(result.u_coverage, 0.8);
    assert.ok(result.u_wind[0] > 0);
    assert.ok(Math.abs(result.u_wind[1]) < 1e-8);
    assert.ok(result.u_rain > 0 && result.u_rain < 1);
    assert.equal(result.u_snow, 0);
});
test('snow water-equivalent observations yield snow, not assumed rain', () => {
    const result = state.weatherUniforms(weather({snowfall: 1, precipitation: 1}), now);
    assert.equal(result.u_rain, 0);
    assert.ok(result.u_snow > 0);
});
test('scene transitions interpolate without overshoot and large resume jumps', () => {
    const initial = {u_coverage: 0, u_wind: [0, 0]};
    const target = {u_coverage: 1, u_wind: [2, 4]};
    const result = state.approachUniforms(initial, target, 1);
    assert.ok(result.u_coverage > 0 && result.u_coverage < 0.5);
    assert.equal(result.u_wind[1], result.u_coverage * 4);
    assert.deepEqual(initial, {u_coverage: 0, u_wind: [0, 0]});
    assert.deepEqual(state.approachUniforms(initial, target, 999), result);
});
test('steady frames reuse immutable uniforms instead of allocating a new scene', () => {
    const input = Object.freeze({u_coverage: .7, u_wind: Object.freeze([2, 4])});
    assert.equal(state.approachUniforms(input, input, 1 / 30), input);
    const sameTarget = {u_coverage: .7, u_wind: [2, 4]};
    // Adopt an equivalent refreshed target so the next frame hits the fast path.
    assert.equal(state.approachUniforms(input, sameTarget, 1 / 30), sameTarget);
});
test('transitions reuse unchanged vectors without rounding away small real changes', () => {
    const input = {u_coverage: .7, u_wind: [2, 4]};
    const target = {u_coverage: .7 + 1e-10, u_wind: [2, 4]};
    const result = state.approachUniforms(input, target, .2);
    assert.ok(result.u_coverage > input.u_coverage);
    assert.ok(result.u_coverage < target.u_coverage);
    assert.equal(result.u_wind, input.u_wind);
    assert.deepEqual(input, {u_coverage: .7, u_wind: [2, 4]});
});
test('transition output follows the target keys when a field is removed', () => {
    assert.deepEqual(state.approachUniforms({u_coverage: .7, removed: 1}, {u_coverage: .7}, .2), {u_coverage: .7});
});
test('zero elapsed time never snaps an unfinished transition to its target', () => {
    const input = {u_coverage: 0, u_wind: [0, 0]};
    const target = {u_coverage: 1, u_wind: [2, 4]};
    assert.deepEqual(state.approachUniforms(input, target, 0), input);
    assert.deepEqual(state.approachUniforms({u_coverage: 0}, {u_coverage: 1}, 0), {u_coverage: 0});
});
test('negative multi-monitor origins retain continuous coordinates', () => {
    assert.deepEqual(state.monitorLayout([{x: -1920, y: 0, width: 1920, height: 1080}, {x: 0, y: 0, width: 1920, height: 1080}]), {x: -1920, y: 0, width: 3840, height: 1080});
    assert.equal(state.monitorLayout([]), null);
});
test('condition codes provide explicitly illustrative particles when rates are unknown', () => {
    const wmo = state.weatherUniforms(weather({weatherCode: 73, snowfall: null}), now);
    assert.ok(wmo.u_snow > 0);
    assert.equal(wmo.u_rain, 0);
    const wttr = state.weatherUniforms({...weather({weatherCode: '296', rain: null}), provider: 'wttr'}, now);
    assert.ok(wttr.u_rain > 0);
    assert.equal(state.weatherUniforms({...weather({weatherCode: '296', rain: 0}), provider: 'wttr'}, now).u_rain, 0);
});
test('fallback celestial follows actual solar position when coordinates are known', () => {
    const noon = Date.UTC(2026, 2, 20, 12);
    const midnight = Date.UTC(2026, 2, 20, 0);
    const input = state.sanitizeScene(scene(), now).uniforms;
    assert.equal(state.withCelestial(input, {latitude: 0, longitude: 0}, noon).u_celestial[3], 1);
    assert.equal(state.withCelestial(input, {latitude: 0, longitude: 0}, midnight).u_celestial[3], 2);
    const explicit = {...input, u_celestial: [.2, .3, .05, 2]};
    assert.deepEqual(state.withCelestial(explicit, {latitude: 0, longitude: 0}, noon).u_celestial.slice(0, 3), explicit.u_celestial.slice(0, 3));
});

test('observed night supplies stars and night lighting without erasing art palette', () => {
    const input = state.sanitizeScene(scene(), now).uniforms;
    const result = state.withCelestial(input, {current: {isNight: true}}, now);
    assert.equal(result.u_daylight, 0);
    assert.ok(result.u_stars >= 200);
    assert.deepEqual(result.u_color0, input.u_color0);
});
test('unknown providers do not reinterpret their codes as WMO weather', () => {
    const result = state.weatherUniforms({...weather({weatherCode: 73}), provider: 'unknown-provider'}, now);
    assert.equal(result.u_snow, 0);
    assert.equal(result.u_rain, 0);
});
test('live openmeteo name supports snow and daytime suppresses stale stars', () => {
    const result = state.weatherUniforms({...weather({weatherCode: 73}), provider: 'openmeteo'}, now);
    assert.ok(result.u_snow > 0);
    const input = state.sanitizeScene(scene({spec: {gradient:['#0a0b10','#324554'], stars: 400}}), now).uniforms;
    assert.equal(state.withCelestial(input, {current:{isNight:false}}, now).u_stars, 0);
});
test('wttr freezing drizzle and freezing rain remain liquid precipitation presets', () => {
    for (const weatherCode of [185, 281, 284, 311, 314]) {
        const result = state.weatherUniforms({...weather({weatherCode}), provider: 'wttr'}, now);
        assert.ok(result.u_rain > 0, `${weatherCode}: freezing liquid should render rain`);
        assert.equal(result.u_snow, 0, `${weatherCode}: freezing liquid is not snow`);
    }
});

test('fresh day and night override stale celestial type but retain composition', () => {
    const sun = state.sanitizeScene(scene({spec:{gradient:['#304050','#708090'], celestial:{type:'sun',x:.7,y:.3,size:.05}}}), now).uniforms;
    assert.deepEqual(state.withCelestial(sun, {current:{isNight:true}}, now).u_celestial, [.7, .3, .05, 2]);
    const moon = {...sun, u_celestial:[.7, .3, .05, 2]};
    assert.deepEqual(state.withCelestial(moon, {current:{isNight:false}}, now).u_celestial, [.7, .3, .05, 1]);
    // Current solar geometry wins over an observation fetched before sunset.
    assert.equal(state.withCelestial(sun, {latitude:0,longitude:0,current:{isNight:false}}, Date.UTC(2026,2,20,0)).u_celestial[3], 2);
});
