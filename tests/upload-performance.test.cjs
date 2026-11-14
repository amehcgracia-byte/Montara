'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
for (const name of ['companion.js', 'resumable-upload.js']) {
  test(name + ' parses', () => {
    const source = fs.readFileSync(path.join(__dirname,'..','web',name),'utf8');
    assert.doesNotThrow(() => new vm.Script(source));
  });
  test(name + ' records phase durations without source filenames', () => {
    const source = fs.readFileSync(path.join(__dirname,'..','web',name),'utf8');
    assert(source.includes("'[Montara upload timing]'"));
    assert(source.includes('total_sec'));
    assert(!source.includes('filename: file.name'));
  });
}

test('a dropped response body retries only the ready proxy read', async () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'web', 'companion.js'), 'utf8');
  let reads = 0;
  const context = vm.createContext({
    AbortController, Blob, TypeError, setTimeout: (resolve, delay) => { if (delay < 120000) resolve(); }, clearTimeout,
    fetch: async url => {
      assert.match(url, /\/proxies\/ready\/file$/);
      reads++;
      return {ok: true, headers: new Headers({'Content-Length':'3'}), blob: async () => {
        if (reads === 1) throw new TypeError('Failed to fetch');
        return new Blob(['mp4']);
      }};
    },
  });
  vm.runInContext(source.replace('  async function fingerprint', '  globalThis.readProxy = readProxy;\n  async function fingerprint'), context);
  const received = await context.readProxy('ready', () => false);
  assert.equal(received.blob.size, 3);
  assert.equal(received.retries, 1);
  assert.equal(reads, 2);
  assert.equal(await context.readProxy('ready', () => true), null);
  assert.equal(reads, 2);
});

test('an unresponsive proxy body times out and retries the same cached file', async () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'web', 'companion.js'), 'utf8');
  let reads = 0;
  const context = vm.createContext({
    AbortController, Blob, TypeError, clearTimeout,
    setTimeout: (fn, delay) => setTimeout(fn, delay === 120000 ? 10 : 0),
    fetch: async (url, {signal}) => {
      assert.match(url, /\/proxies\/ready\/file$/);
      const attempt = ++reads;
      return {ok: true, headers: new Headers({'Content-Length': '3'}), blob: () => {
        if (attempt > 1) return Promise.resolve(new Blob(['mp4']));
        return new Promise((_, reject) => {
          signal.addEventListener('abort', () => reject(signal.reason), {once: true});
        });
      }};
    },
  });
  vm.runInContext(source.replace('  async function fingerprint', '  globalThis.readProxy = readProxy;\n  async function fingerprint'), context);
  const received = await context.readProxy('ready', () => false);
  assert.equal(received.blob.size, 3);
  assert.equal(received.retries, 1);
  assert.equal(reads, 2);
});

test('removed uploads cannot keep Footage busy while retained uploads still block', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'web', 'montara.js'), 'utf8');
  const state = {uploads: 2, files: [
    {kind: 'video'}, {kind: 'master'}, {kind: 'uploading', removed: true},
  ]};
  const context = vm.createContext({state});
  vm.runInContext(source.slice(source.indexOf('function footageIsPreparing()'), source.indexOf('function renderFiles()')), context);
  const isPreparing = () => vm.runInContext('footageIsPreparing()', context);
  assert.equal(isPreparing(), false);
  state.files.push({kind: 'uploading'});
  assert.equal(isPreparing(), true);
});

test('sixteen audio imports occupy at most three slots and advance after failure or removal', async () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'web', 'montara.js'), 'utf8');
  const pending = new Map();
  const started = [];
  const entries = Array.from({length: 16}, (_, id) => ({id}));
  const context = vm.createContext({
    entries,
    AUDIO_NAME: /wav$/i,
    renderFiles() {},
    performUpload: async (_, entry) => {
      started.push(entry.id);
      await new Promise((resolve, reject) => pending.set(entry.id, {resolve, reject}));
    },
  });
  const queue = source.slice(source.indexOf('const audioUploadQueue'), source.indexOf('async function performUpload'));
  vm.runInContext(queue + '\nentries.forEach(entry => upload({name: "track.wav"}, entry));', context);
  assert.deepEqual(started, [0, 1, 2]);
  assert.equal(entries[15].phase, 'Queued');
  entries[3].removed = true;
  pending.get(0).reject(new Error('Upload stalled'));
  await new Promise(setImmediate);
  assert.equal(entries[0].error, 'Upload stalled');
  assert.deepEqual(started, [0, 1, 2, 4]);
  for (let id = 1; id < 16; id++) {
    if (id === 3) continue;
    assert.equal(vm.runInContext('activeAudioUploads <= 3', context), true);
    pending.get(id).resolve();
    await new Promise(setImmediate);
  }
  assert.equal(started.length, 15);
  assert.equal(vm.runInContext('activeAudioUploads', context), 0);
});
