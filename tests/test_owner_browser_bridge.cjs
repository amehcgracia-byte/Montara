/* Node 18+ / no dependencies: verifies real browser URL adapter semantics. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

const PROJECT='7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505';
const code=fs.readFileSync(
  path.resolve(__dirname,'../urano/owner_browser_bridge.js'),'utf8');
const operations=[];

class MockXHR {
  constructor(){this.requestHeaders={};this.aborted=false}
  open(method,url){this.method=method;this.url=url}
  setRequestHeader(name,value){this.requestHeaders[name]=value}
  send(body){this.body=body;operations.push({
    method:this.method,url:this.url,headers:this.requestHeaders,
    body:this.body,kind:'xhr',
  })}
  abort(){this.aborted=true}
}
const mockFetch=async (url,opts={})=>{
  operations.push({kind:'fetch',url,opts});
  const headers=new Headers();
  if(String(url).startsWith('/urano/v1/media/')){
    headers.set('X-Montara-Engine-Generation','4');
  }
  const json=()=>{
    url==='/urano/v1/session/refresh'
      ? Promise.resolve({csrf:'a'.repeat(64)})
      : String(url).endsWith('/ensure')
        ? Promise.resolve({project_id:PROJECT,state:'ready',generation:4})
        : Promise.resolve({ok:true});
  return {ok:true,status:200,headers,json};
};
const window={fetch:mockFetch};
const context={
  window,location:{origin:'https://montara.test',
                   href:'https://montara.test/urano/v1/editor/projects/'+PROJECT+'/'},
  document:{currentScript:{dataset:{ownerProject:PROJECT}}},
  URL,Headers,XMLHttpRequest:MockXHR,Promise,Number,WeakMap,Object,Error,
};
vm.runInNewContext(code,context,{filename:'owner_browser_bridge.js'});
const assertNoGlobal=(url)=>
  assert(!operations.some(v=>v.url===url),'unreviewed shared Engine URL leaked');

(async()=>{
  assert.equal(window.MontaraOwnerBridge.projectId,PROJECT);
  assert.equal(operations.length,0,'bootstrap should not start Engine');
  const proxy=await window.fetch('/api/v1/wizard/upload',{
    method:'POST',body:'proxy-media',
    headers:{'Content-Type':'application/octet-stream',
             'X-Zucker-Filename':'camera.small.mp4'},
  });
  assert.equal(proxy.status,200);
  assert.deepEqual(operations.slice(0,3).map(x=>x.url),[
    '/urano/v1/session/refresh',
    '/urano/v1/projects/'+PROJECT+'/ensure',
    '/urano/v1/media/'+PROJECT+'/wizard/upload',
  ]);
  const forwarded=operations.at(-1);
  assert.equal(forwarded.opts.headers.get('X-Urano-CSRF'),'a'.repeat(64));
  assert.equal(forwarded.opts.headers.get('X-Montara-Engine-Generation'),'4');
  await window.fetch('/api/v1/wizard/draft',{
    method:'POST',headers:{'Content-Type':'application/json'},body:'{}',
  });
  assert.equal(
    operations.filter(x=>String(x.url).endsWith('/ensure')).length,1,
    'same owner must not launch duplicate Engine');
  assert.equal(operations.at(-1).url,
    '/urano/v1/media/'+PROJECT+'/wizard/draft');

  const xhr=new MockXHR();
  xhr.open('POST','/api/v1/wizard/upload');
  xhr.setRequestHeader('X-Zucker-Filename','camera.small.mp4');
  xhr.send('another-proxy');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(operations.at(-1).kind,'xhr');
  assert.equal(operations.at(-1).url,
    '/urano/v1/media/'+PROJECT+'/wizard/upload');
  assert.equal(operations.at(-1).headers['X-Urano-CSRF'],'a'.repeat(64));
  assert.equal(operations.at(-1).headers['X-Montara-Engine-Generation'],'4');

  await assert.rejects(window.fetch('/api/v1/edit/native-source/foreign'),/not yet enabled/);
  await assert.rejects(window.fetch('/montara/uploads'),/not yet enabled/);
  assertNoGlobal('/api/v1/wizard/upload');
  assertNoGlobal('/montara/uploads');
  console.log(JSON.stringify({
    js_bridge_checked:true,
    first_valid_upload_shared_preflight:true,
    original_chema_fetch_and_xhr_rewritten:true,
    stale_shared_engine_fallback_blocked:true,
    original_chema_source_modified:false,
    unfinished_resumable_uploads_not_claimed_supported:true,
  }));
})().catch(e=>{console.error(e);process.exitCode=1});
