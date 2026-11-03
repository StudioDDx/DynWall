// No GNOME imports: these boundaries are also used by the standalone GPU harness.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const bound = (v, fallback, lo, hi) => finite(v) ? Math.max(lo, Math.min(hi, v)) : fallback;
const color = value => typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value)
    ? [1, 3, 5].map(i => parseInt(value.slice(i, i + 2), 16) / 255) : null;
const object = value => value && typeof value === 'object' && !Array.isArray(value);

export function sanitizeScene(document, now = Date.now()) {
    if (!object(document) || document.schemaVersion !== 1 || !finite(document.generatedAt) ||
        document.generatedAt > now + 300000 || !object(document.spec))
        return null;
    const spec = document.spec;
    if (!Array.isArray(spec.gradient) || spec.gradient.length < 2 || spec.gradient.length > 5)
        return null;
    const colors = spec.gradient.map(color);
    if (colors.some(c => !c))
        return null;
    const count = colors.length;
    let positions = spec.gradient_positions;
    if (!Array.isArray(positions) || positions.length !== count || positions.some((v, i) =>
        !finite(v) || v < 0 || v > 1 || (i > 0 && v <= positions[i - 1])))
        positions = colors.map((_, i) => i / (count - 1));
    while (colors.length < 5) colors.push(colors.at(-1));
    while (positions.length < 5) positions = [...positions, 1];
    const glow = object(spec.glow) ? spec.glow : {};
    const celestial = object(spec.celestial) ? spec.celestial : {};
    const mesh = object(spec.mesh) ? spec.mesh : {};
    const landscape = object(spec.landscape) ? spec.landscape : {};
    const landscapeStyle = ['none', 'hills', 'alpine', 'dunes', 'ocean'].indexOf(landscape.style);
    const renderer = object(document.renderer) ? document.renderer : {};
    return {
        enabled: renderer.enabled === true,
        seasonalEffects: renderer.seasonalEffects !== false,
        fps: Math.round(bound(renderer.fps, 30, 15, 60)),
        quality: ['low', 'balanced', 'high'].includes(renderer.quality) ? renderer.quality : 'balanced',
        uniforms: {
            u_color0: colors[0], u_color1: colors[1], u_color2: colors[2], u_color3: colors[3], u_color4: colors[4],
            u_positions: positions.slice(0, 4), u_position4: positions[4], u_stopCount: count,
            u_accent: color(spec.accent) ?? [0.53, 0.53, 0.53],
            u_glowColor: color(glow.color) ?? [1, 1, 1],
            u_glow: [bound(glow.x, 0.68, 0.05, 0.95), bound(glow.y, 0.3, 0, 1), bound(glow.size, 0.8, 0.2, 1.2), object(spec.glow) ? bound(glow.intensity, 0.8, 0, 1) : 0],
            u_glowPulse: bound(glow.pulse, 0.15, 0, 0.3),
            u_celestial: [bound(celestial.x, 0.3, 0.05, 0.95), bound(celestial.y, 0.25, 0, 1), bound(celestial.size, 0.07, 0.03, 0.15), celestial.type === 'sun' ? 1 : celestial.type === 'moon' ? 2 : 0],
            u_celestialDrift: bound(celestial.drift, 0.02, 0, 0.05),
            u_stars: bound(spec.stars, 0, 0, 600),
            u_grain: bound(spec.grain, 0.025, 0, 0.06), u_vignette: bound(spec.vignette, 0.7, 0, 1),
            u_mesh: [mesh.style === 'none' ? 0 : mesh.style === 'lines' ? 2 : 1, bound(mesh.density, 18, 10, 28), bound(mesh.opacity, 0.08, 0.02, 0.16)],
            u_landscape: [landscapeStyle < 0 ? 1 : landscapeStyle, bound(landscape.height, .2, .1, .3), bound(landscape.mist, .5, 0, 1)],
        },
    };
}

export function weatherUniforms(snapshot, now = Date.now()) {
    const result = {u_coverage: 0, u_rain: 0, u_snow: 0, u_wind: [0, 0]};
    if (!object(snapshot) || snapshot.schemaVersion !== 1 || !finite(snapshot.fetchedAt) ||
        now - snapshot.fetchedAt > 7200000 || snapshot.fetchedAt > now + 300000 || !object(snapshot.current))
        return result;
    const current = snapshot.current;
    result.u_coverage = bound(current.cloudCover, 0, 0, 100) / 100;
    result.u_rain = 1 - Math.exp(-bound(current.rain, 0, 0, 200) / 4);
    result.u_snow = 1 - Math.exp(-bound(current.snowfall, 0, 0, 200) / 2);
    // These are visual presets from reported condition codes, NOT measured mm/hour.
    // A measured zero wins; never infer rain from total precipitation or snow depth.
    const code = Number(current.weatherCode);
    const wttr = snapshot.provider === 'wttr';
    const knownCodes = wttr || ['openmeteo', 'open-meteo'].includes(snapshot.provider);
    const rainCodes = wttr ? [176, 185, 200, 263, 266, 281, 284, 293, 296, 299, 302, 305, 308, 311, 314, 353, 356, 359, 386, 389] : [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99];
    const snowCodes = wttr ? [179, 182, 227, 230, 317, 320, 323, 326, 329, 332, 335, 338, 350, 362, 365, 368, 371, 374, 377, 392, 395] : [71, 73, 75, 77, 85, 86];
    if (knownCodes && !finite(current.rain) && rainCodes.includes(code)) result.u_rain = 0.38;
    if (knownCodes && !finite(current.snowfall) && snowCodes.includes(code)) result.u_snow = 0.42;
    // Meteorological direction is FROM north, clockwise. Screen x east, y south.
    if (finite(current.windDirection) && finite(current.windSpeedKmh)) {
        const angle = bound(current.windDirection, 0, 0, 360) * Math.PI / 180;
        const speed = bound(current.windSpeedKmh, 0, 0, 200) / 3.6;
        result.u_wind = [-Math.sin(angle) * speed, Math.cos(angle) * speed];
    }
    return result;
}

