import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
const overlay=JSON.parse(readFileSync(new URL('./overlay.json',import.meta.url),'utf8'));
if(overlay.assetChunks)overlay.assets=JSON.parse(overlay.assetChunks.map(p=>readFileSync(new URL('./'+p,import.meta.url),'utf8')).join(''));
import {Sandbox as SandboxAPI,Drive as DriveAPI} from '@vercel/sandbox';
export const TEMPLATE='snap_652m5JKH6A8aqrBChFowzoeIgZki';
const inflight=new Map();
export async function openPreview(id,services){
  if(inflight.has(id))return inflight.get(id);
  const task=prepare(id,services);inflight.set(id,task);
  try{return await task;}finally{inflight.delete(id);}
}
async function prepare(id,{Sandbox=SandboxAPI,Drive=DriveAPI}={}){
  if(!/^[a-f0-9]{32}$/.test(id))throw new Error('Invalid session');
  const name='montara-demo-'+id;
  const known=await (await Sandbox.list({tags:{application:'montara-demo'},limit:50})).toArray();
  let previous=known.find(s=>s.name===name);
  const active=known.filter(s=>['pending','running','stopping','snapshotting'].includes(s.status));
  if(!active.some(s=>s.name===name)&&active.length>=4)throw new Error('PREVIEW_BUSY: Hay cuatro pruebas abiertas ahora. Vuelve a intentarlo cuando termine una sesión.');
  const legacy=previous?.persistent===true;
  let importDrive;
  if(!legacy){
    try{importDrive=await Drive.get({name:'montara-data-'+id});}
    catch(error){
      const status=error.status??error.statusCode??error.response?.status;
      if(status!==404&&!/\b404\b/.test(error.message||''))throw error;
      if(previous)throw new Error('The saved preview disk is unavailable. Existing work has not been replaced.');
    }
  }
  const boot=async s=>{
    const storage=await s.runCommand({cmd:'/vercel/sandbox/venv/bin/python',args:['-c',overlay.files['deploy/preview_storage.py']+`
prepare_storage(Path('/vercel/sandbox/data'), initialize=${legacy?'False':'True'}, import_root=${importDrive?"Path('/vercel/sandbox/import-data')":'None'})`]});
    if(storage.exitCode!==0)throw new Error('Could not prepare the preview working disk; saved data was kept.');
    const ping=await s.runCommand('curl',['-s','-o','/dev/null','-w','%{http_code}','http://127.0.0.1:8080/montara/version']);
    const serving=(await ping.stdout()).trim()==='401';
    const installed=await s.readFileToBuffer({path:'/vercel/sandbox/montara/.preview-build'});
    if(serving&&installed?.toString()===overlay.revision)return;
    if(serving){
      // Leave active jobs on their current worker; apply the update on the next opening.
      const check=await s.runCommand({cmd:'/vercel/sandbox/venv/bin/python',args:['-c',`import json,urllib.request,subprocess;from pathlib import Path
r=urllib.request.Request('http://127.0.0.1:8080/api/v1/wizard/status',headers={'Cookie':'montara_preview=${id}'})
state=json.load(urllib.request.urlopen(r))
busy=state.get('status') in {'running','mixing','rendering','analyzing'}
for p in Path('/vercel/sandbox/data').rglob('pack.json'):
 d=json.loads(p.read_text());busy=busy or d.get('status')=='preparing' or d.get('captions_status')=='running' or any(r.get('lyrics_status')=='running' or r.get('alignment_status')=='running' or r.get('render',{}).get('status') in {'running','queued'} for r in d.get('reels',[]))
busy=busy or subprocess.run(['pgrep','-x','ffmpeg'],stdout=subprocess.DEVNULL).returncode==0
print('busy' if busy else 'idle')`]});
      if(check.exitCode!==0||(await check.stdout()).trim()!=='idle')return;
    }
    const downloads=await s.runCommand({cmd:'/vercel/sandbox/venv/bin/python',args:['-c',overlay.files['deploy/download_runtime.py']],env:{DENO_NO_UPDATE_CHECK:'1'}});
    if(downloads.exitCode!==0)throw new Error('Could not prepare the video import runtime. Retry opening Montara.');
    if(installed?.toString()!==overlay.revision){await s.writeFiles(Object.entries(overlay.files).map(([path,content])=>({path:'/vercel/sandbox/montara/'+path,content:Buffer.from(content)})));
      const checkAssets=await s.runCommand({cmd:'/vercel/sandbox/venv/bin/python',args:['-c','import hashlib,json;from pathlib import Path; print(json.dumps({str(p.relative_to(Path("/vercel/sandbox/montara"))):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path("/vercel/sandbox/montara/tests/fixtures").rglob("*") if p.is_file()}))']});
      const existing=JSON.parse((await checkAssets.stdout()).trim()||'{}');
      let assetBatch=[],assetBytes=0;for(const [path,content] of Object.entries(overlay.assets||{})){const data=Buffer.from(content,'base64');if(existing[path]===createHash('sha256').update(data).digest('hex'))continue;if(assetBatch.length&&(assetBytes+data.length>768*1024||assetBatch.length>=12)){await s.writeFiles(assetBatch);assetBatch=[];assetBytes=0;}assetBatch.push({path:'/vercel/sandbox/montara/'+path,content:data});assetBytes+=data.length;}if(assetBatch.length)await s.writeFiles(assetBatch);
      await s.writeFiles([{path:'/vercel/sandbox/montara/.preview-build',content:Buffer.from(overlay.revision)}]);}
    if(serving){const reload=await s.runCommand({cmd:'pkill',args:['-HUP','-o','-f','gunicorn.*deploy.sandbox_entry:app']});if(reload.exitCode!==0)throw new Error('Could not reload the preview worker.');return;}
    await s.runCommand({cmd:'/vercel/sandbox/venv/bin/gunicorn',args:['--bind','0.0.0.0:8080','--workers','1','--threads','8','--timeout','1800','--access-logfile','/tmp/montara-access.log','--error-logfile','/tmp/montara-error.log','deploy.sandbox_entry:app'],cwd:'/vercel/sandbox/montara',env:{MONTARA_SESSION_TOKEN:id,OMP_NUM_THREADS:'2',OPENBLAS_NUM_THREADS:'2',MONTARA_WHISPER_MODEL:'small',MONTARA_WHISPER_THREADS:'2',MONTARA_SHARED_MODELS:'1',HF_HUB_CACHE:'/models/hub'},detached:true});
    for(let attempt=0;attempt<40;attempt++){
      const ready=await s.runCommand('curl',['-s','-o','/dev/null','-w','%{http_code}','http://127.0.0.1:8080/montara/version']);
      if((await ready.stdout()).trim()==='401')return;
      await new Promise(r=>setTimeout(r,250));
    }
    throw new Error('The preview could not start. Please retry.');
  };
  const models=await Drive.get({name:'montara-lyric-models'});
  const mounts={'/models':models.snapshot()};
  // A complete render needs more than the 1 GiB visitor Drive. Keep data on
  // the large private working disk and persist it with the sandbox snapshot.
  // Existing Drives are retained and mounted read-only for a one-time copy.
  if(importDrive)mounts['/vercel/sandbox/import-data']=importDrive.snapshot();
  if(previous&&!legacy){
    const retired=await Sandbox.get({name});
    if(previous.status==='running'){
      const check=await retired.runCommand({cmd:'/vercel/sandbox/venv/bin/python',args:['-c',`import json,urllib.request,subprocess;from pathlib import Path
r=urllib.request.Request('http://127.0.0.1:8080/api/v1/wizard/status',headers={'Cookie':'montara_preview=${id}'})
state=json.load(urllib.request.urlopen(r))
busy=state.get('status') in {'running','mixing','rendering','analyzing'}
for p in Path('/vercel/sandbox/data').rglob('pack.json'):
 d=json.loads(p.read_text());busy=busy or d.get('status')=='preparing' or d.get('captions_status')=='running' or any(r.get('lyrics_status')=='running' or r.get('alignment_status')=='running' or r.get('render',{}).get('status') in {'running','queued'} for r in d.get('reels',[]))
busy=busy or subprocess.run(['pgrep','-x','ffmpeg'],stdout=subprocess.DEVNULL).returncode==0
print('busy' if busy else 'idle')`]});
      if(check.exitCode!==0||(await check.stdout()).trim()!=='idle')return {url:retired.domain(8080)+'/_preview/grant?token='+id,name};
      await retired.stop();
    }else if(previous.status!=='stopped')throw new Error('PREVIEW_BUSY: Tu espacio está guardándose. Vuelve a abrirlo en unos instantes.');
    await retired.delete();
  }
  if(previous?.status==='stopped'&&legacy){const stopped=await Sandbox.get({name});await stopped.update({resources:{vcpus:2},mounts});}
  const s=await Sandbox.getOrCreate({name,source:{type:'snapshot',snapshotId:TEMPLATE},ports:[8080],resources:{vcpus:2},mounts,timeout:45*60*1000,persistent:true,snapshotExpiration:7*86400000,keepLastSnapshots:{count:1,expiration:7*86400000},tags:{application:'montara-demo'},networkPolicy:{allow:{'*':[]},subnets:{deny:['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16']}},onCreate:boot,onResume:boot,resume:true});
  await boot(s);
  return {url:s.domain(8080)+'/_preview/grant?token='+id,name};
}
