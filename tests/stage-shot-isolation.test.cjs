// Regression: editing a single Stage shot must not fan its crop out to every
// shot from the same video. Shared musician assignment is a separate opt-in.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync('web/cut-editor.js', 'utf8');

test('Stage editor JavaScript parses', () => {
  new vm.Script(source, {filename:'web/cut-editor.js'});
});

test('Stage framing Save explicitly restricts the patch to one shot', () => {
  const edit = source.slice(source.indexOf('async function openMusicShot('), source.indexOf('function previewMusicShot('));
  assert.ok(edit.startsWith('async function openMusicShot('));
  assert.match(edit, /project_id:doc\.project_id,revision:doc\.revision,index,/);
  assert.match(edit, /edit_component:'framing',apply_to_source:false,/);
  assert.doesNotMatch(edit, /name="applySource"|apply_to_source:e\.submitter/);
});

test('musician memory remains explicit and opt-in', () => {
  const edit = source.slice(source.indexOf('async function openMusicShot('), source.indexOf('function previewMusicShot('));
  assert.match(edit, /name="rememberMusician"/);
  assert.match(edit, /field\('rememberMusician'\)\.value\?\{remember_musician:/);
});

test('each Stage shot has a movement checkbox, saved without touching siblings', () => {
  const edit = source.slice(source.indexOf('async function openMusicShot('), source.indexOf('function previewMusicShot('));
  assert.match(edit, /type="checkbox" name="movement"/);
  assert.match(edit, /field\('movement'\)\.checked=doc\.movement !== false/);
  assert.match(edit, /movement:field\('movement'\)\.checked/);
});
