// The loading-screen audio transport must reuse the existing song-range audio.
// Render jobs must never be affected by Play/Pause.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const js = fs.readFileSync('web/montara.js', 'utf8');
const html = fs.readFileSync('web/index.html', 'utf8');
const css = fs.readFileSync('web/montara.css', 'utf8');

test('Montara JavaScript parses', () => new vm.Script(js));
test('loader provides a reachable accessible transport', () => {
  assert.match(html, /id="makingAudioToggle"[^>]*type="button"[^>]*hidden/);
  assert.match(css, /\.making-audio\[hidden\]/);
});
test('transport controls only the original range player', () => {
  const start = js.indexOf('function prepareMakingPlayback()');
  const end = js.indexOf('function audioUrl(f)', start);
  const block = js.slice(start, end);
  assert.ok(start > 0 && end > start);
  assert.match(block, /\$\("#rangeAudio"\)/);
  assert.match(block, /audio\.play\(\)/);
  assert.match(block, /audio\.pause\(\)/);
  assert.match(block, /button\.hidden = !audio\.getAttribute\("src"\)/);
  assert.doesNotMatch(block, /startPolling|stopPolling|cancelVideo|beginWork|renderFrames/);
});
test('music stops when leaving the loading screen', () => {
  assert.match(js, /if \(id !== "making" && !\$\("#making"\)\.hidden\) \$\("#rangeAudio"\)\.pause\(\)/);
  assert.match(js, /if \(id === "making"\) prepareMakingPlayback\(\)/);
});
