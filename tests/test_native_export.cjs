const {test} = require('node:test');
const assert = require('node:assert/strict');
const {originalFor, plan} = require('../web/native-export.js');
const original = {name:'camera.mov', size:123, fingerprint:'a'.repeat(64)};
test('saved identity survives renamed proxy paths; basename guesses are rejected', () => {
  assert.deepEqual(originalFor({path:'/old/Tuneup.small.mp4', original}, []), original);
  assert.equal(originalFor({path:'/old/Tuneup.small.mp4'}, [{path:'/new/Tuneup.small.mp4', original}]), null);
  assert.equal(originalFor({path:'/old/a'}, [{path:'/old/a',original},{path:'/old/a',original:{...original,fingerprint:'b'.repeat(64)}}]), null);
});
const shot = {source:0, master_start_sec:12, duration_sec:3, clip_start_sec:0};
const fallback = {...shot,source:1,clip_start_sec:7,playback_speed:1};
const recipe = {sources:[{key:0,path:'logo.small.mp4',optional:true},{key:1,path:'camera.mov',optional:false}],segments:[shot],fallbacks:{0:[fallback]}};
test('optional insert omission retains exact master clock and records decision', () => {
  const result = plan(recipe,[0]);
  assert.equal(result.blocked,false);
  assert.deepEqual(result.recipe.segments,[fallback]);
  assert.deepEqual(result.recipe.sources,[recipe.sources[1]]);
  assert.equal(result.diagnostics[0].status,'omitted');
  assert.deepEqual(plan(recipe,[0]),result);
  assert.deepEqual(recipe.segments,[shot]);
});
test('required shots block; optional shots preserve time even without camera coverage', () => {
  assert.equal(plan({...recipe,sources:recipe.sources.map(s=>({...s,optional:false}))},[0]).blocked,true);
  assert.equal(plan(recipe,[0,1]).blocked,false);
  assert.equal(plan({...recipe,fallbacks:{0:[{...fallback, duration_sec:2}]}},[0]).recipe.segments[0].placeholder,'black');
});
test('unused missing source does not block the plan', () => {
  assert.equal(plan({...recipe,segments:[fallback]},[0]).blocked,false);
});

test('80 saved shots with 16 missing Tune Up inserts yield one warning and exact clocks', () => {
  const {warnings} = require('../web/native-export.js');
  const segments = Array.from({length:80}, (_,i)=>({...shot,source:(i+1)%5===0 ? 0 : 1,master_start_sec:i*2,duration_sec:2,clip_start_sec:i*2}));
  const input={...recipe,segments,fallbacks:{},sources:[{...recipe.sources[0],path:'Tuneup short logo vid.small.mp4'},recipe.sources[1]]};
  const before=JSON.stringify(input);
  const result=plan(input,[0]);
  assert.equal(result.blocked,false);
  assert.equal(result.diagnostics.length,16);
  assert.equal(warnings(result.diagnostics).length,1);
  result.recipe.segments.forEach((s,i)=> {
    assert.equal(s.master_start_sec,i*2);assert.equal(s.duration_sec,2);
    if ((i+1)%5===0) assert.equal(s.placeholder,'black');
    else assert.deepEqual(s,segments[i]);
  });
  assert.equal(JSON.stringify(input),before);
});
