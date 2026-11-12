/* Stage launches must not inherit another Owner project's remembered edit. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const project='7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505';
const other='2c0e0ecf-d9d0-482e-a09f-9689f89d024a';
const code=fs.readFileSync(path.resolve(__dirname,'../urano/owner_browser_bridge.js'),'utf8');
function run(query,saved,extras={}) {
  const values=new Map(Object.entries({...extras,'montara-open-edit':saved}));
  const storage={
    getItem:k=>values.get(k)||null,
    setItem:(k,v)=>values.set(k,String(v)),
    removeItem:k=>values.delete(k)
  };
  const calls=[];
  const window={fetch:async(url)=>{calls.push(url);return {ok:true,status:200}}};
  vm.runInNewContext(code,{
    window,document:{currentScript:{dataset:{ownerProject:project}}},
    location:{origin:'https://montara.test',href:'https://montara.test/urano/v1/editor/projects/'+project+'/'+query},
    URL,Headers,Promise,Number,WeakMap,Object,Error,sessionStorage:storage
  });
  assert.equal(calls.length,0);
  return values;
}
const past=JSON.stringify({project:'/private/Projects/'+other,platform:'youtube',step:'frames'});
const a=run('?start=stage',past);
assert.equal(a.has('montara-open-edit'),false);
assert.equal(a.get('montara-owner-edit:'+other),past);
const own=JSON.stringify({project:'/private/Projects/'+project,platform:'youtube',step:'footage'});
const b=run('?resume=footage',past,{['montara-owner-edit:'+project]:own});
assert.equal(b.get('montara-open-edit'),own);
assert.equal(b.get('montara-owner-edit:'+other),past);
console.log('OWNER_TAB_PROJECT_ISOLATION_PASS preserved prior edit and no cross-project resume');
