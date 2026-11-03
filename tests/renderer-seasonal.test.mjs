import test from 'node:test';
import assert from 'node:assert/strict';
const seasonal = await import('../extension/seasonal.js').catch(() => ({}));

test('autumn follows the local calendar and observation hemisphere', () => {
    assert.equal(typeof seasonal.isAutumn, 'function');
    for (let month = 0; month < 12; month++) {
        const now = new Date(2026, month, 15).getTime();
        assert.equal(seasonal.isAutumn(now, 42), [8, 9, 10].includes(month));
        assert.equal(seasonal.isAutumn(now, -34), [2, 3, 4].includes(month));
        assert.equal(seasonal.isAutumn(now, null), [8, 9, 10].includes(month));
    }
    assert.equal(seasonal.isAutumn(NaN, 42), false);
});

const advance = (clock, seconds, options = {enabled: true, windX: 4}) => {
    let frame;
    for (let i = 0; i < Math.round(seconds * 10); i++) frame = clock.update(.1, options);
    return frame;
};

test('a gust builds, blows with the observed wind, fades and leaves a quiet interval', () => {
    assert.equal(typeof seasonal.AutumnGusts, 'function');
    const clock = new seasonal.AutumnGusts(() => 0);
    assert.deepEqual(clock.update(0, {enabled: true}), [0, 0, 0, 0]);
    assert.equal(advance(clock, 11)[1], 0);
    const start = advance(clock, 1.5);
    const peak = advance(clock, 3.5);
    assert.ok(start[1] > 0 && start[1] < peak[1]);
    assert.equal(peak[1], 1);
    assert.equal(peak[2], 1);
    const fading = advance(clock, 5.5);
    assert.ok(fading[1] > 0 && fading[1] < peak[1]);
    assert.equal(advance(clock, 1)[1], 0);
    assert.equal(advance(clock, 80)[1], 0);
    assert.ok(advance(clock, 15)[1] > 0, 'a later gust should follow the quiet interval');
});

test('gust direction is fixed for an event and follows westward weather', () => {
    const clock = new seasonal.AutumnGusts(() => 0);
    const frame = advance(clock, 15, {enabled: true, windX: -5});
    assert.equal(frame[2], -1);
    assert.equal(clock.update(.1, {enabled: true, windX: 5})[2], -1);
});

test('paused clocks do not advance and disabled effects restart quietly', () => {
    const clock = new seasonal.AutumnGusts(() => 0);
    const active = advance(clock, 15);
    assert.deepEqual(clock.update(0, {enabled: true}), active);
    assert.deepEqual(clock.update(.1, {enabled: false}), [0, 0, 0, 0]);
    assert.equal(advance(clock, 5)[1], 0);
});

test('event bounds vary with randomness without large resume or invalid-time jumps', () => {
    const clock = new seasonal.AutumnGusts(() => .999);
    assert.equal(advance(clock, 30)[1], 0);
    const active = advance(clock, 9);
    assert.ok(active[1] > 0);
    assert.equal(active[2], 1);
    for (const seconds of [NaN, Infinity, -1])
        assert.deepEqual(clock.update(seconds, {enabled: true}), active);
    const resumed = clock.update(3600, {enabled: true});
    assert.ok(resumed[0] - active[0] <= .201);
    assert.ok(advance(clock, 9)[1] > 0);
    assert.equal(advance(clock, 8)[1], 0);
    assert.equal(advance(clock, 230)[1], 0);
});

test('wind advection remains visible in light reported wind', () => {
    assert.equal(typeof seasonal.advanceAdvection, 'function');
    let flow = [0, 0];
    for (let frame = 0; frame < 150; frame++)
        flow = seasonal.advanceAdvection(flow, [1, 0], [0, 0, 0, 0], .1);
    assert.ok(flow[0] >= .02, `fifteen seconds of light wind only moved ${flow[0]}`);
    assert.equal(flow[1], 0);
});

test('windborne leaves require a plausible nearby source', () => {
    assert.equal(typeof seasonal.supportsWindborneLeaves, 'function');
    assert.equal(seasonal.supportsWindborneLeaves(1, false), true, 'wooded hills');
    assert.equal(seasonal.supportsWindborneLeaves(2, false), true, 'alpine vegetation');
    assert.equal(seasonal.supportsWindborneLeaves(0, true), true, 'foreground pack');
    for (const style of [0, 3, 4])
        assert.equal(seasonal.supportsWindborneLeaves(style, false), false);
});
