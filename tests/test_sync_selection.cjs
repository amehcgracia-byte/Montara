const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');const fs=require('node:fs');
const policy=vm.runInNewContext(fs.readFileSync('web/sync-selection.js','utf8')+';SyncSelection');
test('silent footage is separate from uncertain cameras; filler does not need sync',()=>{
 const files=[{path:'silent'},{path:'wrong'},{path:'good'},{path:'chosen',usage:'filler'}];
 const result=policy.review(files,{a:{source_path:'silent',no_audio:true},b:{source_path:'wrong',offset_sec:0,duration_sec:20,confidence:30,unstable_sync:true},c:{source_path:'good',offset_sec:10,duration_sec:20}});
 assert.deepEqual(Array.from(result.ready,x=>x.path),['good']);
 assert.deepEqual(Array.from(result.silent,x=>x.path),['silent']);
 assert.deepEqual(Array.from(result.uncertain,x=>x.path),['wrong']);
});
test('high confidence cannot rescue nonoverlap, missing results or invalid times',()=>{
 const result=policy.review([{path:'outside'},{path:'missing'},{path:'nan'}],{a:{source_path:'outside',offset_sec:70,duration_sec:10,confidence:99},b:{source_path:'nan',offset_sec:NaN,duration_sec:10}},{end:30});
 assert.equal(result.uncertain.length,3);assert.equal(result.ready.length,0);
});
