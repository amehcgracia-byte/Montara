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
