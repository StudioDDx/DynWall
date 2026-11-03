import assert from 'node:assert/strict';
import test from 'node:test';
import {UniformUploadCache} from '../extension/uniforms.js';

test('uniform cache uploads an initial value once and remembers float32 values by copy', () => {
    const cache = new UniformUploadCache();
    const source = [0.1, 0.2];

    const first = cache.prepare('u_flow', source);
    assert.deepEqual(first, [Math.fround(0.1), Math.fround(0.2)]);
    assert.equal(cache.prepare('u_flow', source), null);

    // The source array belongs to the animation loop and may be replaced or mutated.
    source[0] = 0.3;
    assert.deepEqual(cache.prepare('u_flow', source), [Math.fround(0.3), Math.fround(0.2)]);
});

test('uniform cache skips values that GL receives as the same float32 value', () => {
    const cache = new UniformUploadCache();
    assert.notEqual(cache.prepare('u_time', 1), null);
    assert.equal(cache.prepare('u_time', 1 + 2 ** -25), null);
    assert.notEqual(cache.prepare('u_time', 1 + 2 ** -23), null);
});

test('clearing the cache re-uploads all values after a GLSL pipeline rebuild', () => {
    const cache = new UniformUploadCache();
    assert.notEqual(cache.prepare('u_color0', [0.2, 0.3, 0.4]), null);
    assert.equal(cache.prepare('u_color0', [0.2, 0.3, 0.4]), null);
    cache.clear();
    assert.notEqual(cache.prepare('u_color0', [0.2, 0.3, 0.4]), null);
});
