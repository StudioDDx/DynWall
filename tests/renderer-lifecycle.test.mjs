import test from 'node:test';
import assert from 'node:assert/strict';
const module = await import('../extension/lifecycle.js').catch(() => ({}));
test('cleanup is reverse ordered, idempotent, and continues past one native error', () => {
    assert.equal(typeof module.Lifetime, 'function');
    const life = new module.Lifetime();
    const released = [];
    life.add(() => released.push('actor'));
    life.add(() => { released.push('monitor'); throw new Error('destroy failed'); });
    life.add(() => released.push('timer'));
    life.close(); life.close();
    assert.deepEqual(released, ['timer', 'monitor', 'actor']);
    assert.equal(life.closed, true);
});
test('late asynchronous acquisitions after disable are released immediately', () => {
    const life = new module.Lifetime();
    life.close();
    let active = true;
    life.add(() => { active = false; });
    assert.equal(active, false);
});
test('lock, suspend, overview, reduced motion and missing scene stop scheduling', () => {
    const ready = {enabled: true, hasScene: true, hasMonitors: true, animations: true};
    assert.equal(module.shouldAnimate(ready), true);
    for (const flag of ['locked', 'suspended', 'overview', 'displayAsleep'])
        assert.equal(module.shouldAnimate({...ready, [flag]: true}), false);
    for (const flag of ['enabled', 'hasScene', 'hasMonitors', 'animations'])
        assert.equal(module.shouldAnimate({...ready, [flag]: false}), false);
});
test('only confirmed display standby, suspend or off modes pause rendering', () => {
    assert.equal(typeof module.isDisplayAsleep, 'function');
    for (const mode of [1, 2, 3]) assert.equal(module.isDisplayAsleep(mode), true);
    for (const mode of [0, -1, undefined, null, NaN, '3', 4])
        assert.equal(module.isDisplayAsleep(mode), false);
});
test('atomic input replacements match both rename endpoints, including while disabled', () => {
    assert.equal(typeof module.isInputChange, 'function');
    for (const [file, other] of [
        ['scene.tmp', 'scene.json'], ['current.tmp', 'current.json'],
        ['scene.json', 'old-scene.json'], ['current.json', null],
        ['dynwall', null], ['topweather', null],
    ])
        assert.equal(module.isInputChange(file, other), true, `${file} -> ${other}`);
    for (const [file, other] of [['scene.tmp', 'unrelated.json'], ['unrelated.json', null], [null, null]])
        assert.equal(module.isInputChange(file, other), false, `${file} -> ${other}`);
});
