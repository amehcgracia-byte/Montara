/* H3: native Chema browser bridge is tested without jsdom or a second UI.
 * Node's built-in VM supplies only the actual browser primitives it needs.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function main() {
  const source = fs.readFileSync(
    path.join(__dirname,'../urano/native_owner_browser_bridge.js'),'utf8');
  const calls = [];
  const csrf = 'a'.repeat(64);
  const footage = {hidden:true};
  let observed = null;
  class FakeObserver {
    constructor(callback) { this.callback=callback; }
    observe(target, options) {
      assert.equal(target,footage);
      assert.deepEqual(Array.from(options.attributeFilter),['hidden']);
      observed=this.callback;
    }
    disconnect() {observed=null;}
  }

  async function network(url,options={}) {
    calls.push({url,options});
    if(url==='/urano/v1/session/refresh') {
      return new Response(JSON.stringify({csrf}),{
        status:200,headers:{'Content-Type':'application/json'}});
    }
    if(url==='/urano/v1/native/ensure') {
      return new Response(JSON.stringify({state:'ready',generation:4}),{
        status:200,headers:{'Content-Type':'application/json'}});
    }
    if(url==='/urano/v1/native/rpc/montara/recovery/latest') {
      return new Response(JSON.stringify({error:'No saved project'}),{
        status:404,headers:{'Content-Type':'application/json'}});
    }
    if(url==='/urano/v1/native/rpc/api/v1/wizard/projects/new') {
      return new Response(JSON.stringify({ok:true}),{
        status:200,headers:{'Content-Type':'application/json',
                            'X-Montara-Engine-Generation':'4'}});
    }
    if(url==='/urano/v1/native/rpc/api/v1/wizard/review?render=0') {
      return new Response(JSON.stringify({
        items:[{index:0,
          thumbnail:'/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg',
          preview:'/api/v1/wizard/review/preview/0?v=123abc'}],
        platform:'youtube'
      }),{status:200,headers:{'Content-Type':'application/json'}});
    }
    if(url==='/urano/v1/native/rpc/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg') {
      return new Response(new Uint8Array([255,216,255,217]),{
        status:200,headers:{'Content-Type':'image/jpeg'}});
    }
    if(url.startsWith('/urano/v1/native/rpc/montara/audio?path=')) {
      return new Response(new Uint8Array([82,73,70,70,0,0,0,0]),{
        status:200,headers:{'Content-Type':'audio/x-wav'}});
    }
    if(url==='/urano/v1/native/rpc/montara/branding') {
      return new Response(JSON.stringify({mode:'montara',has_logo:false}),{
        status:200,headers:{'Content-Type':'application/json'}});
    }
    if(url==='/urano/v1/native/rpc/api/v1/edit/shot?index=3') {
      return new Response(JSON.stringify({index:3,revision:'a'.repeat(20)}),
        {status:200,headers:{'Content-Type':'application/json'}});
    }
    if(url==='/urano/v1/native/rpc/api/v1/edit/shot') {
      return new Response(JSON.stringify({ok:true}),
        {status:200,headers:{'Content-Type':'application/json'}});
    }
    if(url==='/urano/v1/native/rpc/api/v1/edit/shot/frame?index=3&choice=0&revision='+('a'.repeat(20))) {
      return new Response(new Uint8Array([255,216,255,217]),
        {status:200,headers:{'Content-Type':'image/jpeg'}});
    }
    if(url==='/montara/companion/version') {
      return new Response(JSON.stringify({version:'0.6.5'}),{status:200});
    }
    throw Error('Unexpected real network call '+url);
  }

  class FakeMediaElement {
    constructor() {this._src='';this.loaded=false;}
    load(){this.loaded=true;}
    dispatchEvent(){}
  }
  Object.defineProperty(FakeMediaElement.prototype,'src',{
    configurable:true,get(){return this._src;},set(v){this._src=v;}
  });
  class FakeAudioElement extends FakeMediaElement {}
  class FakeImageElement extends FakeMediaElement {}
  Object.defineProperty(FakeImageElement.prototype,'src',{
    configurable:true,get(){return this._src;},set(v){this._src=v;}
  });
  const window = {fetch:network};
  const context = {
    window, location:{
      origin:'https://montara.test',
      href:'https://montara.test/urano/v1/native/'
    },
    document:{getElementById:id => id==='footage'?footage:null},
    MutationObserver:FakeObserver,URL,Response,Headers,
    XMLHttpRequest:undefined,
    HTMLMediaElement:FakeMediaElement,HTMLAudioElement:FakeAudioElement,
    HTMLImageElement:FakeImageElement,
  };
  vm.runInNewContext(source,context,{filename:'native_owner_browser_bridge.js'});
  assert.equal(typeof window.fetch,'function');

  // Chema calls Latest on startup: neither Google CSRF nor the Engine may
  // be contacted until Chema itself shows its original Footage/Stage screen.
  const startup = window.fetch('/montara/recovery/latest');
  await Promise.resolve();
  assert.equal(calls.length,0);
  assert.equal(typeof observed,'function');

  // Original Home version is a lightweight local label, not an Engine start.
  const version=await window.fetch('/montara/version');
  assert.equal(version.status,200);
  assert.equal(calls.length,0);

  footage.hidden=false;
  observed();
  const latest=await startup;
  assert.equal(latest.status,404);
  assert.deepEqual(calls.map(c=>c.url),[
    '/urano/v1/session/refresh','/urano/v1/native/ensure',
    '/urano/v1/native/rpc/montara/recovery/latest']);
  assert.equal(calls[2].options.headers.get('X-Urano-CSRF'),csrf);
  assert.equal(calls[2].options.headers.get('X-Montara-Engine-Generation'),'4');

  const created=await window.fetch('/api/v1/wizard/projects/new',{
    method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  assert.equal(created.status,200);
  assert.equal(calls.length,4); // same worker and same rotating CSRF
  assert.equal(calls[3].url,
    '/urano/v1/native/rpc/api/v1/wizard/projects/new');
  assert.equal(calls[3].options.method,'POST');

  const review=await window.fetch('/api/v1/wizard/review?render=0');
  assert.equal(review.status,200);
  const reviewResult=await review.json();
  assert.ok(reviewResult.items[0].thumbnail.startsWith('blob:'));
  assert.equal(calls[4].url,
    '/urano/v1/native/rpc/api/v1/wizard/review?render=0');
  assert.equal(calls[5].url,
    '/urano/v1/native/rpc/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg');
  const framePath='/api/v1/edit/shot/frame?index=3&choice=0&revision='+('a'.repeat(20));
  const shot=await window.fetch('/api/v1/edit/shot?index=3');
  assert.equal(shot.status,200);
  assert.equal((await shot.json()).index,3);
  const shotPatch=await window.fetch('/api/v1/edit/shot',{
    method:'PATCH',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({project_id:'/owner/Projects/test',revision:'a'.repeat(20),
      index:3,choice:0,apply_to_source:false,edit_component:'movement'})
  });
  assert.equal(shotPatch.status,200);
  const image=new FakeImageElement();
  image.src=framePath;
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(image._src.startsWith('blob:'),image._src);
  assert.equal(image.src,framePath);
  assert.equal(calls.at(-1).url,'/urano/v1/native/rpc/'+framePath.slice(1));
  const branding=await window.fetch('/montara/branding',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({mode:'montara'})
  });
  assert.equal(branding.status,200);
  assert.equal(calls[6].url,'/urano/v1/native/rpc/montara/branding');
  assert.equal(calls[6].options.headers.get('X-Urano-CSRF'),csrf);
  assert.equal(calls[6].options.headers.get('X-Montara-Engine-Generation'),'4');

  await assert.rejects(
    () => window.fetch('/api/v1/internal/other'),
    /not enabled/);
  await assert.rejects(
    () => window.fetch('/montara/session/secret'),
    /not enabled/);
  assert.equal(calls.length,7);
  const sound = new FakeAudioElement();
  sound.src='/montara/audio?path='+encodeURIComponent('/private/WizardUploads/song.wav');
  await new Promise(resolve=>setTimeout(resolve,30));
  assert.ok(sound.loaded,'Original song player must load its private audio blob');
  assert.ok(sound._src.startsWith('blob:'),'Audio bytes must use a browser-local blob');
  assert.equal(calls[7].url,'/urano/v1/native/rpc/montara/audio?path='+encodeURIComponent('/private/WizardUploads/song.wav'));
  assert.equal(calls[7].options.headers.get('X-Urano-CSRF'),csrf);
  console.log('H3_NATIVE_BROWSER_BRIDGE_PASS startup-lazy, csrf, owner-worker, new, secured-thumbnail-blob, blocked-routes');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
