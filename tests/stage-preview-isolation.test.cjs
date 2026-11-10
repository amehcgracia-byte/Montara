// Stage review must keep finished pictures visible even if hover videos are pending.
// Loading audio Play/Pause is an independent, optional transport.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const test=require('node:test');
const vm=require('node:vm');
const source=fs.readFileSync('web/montara.js','utf8');

test('Montara client syntax still parses',()=>new vm.Script(source));
test('loading hover previews never makes completed thumbnails busy',()=>{
 const start=source.indexOf('async function updateFrames(first,index)');
 const end=source.indexOf('async function swap(index)',start);
 const body=source.slice(start,end);
 assert.ok(start>0&&end>start);
 assert.match(body,/fig\.classList\.toggle\("busy", !unavailable && \(!item\.thumbnail \|\| swapping\.has\(item\.index\)\)\)/);
 assert.doesNotMatch(body,/fig\.classList\.toggle\("busy"[^\n]*!item\.preview_ready/);
 assert.match(body,/const waitingPhotos = all\.filter\(item => !item\.thumbnail/);
});
test('targeted shot save still sends the requested index',()=>{
 const edit=fs.readFileSync('web/cut-editor.js','utf8');
 assert.match(edit,/async function refreshMusicReview\(index\)/);
 assert.match(edit,/await refreshFrames\(true,index\)/);
});

test('Companion update reminder checks version on entry without launching native code',()=>{
 const html=fs.readFileSync('web/index.html','utf8');
 const app=fs.readFileSync('app.py','utf8');
 assert.match(html, /id="companionUpdateNotice"/);
 assert.match(html, /id="companionUpdateDownload"[^>]*href="\/montara\/companion\/download"/);
 assert.match(source, /void checkCompanionUpdate\(\);/);
 assert.match(source, /info\?\.local_video\?\.engine/);
 assert.match(source, /installed!==expectedCompanionEngine/);
 assert.match(source, /fetch\("\/montara\/companion\/version"/);
 assert.match(app, /@app\.get\("\/montara\/companion\/version"\)/);
 assert.doesNotMatch(source.slice(source.indexOf('async function checkCompanionUpdate'),source.indexOf('async function watchCompanion')), /exec\(|Terminal\.app|osascript|new Function|eval\(/);
});
