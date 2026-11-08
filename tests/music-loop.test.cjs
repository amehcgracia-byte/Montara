'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '..', 'web', 'montara.js'), 'utf8');
test('Stage main script parses', () => {
  assert.doesNotThrow(() => new vm.Script(source, {filename:'web/montara.js'}));
});
const first = source.indexOf('function musicLoopBounds(audio) {');
const second = source.indexOf('function updateMusicLoopControl(screen) {', first);
assert(first !== -1 && second > first);
const bounded = source.slice(first, second);

function calculate(range, duration) {
  const sandbox = {range, audio: {duration}};
  vm.runInNewContext(bounded + '\nresult = musicLoopBounds(audio);', sandbox);
  return [sandbox.result.start, sandbox.result.end];
}

test('Stage loop uses marked audio start and end', () =>
  assert.deepEqual(calculate({start:20,end:50},120),[20,50]));
test('Stage loop defaults to source duration without an end marker', () =>
  assert.deepEqual(calculate({start:20,end:null},120),[20,120]));
test('Stage loop clamps the end marker to the source duration', () =>
  assert.deepEqual(calculate({start:20,end:200},120),[20,120]));
test('Stage loop never creates a negative interval', () =>
  assert.deepEqual(calculate({start:180,end:200},120),[120,120]));
test('Stage loop handles audio before duration metadata is available', () =>
  assert.deepEqual(calculate({start:0,end:null},NaN),[0,Infinity]));
test('Stage waiting music stops when navigating away from rendering', () => {
  assert(source.includes("if (id !== 'making' && !$('#making').hidden && state.platform === 'youtube') $('#rangeAudio').pause();"));
  assert(source.includes("state.platform !== \"youtube\" || $(\"#making\").hidden || audio.paused"));
});
