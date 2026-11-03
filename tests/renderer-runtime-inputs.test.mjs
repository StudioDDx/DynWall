import test from 'node:test';
import assert from 'node:assert/strict';
const api=await import('../extension/presentation.js');
test('untrusted pack descriptors cannot reference arbitrary files or oversized images',()=>{
 assert.equal(typeof api.sanitizePack,'function');
 for(const value of [null,{}, {foreground:'/etc/passwd',horizon:.7}, {root:'/packs/a',foreground:'/packs/ab/x.png',horizon:.7}, {root:'/packs/a',foreground:'/packs/a/../secret.png',horizon:.7}]) assert.equal(api.sanitizePack(value),null);
 const good={root:'/packs/a',foreground:'/packs/a/foreground.png',horizon:.7};
 assert.equal(api.sanitizePack(good).foreground,good.foreground);
});
test('clock phase selection wraps at night and keeps dawn and dusk distinct',()=>{
 assert.equal(api.phaseAt(0),'night');assert.equal(api.phaseAt(6),'sunrise');assert.equal(api.phaseAt(12),'day');assert.equal(api.phaseAt(18),'sunset');assert.equal(api.phaseAt(23),'night');
});
test('an old reset marker cannot erase environmental state on every restart',()=>{
 assert.equal(typeof api.shouldResetEnvironment,'function');
 assert.equal(api.shouldResetEnvironment({updatedAt:2000},1000),false);
 assert.equal(api.shouldResetEnvironment({updatedAt:1000},2000),true);
 assert.equal(api.shouldResetEnvironment(null,2000),true);
 assert.equal(api.shouldResetEnvironment({updatedAt:1000},NaN),false);
});
