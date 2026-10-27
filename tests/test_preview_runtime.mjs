import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {openPreview} from '../deployment/vercel/runtime.js';
const revision=JSON.parse(readFileSync(new URL('../deployment/vercel/overlay.json',import.meta.url))).revision;
function setup(previous, {busy=false, hasDrive=false}={}){
  const calls=[];
  const worker={
    runCommand:async(cmd,args)=>{
      const argv=typeof cmd==='string'?args:cmd.args;
      calls.push(['command',argv]);
      const output=argv?.includes('-w')?'401':argv?.some(a=>a.includes("print('busy'"))?(busy?'busy':'idle'):'';
      return {exitCode:0,stdout:async()=>output};
    },
    readFileToBuffer:async()=>Buffer.from(revision),
    domain:()=> 'https://example.vercel.run',
    stop:async()=>calls.push(['stop']),delete:async()=>calls.push(['delete']),
    update:async()=>calls.push(['update'])
  };
  const Sandbox={list:async()=>({toArray:async()=>previous?[previous]:[]}),get:async()=>worker,
    getOrCreate:async options=>{calls.push(['create',options]);await options.onCreate(worker);return worker;}};
  const Drive={get:async({name})=>{
    calls.push(['drive',name]);
    if(name==='montara-lyric-models'||hasDrive)return {snapshot:()=>({drive:name,mode:'snapshot'})};
    throw Object.assign(new Error('Drive not found'),{status:404});
  },getOrCreate:async()=>{throw new Error('Must not reserve a visitor Drive');}};
  return {calls,services:{Sandbox,Drive}};
}
test('new visitor uses large snapshot-backed working disk without reserving Drive quota',async()=>{
  const x=setup();await openPreview('0'.repeat(32),x.services);
  const options=x.calls.find(c=>c[0]==='create')[1];
  assert.equal(options.persistent,true);
  assert.deepEqual(Object.keys(options.mounts),['/models']);
  assert(x.calls.some(c=>c[0]==='command'&&c[1].some(a=>a.includes('initialize=True'))));
});
test('stopped small-Drive preview retains old disk as read-only migration source',async()=>{
  const x=setup({name:'montara-demo-'+'1'.repeat(32),status:'stopped',persistent:false},{hasDrive:true});
  await openPreview('1'.repeat(32),x.services);
  const options=x.calls.find(c=>c[0]==='create')[1];
  assert.equal(options.mounts['/vercel/sandbox/import-data'].mode,'snapshot');
  assert(!options.mounts['/vercel/sandbox/data']);
  assert(x.calls.findIndex(c=>c[0]==='delete')<x.calls.findIndex(c=>c[0]==='create'));
});
test('busy existing preview keeps serving without stop, migration or replacement',async()=>{
  const x=setup({name:'montara-demo-'+'2'.repeat(32),status:'running',persistent:false},{hasDrive:true,busy:true});
  const result=await openPreview('2'.repeat(32),x.services);
  assert(result.url.startsWith('https://example.vercel.run/'));
  assert(!x.calls.some(c=>['stop','delete','create'].includes(c[0])));
});
test('existing snapshot preview preserves its data and does not need a visitor Drive',async()=>{
  const x=setup({name:'montara-demo-'+'3'.repeat(32),status:'running',persistent:true});
  await openPreview('3'.repeat(32),x.services);
  assert.equal(x.calls.filter(c=>c[0]==='drive').length,1);
  assert(x.calls.some(c=>c[0]==='command'&&c[1].some(a=>a.includes('initialize=False'))));
});
