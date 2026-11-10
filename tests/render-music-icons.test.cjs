const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const html=fs.readFileSync('web/index.html','utf8'),js=fs.readFileSync('web/montara.js','utf8'),css=fs.readFileSync('web/montara.css','utf8');
test('render music has a visible icon and accessible labels',()=>{
  const start=html.indexOf('id="makingAudioToggle"');
  assert.ok(start>=0);
  const button=html.slice(html.lastIndexOf('<button',start),html.indexOf('</button>',start)+9);
  assert.ok(button.includes('<svg '));
  assert.ok(button.includes('making-icon-play'));
  assert.ok(button.includes('making-icon-pause'));
  assert.ok(!button.includes('>Play music</button>'));
  assert.ok(button.includes('aria-label="Play music while Montara works"'));
});
test('music play button toggles icons with pressed state, no text replacement',()=>{
  assert.ok(css.includes('making-audio[aria-pressed="true"] .making-icon-pause'));
  assert.ok(!js.includes('button.textContent = playing'));
  assert.ok(js.includes('button.setAttribute("aria-pressed"'));
  assert.ok(js.includes('button.title = playing'));
});
