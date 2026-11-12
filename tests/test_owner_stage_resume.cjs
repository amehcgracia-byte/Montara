/* Regression: reopening an Owner Stage is not a fresh project or a shared Engine route. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const PROJECT = '7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505';
const code = fs.readFileSync(path.resolve(__dirname, '../urano/owner_browser_bridge.js'), 'utf8');

async function exercise(query, expectedEnsure) {
  const calls = [];
  const mockFetch = async (url, opts={}) => {
    calls.push({url:String(url), opts});
    const headers = new Headers();
    if (String(url).startsWith('/urano/v1/media/'))
      headers.set('X-Montara-Engine-Generation', '7');
    return {
      ok:true, status:200, headers,
      json: async()=> String(url).endsWith('/session/refresh')
        ? {csrf:'a'.repeat(64)}
        : String(url).endsWith('/ensure')
          ? {project_id:PROJECT,state:'ready',generation:7}
          : {status:'waiting_review'}
    };
  };
  const window={fetch:mockFetch};
  const context={
    window, location:{
      origin:'https://montara.test',
      href:'https://montara.test/urano/v1/editor/projects/'+PROJECT+'/'+query,
    },
    document:{currentScript:{dataset:{ownerProject:PROJECT}}},
    URL,Headers,Promise,Number,WeakMap,Object,Error,
  };
  vm.runInNewContext(code,context);
  assert.equal(calls.length,0,'Opening the browser does not automatically open Engine');
  const result=await window.fetch('/api/v1/wizard/status?project_id=legacy-physical-path');
  assert.equal(result.status,200);
  assert.equal(calls.filter(x=>x.url.endsWith('/ensure')).length,expectedEnsure);
  assert(calls.some(x=>x.url==='/urano/v1/media/'+PROJECT+'/wizard/status?project_id=owner-worker'));
  assert(!calls.some(x=>x.url.startsWith('/api/v1/')));
  if (expectedEnsure) {
    const media=calls.find(x=>x.url.includes('/media/'));
    assert.equal(media.opts.headers.get('X-Montara-Engine-Generation'),'7');
  }
}
(async()=>{
  await exercise('?resume=footage',1);
  await exercise('?start=stage',0);
  await exercise('',0);
  console.log('OWNER_STAGE_RESUME_PASS: authorized worker on recovery only, legacy path stripped, normal navigation idle');
})().catch(error=>{console.error(error);process.exitCode=1});