export function approachUniforms(previous, target, seconds) {
    // Uniform documents are treated as immutable. Keep the steady-frame path
    // allocation-free, and share unchanged vectors while real transitions run.
    if (previous === target) return previous;
    const fraction = 1 - Math.exp(-bound(seconds, 0, 0, 1) / 8);
    const interpolate = (a, b) => {
        if (Array.isArray(b)) {
            if (Array.isArray(a) && a.length === b.length && a.every((value, i) => value === b[i]))
                return a;
            return b.map((value, i) => interpolate(a?.[i] ?? value, value));
        }
        return (finite(a) ? a : b) + (b - (finite(a) ? a : b)) * fraction;
    };
    let result = null;
    let settled = true;
    for (const [key, value] of Object.entries(target)) {
        const next = interpolate(previous[key], value);
        if (Array.isArray(value) ? !value.every((item, i) => item === next[i]) : next !== value)
            settled = false;
        if (next !== previous[key]) {
            result ??= {...previous};
            result[key] = next;
        }
    }
    for (const key in previous) {
        if (!Object.hasOwn(target, key)) {
            result ??= {...previous};
            delete result[key];
        }
    }
    return result ?? (settled ? target : previous);
}

export function monitorLayout(monitors) {
    if (!monitors.length) return null;
    const x = Math.min(...monitors.map(m => m.x));
    const y = Math.min(...monitors.map(m => m.y));
    return {x, y, width: Math.max(...monitors.map(m => m.x + m.width)) - x,
        height: Math.max(...monitors.map(m => m.y + m.height)) - y};
}

export function withCelestial(uniforms, snapshot, now = Date.now()) {
    const explicit = uniforms.u_celestial[3] > 0;
    const light = uniforms.u_color0.reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0);
    let day = uniforms.u_stars < 1 && light > .12;
    if (typeof snapshot?.current?.isNight === 'boolean') day = !snapshot.current.isNight;
    let daylight = day ? 1 : 0;
    let x = .74, y = .28;
    if (finite(snapshot?.latitude) && finite(snapshot?.longitude) && Math.abs(snapshot.latitude) <= 90 && Math.abs(snapshot.longitude) <= 180) {
        // Approximate solar ephemeris (J2000 orbital elements); no timezone/DST dependency.
        const rad = Math.PI / 180;
        const d = now / 86400000 - 10957.5;
        const mean = rad * (357.5291 + .98560028 * d);
        const longitude = mean + rad * (1.9148 * Math.sin(mean) + .0200 * Math.sin(2 * mean) + .0003 * Math.sin(3 * mean) + 102.9372 + 180);
        const obliquity = 23.4397 * rad;
        const declination = Math.asin(Math.sin(longitude) * Math.sin(obliquity));
        const rightAscension = Math.atan2(Math.sin(longitude) * Math.cos(obliquity), Math.cos(longitude));
        const hourAngle = rad * (280.16 + 360.9856235 * d + snapshot.longitude) - rightAscension;
        const lat = snapshot.latitude * rad;
        const elevation = Math.asin(Math.sin(lat) * Math.sin(declination) + Math.cos(lat) * Math.cos(declination) * Math.cos(hourAngle));
        day = elevation > -6 * rad;
        daylight = bound((elevation / rad + 6) / 18, 0, 0, 1);
        if (day) {
            x = .5 + Math.sin(hourAngle) * .36;
            // Keep a focal disc away from the common central dual-monitor seam.
            if (Math.abs(x - .5) < .065) x += .085;
            y = bound(.83 - Math.sin(Math.max(0, elevation)) * .65, .28, .12, .88);
        }
    }
    // Moon placement is art direction, not an ephemeris or a measured observation.
    return {...uniforms, u_daylight: daylight, u_stars: day ? 0 : Math.max(200, uniforms.u_stars),
        u_celestial: explicit ? [...uniforms.u_celestial.slice(0, 3), day ? 1 : 2] : [day ? x : .76, day ? y : .26, day ? .038 : .032, day ? 1 : 2]};
}
