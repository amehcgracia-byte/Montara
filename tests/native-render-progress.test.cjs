// Keep native export progress honest: staged checks, no premature shot bars,
// fixed percentage, and at most two original identity checks at once.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const ui = fs.readFileSync('web/montara.js','utf8');
const css = fs.readFileSync('web/montara.css','utf8');
const companion = fs.readFileSync('companion/video_jobs.py','utf8');

test('montara client JavaScript parses',()=>new vm.Script(ui,{filename:'web/montara.js'}));
test('original camera lookup is bounded, and complete video downloads are sequential',()=>{
  const start=ui.indexOf('async function finishOriginalVideo(');
  const end=ui.indexOf('async function watchNativeVideo(',start);
  const body=ui.slice(start,end);
  assert.match(body,/recipe\.sources\.slice\(index,index\+2\)\.map\(verifySources\)/);
  assert.match(body,/method:'HEAD'/);
  assert.match(body,/for\(const source of recipe\.sources\)/);
  assert.doesNotMatch(body,/Promise\.all\(.*saveInProject/);
});
test('bar display waits for a real started shot',()=>{
  const start=ui.indexOf('function renderShotBars(');
  const end=ui.indexOf('function setProgress(',start);
  assert.match(ui.slice(start,end),/shots\.some\(t => Number\(t\.percent \|\| 0\) > 0\)/);
});
test('native status uses phase and elapsed time',()=>{
  assert.match(ui,/const phase = status\.message\?\.trim\(\)/);
  assert.match(ui,/Number\.isFinite\(status\.elapsed_sec\)/);
  assert.match(companion,/result\['elapsed_sec'\]/);
});
test('percentage text is not inside the animated zoom wrapper',()=>{
  assert.match(css,/\.ring \.ring-brand\{[^}]*gap:8px\}/);
  assert.match(css,/\.ring \.loading-mark\{[^}]*animation:brandbreathe/);
});

test('Companion shows explicit pre-render phases before the FFmpeg export',()=>{
  const local = fs.readFileSync('companion/local_video.py','utf8');
  assert.match(local,/Checking local camera metadata/);
  assert.match(local,/Preparing reviewed shot plan for original-quality export/);
  assert.match(local,/Starting export engine/);
});
