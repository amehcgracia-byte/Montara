const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const editor=fs.readFileSync('web/cut-editor.js','utf8');

test('Music camera editor uses English labels and one name field, never musician allocation lists',()=>{
  assert.match(editor,/Mark this view as a musician/);
  assert.match(editor,/Musician or instrument name/);
  assert.match(editor,/\.music-view-buttons/);
  assert.match(editor,/> Movement<\/label>/);
  assert.doesNotMatch(editor,/Movimiento|left to right|data-person=|performer_roles:assignments|Remember this crop as a musician/);
});
test('Switching cameras resets the preview from the selected camera, not the prior shot',()=>{
  const start=editor.indexOf("field('camera').onchange");
  const end=editor.indexOf('    update();',start);
  const part=editor.slice(start,end+15);
  assert.match(part,/selected\.pose/);
  assert.match(part,/selected\.framing/);
});
test('Saved musician buttons apply a view only to the current selected shot',()=>{
  assert.match(editor,/applyRemembered/);
  assert.match(editor,/button\.onclick=\(\)=>applyRemembered\(saved\)/);
  assert.match(editor,/apply_to_source:false/);
  assert.doesNotMatch(editor,/apply_to_source:true/);
});
