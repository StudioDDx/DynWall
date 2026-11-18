import test from 'node:test';
import assert from 'node:assert/strict';
import {advanceAdvection} from '../extension/state.js';

test('wind advection remains visible in light reported wind', () => {
    let flow = [0, 0];
    for (let frame = 0; frame < 150; frame++)
        flow = advanceAdvection(flow, [1, 0], .1);
    assert.ok(flow[0] >= .02, `fifteen seconds of light wind only moved ${flow[0]}`);
    assert.equal(flow[1], 0);
});

test('advection integrates without jumps on invalid or large frames', () => {
    const flow = advanceAdvection([.05, .02], [2, 1], NaN);
    assert.deepEqual(flow, [.05, .02]);
    const clamped = advanceAdvection([0, 0], [10, -10], 5);
    assert.equal(clamped[0], 10 * .2 * .0015);
    assert.equal(clamped[1], -10 * .2 * .0015);
    assert.ok(advanceAdvection(null, null, .1).every(v => v === 0));
});
