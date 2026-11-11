/* Real Owner adapter regression for Chema's native Audio and downloads. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const PROJECT='7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505';
const SID='c'.repeat(12);
const source=fs.readFileSync(path.resolve(__dirname,'../urano/owner_browser_bridge.js'),'utf8');
const network=[];
const audioInstances=[];
const downloads=[];
let clickHandler;
class NativeAudio {
  constructor(path){
    this.src=path||'';this.loaded=false;this.listeners={};
    audioInstances.push(this);
  }
  load(){this.loaded=true}
  dispatchEvent(e){this.dispatchedError=e?.type}
}
const doc={
  currentScript:{dataset:{ownerProject:PROJECT}},
  addEventListener(name,handler){if(name==='click')clickHandler=handler},
  createElement(name){return name==='a'
    ? {href:'',download:'',click(){downloads.push({href:this.href,filename:this.download})},
       remove(){}}
    : {setAttribute(){},hidden:false}},
  body:{append(){}}
};
const res=(code,body,ctype='application/json')=>({
  ok:code<400,status:code,
  headers:new Headers({'Content-Type':ctype,
    'Content-Length':String(body.length)}),
  async json(){return JSON.parse(body)},
  async blob(){return new Blob([body],{type:ctype})},
  body:new Response(body,{headers:{'Content-Type':ctype}}).body,
});
const fetcher=async(url,options={})=>{
  network.push({url,options});
  if(url==='/urano/v1/session/refresh')return res(200,JSON.stringify({csrf:'a'.repeat(64)}));
  if(String(url).endsWith('/ensure'))return res(200,JSON.stringify({
    project_id:PROJECT,generation:2,state:'ready'}));
  if(String(url).endsWith('/listen'))return res(200,'RIFFtiny-listening','audio/webm');
  if(String(url).endsWith('/results.zip'))return res(200,'ZIP-tiny','application/zip');
  return res(200,'MP3tiny','audio/mpeg');
};
const window={fetch:fetcher,Audio:NativeAudio,addEventListener(){},dispatchEvent(){}};
vm.runInNewContext(source,{
  window,document:doc,location:{origin:'https://montara.test',
    href:'https://montara.test/urano/v1/editor/projects/'+PROJECT+'/'},
  URL,Headers,Promise,Number,WeakMap,Object,Error,Blob,Response,Event,
  setTimeout(){},
},{filename:'owner_browser_bridge.js'});
async function flush(){await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
  const audio=new window.Audio('/montara/session/'+SID+'/listen');
  await flush();
  assert.ok(audio.loaded,'private audio should load after protected fetch');
  assert.ok(audio.src.startsWith('blob:'),'audio should use an object URL');
  assert.ok(network.some(x=>String(x.url).endsWith('/session/'+SID+'/listen')));
  assert.ok(!network.some(x=>String(x.url).startsWith('/montara/session/')));

  let prevented=false;
  const link={getAttribute:()=>'/montara/session/'+SID+'/results.zip'};
  await clickHandler({
    target:{closest:()=>link},
    preventDefault(){prevented=true}
  });
  assert.equal(prevented,true);
  assert.equal(downloads.length,1);
  assert.equal(downloads[0].filename,'Montara session.zip');
  assert.ok(downloads[0].href.startsWith('blob:'));
  assert.ok(network.some(x=>String(x.url).endsWith('/session/'+SID+'/results.zip')));

  const raw=new NativeAudio('other.mp3');
  assert.equal(raw.src,'other.mp3');
  console.log('PRIVATE_CHEMA_AUDIO_AND_DOWNLOAD_PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
