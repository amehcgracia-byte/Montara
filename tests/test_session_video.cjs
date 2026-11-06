const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../web/session-video.js'), 'utf8');
const ctx = vm.createContext({}); vm.runInContext(source, ctx);
const choose = vm.runInContext('SessionVideo.songForClips', ctx);
const songs = [{id:1,start:0,end:60}, {id:2,start:65,end:130}];
const clip = (offset, duration=20, rest={}) => ({offset_sec:offset, duration_sec:duration, ...rest});
assert.equal(choose(songs, {a:clip(75), b:clip(90)}).id, 2);
assert.equal(choose(songs, {a:clip(10), b:clip(80,20,{low_confidence:true})}).id, 1);
assert.throws(()=>choose(songs, {a:clip(10),b:clip(90)}), /different songs/);
assert.throws(()=>choose(songs, {a:clip(10,20,{unstable_sync:true})}), /confidently/);
assert.throws(()=>choose(songs, {a:clip(50,25)}), /several songs/);
assert.throws(()=>choose(songs, {a:clip(NaN)}), /confidently/);
assert.throws(()=>choose(songs, {a:clip(-90)}), /confidently/);
console.log('7 session-video matching scenarios passed');

// Push's registration wrapper must preserve Stage's completed-master flag;
// dropping it would recursively detect/mix the whole session again.
const pack = fs.readFileSync(require('node:path').join(__dirname, '../web/push-pack.js'), 'utf8');
const wrapper = pack.slice(pack.indexOf('const packNativeRegister='), pack.indexOf("  const url=$('#pushPackURL')")) + '\n};';
const calls = [];
const bridge = vm.createContext({registerProject:async options=>calls.push(options),packEnabled:()=>false});
vm.runInContext(wrapper, bridge);
bridge.registerProject({mixed:true}).then(()=>{
  assert.equal(calls.length,1);assert.equal(calls[0].mixed,true);
  console.log('Push wrapper preserves Stage master completion');
});

// An older saved edit may lack duration, but the original fingerprint retains its size.
const main = fs.readFileSync(require('node:path').join(__dirname,'../web/montara.js'),'utf8');
const whole = main.slice(main.indexOf('function isWholeSession()'),main.indexOf('async function registerProject'));
const restored = vm.createContext({state:{files:[]},isAudioEntry:()=>true,LONG_AUDIO_BYTES:150*1024*1024,LONG_AUDIO_SECONDS:1200});
vm.runInContext(whole,restored);
for(const [files,expected] of [
  [[{preview:true}],true],
  [[{original:{size:2*1024**3},duration:0}],true],
  [[{original:{size:2*1024**3},duration:300}],false],
  [[{duration:1800}],true],
  [[{duration:60}],false],
]){restored.state.files=files;assert.equal(restored.isWholeSession(),expected);}
console.log('5 restored-session routing scenarios passed');
