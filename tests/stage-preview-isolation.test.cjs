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

test('a failed version request recovers and a server rollback makes the notice visible', async () => {
 const vm = require('node:vm');
 const installed = 'a'.repeat(40);
 let required = installed;
 let fail = true;
 const elements = new Map();
 const context = vm.createContext({
   isDesktopMac: true,
   $: id => {
     if (!elements.has(id)) elements.set(id, {hidden: true});
     return elements.get(id);
   },
   fetch: async () => ({ok: !fail, json: async () => ({engine: required})}),
   montaraCompanion: {detect: async () => ({local_video: {engine: installed}})},
   console: {warn() {}},
 });
 vm.runInContext(source.slice(source.indexOf('let companionVersionRequest'), source.indexOf('$("#companionUpdateRecheck").addEventListener')), context);
 const check = () => vm.runInContext('checkCompanionUpdate()', context);
 await check();
 fail = false;
 required = 'b'.repeat(40);
 await check();
 assert.equal(elements.get('#companionUpdateNotice').hidden, false);
 assert.match(elements.get('#companionUpdateMessage').textContent, /bbbbbbb.*aaaaaaa/);
 required = installed;
 await check();
 assert.equal(elements.get('#companionUpdateNotice').hidden, true);
});
