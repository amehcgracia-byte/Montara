/* Contract-level Cloudflare Worker test: native Chema media headers. */
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const src=fs.readFileSync(path.resolve(__dirname,'../infra/cloudflare/montara-owner-worker.mjs'),'utf8');
const js=src.replace('export const OWNER_HOST','const OWNER_HOST').replace('export default {','const __worker = {')+'\n;globalThis.workerToTest=__worker;';
const ctx={Request,Response,Headers,URL,console};
vm.runInNewContext(js,ctx,{filename:'montara-owner-worker.mjs'});
const origin='https://montara-owner.memoriainvalida001.workers.dev';
let captured;
const env={OWNER_PRIVATE_API:{fetch:async request=>{
  captured=request;
  return new Response(JSON.stringify({error:'Authentication required'}),{status:401,headers:{'content-type':'application/json'}});
}}};
(async ()=>{
  const req=new Request(origin+'/urano/v1/media/example/wizard/upload',{
    method:'POST',headers:{
      Origin:origin,'X-Zucker-Filename':'5._Second.mp3','Upload-Offset':'4096',
      'X-Montara-Engine-Generation':'2','X-Urano-CSRF':'f'.repeat(64),
      'X-Dont-Forward':'private','Content-Type':'application/octet-stream',
    },body:'synthetic-data'
  });
  const response=await ctx.workerToTest.fetch(req,env);
  assert.equal(response.status,401);
  assert.equal(new URL(captured.url).protocol,'http:');
  assert.equal(captured.headers.get('x-zucker-filename'),'5._Second.mp3');
  assert.equal(captured.headers.get('upload-offset'),'4096');
  assert.equal(captured.headers.get('x-montara-engine-generation'),'2');
  assert.equal(captured.headers.get('x-urano-csrf'),'f'.repeat(64));
  assert.equal(captured.headers.get('x-dont-forward'),null);
  assert.equal(await captured.text(),'synthetic-data');
  const forbidden=await ctx.workerToTest.fetch(new Request(origin+'/api/v1/wizard/upload'),env);
  assert.equal(forbidden.status,404);
  const evil=await ctx.workerToTest.fetch(new Request(origin+'/urano/v1/media/example/uploads',{method:'POST',headers:{Origin:'https://evil.invalid'},body:'test'}),env);
  assert.equal(evil.status,403);
  const part=await ctx.workerToTest.fetch(new Request(origin+'/urano/v1/media/example/uploads/'+ 'a'.repeat(32),{method:'PUT',headers:{Origin:origin,'Upload-Offset':'0'},body:'part'}),env);
  assert.equal(part.status,401);
  assert.equal(captured.headers.get('upload-offset'),'0');
  console.log('CLOUDFLARE_CHEMA_OWNER_MEDIA_HEADERS_PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
