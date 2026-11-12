/* Recovery errors must not masquerade as a disconnected Chema server. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const PROJECT='7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505';
const code=fs.readFileSync(path.resolve(__dirname,'../urano/owner_browser_bridge.js'),'utf8');

async function scenario(admissionStatus) {
  const calls=[];
  const fetch=async (url,options={})=>{
    calls.push(String(url));
    if(String(url).endsWith('/session/refresh'))
      return {ok:true,status:200,json:async()=>({csrf:'a'.repeat(64)})};
    if(String(url).endsWith('/ensure'))
      return admissionStatus===200
        ? {ok:true,status:200,json:async()=>({project_id:PROJECT,state:'ready',generation:3})}
        : {ok:false,status:admissionStatus,json:async()=>({error:'Engine already busy'})};
    throw Error('Gateway must not be called after failed admission');
  };
  const window={fetch}, context={
    window,
    document:{currentScript:{dataset:{ownerProject:PROJECT}}},
    location:{origin:'https://montara.test',href:'https://montara.test/urano/v1/editor/projects/'+PROJECT+'/?resume=footage'},
    URL,Headers,Response,Promise,Number,WeakMap,Object,Error,
  };
  vm.runInNewContext(code,context);
  if(admissionStatus!==200) {
    const response=await window.fetch('/api/v1/wizard/status');
    assert.equal(response.status,admissionStatus);
    const body=await response.json();
    assert.equal(body.error.code,'OWNER_STAGE_RECOVERY');
    assert.match(body.error.message,admissionStatus===409?/otro proyecto abierto/:/Engine privado/);
    assert.equal(calls.filter(p=>p.includes('/ensure')).length,1);
    assert(!calls.some(p=>p.includes('/media/')));
  }
}
(async()=>{await scenario(409);await scenario(503);console.log('OWNER_RECOVERY_ERRORS_PASS no false network failure or unintended media call')})()
  .catch(e=>{console.error(e);process.exitCode=1});
