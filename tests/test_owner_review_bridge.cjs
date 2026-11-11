/* Browser-contract acceptance: original JM review photos and hover videos
 * use only authenticated Owner media fetches, never public Engine URLs.
 * Node 20+ no dependencies, no production browser or Companion.
 */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const ID='7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505';
const BASE='/urano/v1/media/'+ID+'/';
const calls=[];
class URLWithBlob extends URL {
  static createObjectURL(blob) {
    const id='blob:montara-review-'+calls.filter(c=>c.url?.includes('/wizard/review/')).length;
    assert(blob instanceof Blob);
    return id;
  }
}
class Media {
  get src(){return this._src||''}
  set src(v){this._src=v}
  load(){this.loaded=(this.loaded||0)+1}
  dispatchEvent(e){this.event=e.type}
}
class Video extends Media{}
async function nativeFetch(url,opts={}){
  const address=String(url);
  calls.push({url:address,opts});
  if(address==='/urano/v1/session/refresh'){
    return new Response(JSON.stringify({csrf:'a'.repeat(64)}),{
      headers:{'Content-Type':'application/json'}});
  }
  if(address==='/urano/v1/projects/'+ID+'/ensure'){
    return new Response(JSON.stringify({
      state:'ready',project_id:ID,generation:7}),{
      headers:{'Content-Type':'application/json'}});
  }
  const hdr={'X-Montara-Engine-Generation':'7'};
  if(address===BASE+'wizard/review?render=1&shot=0'){
    const body={platform:'youtube',items:[{
      index:0,thumbnail:'/api/v1/wizard/review/thumbnail/assets-v2/frame-0.jpg',
      preview:'/api/v1/wizard/review/preview/0?v=123abc',
    }]};
    return new Response(JSON.stringify(body),{
      headers:{...hdr,'Content-Type':'application/json'}});
  }
  if(address===BASE+'wizard/review/thumbnail/assets-v2/frame-0.jpg'){
    return new Response(new Blob(['jpeg'],{type:'image/jpeg'}),{
      headers:{...hdr,'Content-Type':'image/jpeg'}});
  }
  if(address===BASE+'wizard/review/preview/0?v=123abc'){
    return new Response(new Blob(['mp4'],{type:'video/mp4'}),{
      headers:{...hdr,'Content-Type':'video/mp4'}});
  }
  if(address===BASE+'wizard/review/render'){
    return new Response(JSON.stringify({status:'running'}),{
      status:202,headers:{...hdr,'Content-Type':'application/json'}});
  }
  if(address===BASE+'wizard/review/replace'){
    return new Response(JSON.stringify({replaced:[0]}),{
      headers:{...hdr,'Content-Type':'application/json'}});
  }
  if(address===BASE+'edit/native-recipe?project_id=owner-worker'){
    return new Response(JSON.stringify({
      engine:'b'.repeat(40),revision:'abcdef0123456789abcd',platform:'youtube',
      sources:[],segments:[],
    }),{headers:{'Content-Type':'application/json',...hdr}});
  }
  if(address===BASE+'edit/native-master?project_id=owner-worker&revision=abcdef0123456789abcd'){
    return new Response(new Blob(['wav-master'],{type:'application/octet-stream'}),{
      headers:{'Content-Type':'application/octet-stream',...hdr}});
  }
  if(address===BASE+'version'){
    return new Response(JSON.stringify({version:'beta'}),{
      headers:{'Content-Type':'application/json'}});
  }
  throw Error('Unexpected unreviewed URL '+address);
}
const window={fetch:nativeFetch};
const ctx={
  window, document:{currentScript:{dataset:{ownerProject:ID}}},
  location:{origin:'https://montara.test',
            href:'https://montara.test/urano/v1/editor/projects/'+ID+'/'},
  URL:URLWithBlob, Headers, Response, Blob, Event,
  XMLHttpRequest:undefined,HTMLMediaElement:Media,HTMLVideoElement:Video,
  Promise,Number,Object,Map,WeakMap,Error,
};
vm.runInNewContext(fs.readFileSync(
  path.resolve(__dirname,'../urano/owner_browser_bridge.js'),'utf8'),
  ctx,{filename:'owner_browser_bridge.js'});
(async()=>{
  const before=calls.length;
  await window.fetch('/montara/version');
  assert.equal(calls.length,before+2); // refresh + version; no Engine
  const review=await window.fetch('/api/v1/wizard/review?render=1&shot=0');
  assert.equal(review.status,200);
  const body=await review.json();
  assert.equal(body.items.length,1);
  assert(body.items[0].thumbnail.startsWith('blob:montara-review-'));
  const imgCall=calls.find(c=>c.url.endsWith('/wizard/review/thumbnail/assets-v2/frame-0.jpg'));
  assert(imgCall);
  assert.equal(imgCall.opts.headers.get('X-Urano-CSRF'),'a'.repeat(64));
  const video=new Video();
  video.src=body.items[0].preview;
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(video.src,body.items[0].preview);
  assert(video._src.startsWith('blob:montara-review-'));
  assert(video.loaded>0);
  const previewCall=calls.find(c=>c.url.includes('wizard/review/preview/0'));
  assert(previewCall);
  assert.equal(previewCall.opts.headers.get('X-Montara-Engine-Generation'),'7');
  const recipe=await window.fetch('/api/v1/edit/native-recipe?project_id=%2Ftmp%2Fprivate-worker');
  assert.equal(recipe.status,200);
  assert.equal((await recipe.json()).engine,'b'.repeat(40));
  const master=await window.fetch('/api/v1/edit/native-master?revision=abcdef0123456789abcd&project_id=%2Ftmp%2Fprivate-worker');
  assert.equal(master.status,200);
  assert.equal(await master.text(),'wav-master');
  await assert.rejects(window.fetch('/api/v1/edit/native-master?revision=../3&project_id=other'),
    /not yet enabled/);
  const render=await window.fetch('/api/v1/wizard/review/render',{
    method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  assert.equal(render.status,202);
  const swapped=await window.fetch('/api/v1/wizard/review/replace',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:'{"rejected":[0]}'});
  assert.equal(swapped.status,200);
  await assert.rejects(
    window.fetch('/api/v1/wizard/review/thumbnail/evil/other.jpg'),
    /not yet enabled/);
  await assert.rejects(
    window.fetch('/api/v1/wizard/review?path=/tmp/other-owner'),
    /not yet enabled/);
  assert(!calls.some(c=>c.url.startsWith('/api/v1/')),
    'no legacy shared Engine request may reach network');
  assert.equal(calls.filter(c=>c.url.endsWith('/ensure')).length,0,
    'opening/reviewing existing Stage must not trigger duplicate Engine');
  console.log(JSON.stringify({
    private_original_jm_review:true,
    original_shot_thumbnail_owner_authenticated:true,
    original_hover_video_owner_authenticated:true,
    shot_replace_and_render_request_owner_scoped:true,
    unreviewed_paths_blocked:true,
    global_engine_media_not_exposed:true,
  }));
})().catch(e=>{console.error(e);process.exitCode=1});
