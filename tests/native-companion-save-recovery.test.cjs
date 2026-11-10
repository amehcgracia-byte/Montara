const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const companion=fs.readFileSync('web/companion.js','utf8');
const editor=fs.readFileSync('web/montara.js','utf8');

test('saving a local file surfaces the actual Companion HTTP status and error',async()=>{
  const scope={fetch:async()=>({ok:false,status:404,json:async()=>({error:'unknown project'})}),Blob,AbortController,console,URL,crypto:require('node:crypto').webcrypto};
  vm.createContext(scope);
  vm.runInContext(companion+';globalThis.montaraCompanionForTest=montaraCompanion;',scope);
  const instance=scope.montaraCompanionForTest;
  await assert.rejects(instance.saveInProject('deadbeef01234567','test.mp4',new Blob(['data'])),e=>
    e.status===404 && e.companionError==='unknown project' && /404.*unknown project/.test(e.message));
});
test('Native export recovers only unknown project errors by reselecting local destination',()=>{
  assert.match(editor,/error\.status !== 404 \|\| error\.companionError !== 'unknown project'/);
  assert.match(editor,/state\.localProject = selected/);
  assert.match(editor,/return montaraCompanion\.saveInProject\(selected\.id, name, blob\)/);
  assert.match(editor,/await saveNativeAsset\(master,masterBlob\)/);
  assert.match(editor,/await saveNativeAsset\(logo,await image\.blob\(\)\)/);
  assert.match(editor,/!blob\?\.size/);
});
