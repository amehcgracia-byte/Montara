/* Failure regression for Companion fragmented fetch through private Owner. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const project='7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505';
const source=fs.readFileSync(path.resolve(__dirname,'../urano/owner_browser_bridge.js'),'utf8');
const messages=[];
const footage={prepend:element=>messages.push(element)};
const document={
 currentScript:{dataset:{ownerProject:project}},
 getElementById:id=>id==='footage'?footage:null,
 querySelector:selector=>selector==='#footage'?footage:null,
 createElement:()=>({textContent:'',setAttribute(){},hidden:false}),
};
const headers=new Headers({'X-Montara-Engine-Generation':'3'});
const network=async url=>{
 if(url==='/urano/v1/session/refresh')
  return {ok:true,status:200,json:async()=>({csrf:'a'.repeat(64)})};
 if(String(url).endsWith('/ensure'))
  return {ok:true,status:200,json:async()=>({project_id:project,state:'ready',generation:3})};
 if(String(url).includes('/uploads/')){
  return {ok:false,status:413,headers,
   clone:()=>({json:async()=>({error:{message:'Proxy capacity exceeded'}})}),
   json:async()=>({error:{message:'Proxy capacity exceeded'}})};
 }
 return {ok:true,status:201,headers,json:async()=>({id:'b'.repeat(32)})};
};
const window={fetch:network};
vm.runInNewContext(source,{window,document,location:{
 origin:'https://montara.test',
 href:'https://montara.test/urano/v1/editor/projects/'+project+'/'
},URL,Headers,Promise,Number,WeakMap,Object,Error});
(async()=>{
 const result=await window.fetch('/montara/uploads/'+'b'.repeat(32),{
   method:'PUT',headers:{'Upload-Offset':'0','Content-Type':'application/octet-stream'},body:'test'});
 assert.equal(result.status,413);
 assert.equal(messages.length,1);
 assert.equal(messages[0].textContent,'Private proxy transfer rejected: Proxy capacity exceeded');
 console.log('PRIVATE_RESUMABLE_ERROR_VISIBLE_PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
