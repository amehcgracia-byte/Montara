"""Original-quality rendering jobs; all filesystem access is resolved locally."""
import hashlib,json,os,re,signal,subprocess,threading,time,uuid
from pathlib import Path
from video_recipe import validate


def stop_process_tree(process):
    """Stop this worker and its FFmpeg descendants, including separate groups."""
    if process.poll() is not None:return
    rows=subprocess.check_output(['ps','-Ao','pid=,ppid='],text=True).splitlines()
    children={}
    for line in rows:
        pid,parent=map(int,line.split());children.setdefault(parent,[]).append(pid)
    tree=[]
    def collect(pid):
        for child in children.get(pid,[]):collect(child)
        tree.append(pid)
    collect(process.pid)
    for pid in tree:
        try:os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:pass
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:pass
    # Children can ignore TERM even after their parent has exited.
    for pid in tree:
        try:os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass
    process.wait(timeout=5)


class VideoJobs:
    def __init__(self,home):
        self.home=Path(home)/'video';self.jobs={};self.lock=threading.Lock();self.slot=threading.Semaphore(1)
        try:
            saved=json.loads((self.home/'completed-jobs.json').read_text())
            if not isinstance(saved,dict):saved={}
            for token,row in saved.items():
                if not re.fullmatch('[a-f0-9]{32}',token) or not isinstance(row,dict):continue
                path=Path(row['path'])
                if path.is_file() and path.stat().st_size>0:
                    self.jobs[token]={'status':'ready','progress':1.,'path':path,'work':Path(row['work']),
                                      'snapshot':Path(row['snapshot']),'download_name':row['download_name'],'diagnostics':row.get('diagnostics',[])}
        except (OSError,ValueError,KeyError,TypeError):pass

    def _save_completed(self):
        rows={token:{k:str(job[k]) for k in ('path','work','snapshot','download_name')}
              for token,job in self.jobs.items() if job['status']=='ready'}
        for token,row in rows.items():row['diagnostics']=self.jobs[token].get('diagnostics',[])
        self.home.mkdir(parents=True,exist_ok=True)
        temporary=self.home/'completed-jobs.tmp'
        temporary.write_text(json.dumps(dict(list(rows.items())[-30:])))
        temporary.replace(self.home/'completed-jobs.json')

    def runtime(self):
        python=self.home/'venv/bin/python';marker=self.home/'ENGINE_COMMIT'
        if (self.home/'INSTALLING').exists():return None
        if not python.is_file() or not marker.is_file() or not (self.home/'local_video.py').is_file():return None
        sha=marker.read_text().strip()
        return {'engine':sha} if re.fullmatch('[a-f0-9]{40}',sha) else None

    def start(self,body,projects,find_original):
        runtime=self.runtime()
        if not runtime:raise ValueError('Install the companion video renderer before exporting originals')
        recipe=validate(body.get('recipe'))
        if recipe['engine']!=runtime['engine']:raise ValueError('Update the companion to the editor version on this page')
        folder=projects.get(body.get('project'))
        if folder is None or not folder.is_dir():raise ValueError('Choose the project folder on this computer')
        master=body.get('master')
        if not isinstance(master,str) or not re.fullmatch(r'montara-render-audio-[a-f0-9]{32}\.audio',master):raise ValueError('Choose the exported master')
        master=folder/master
        if not master.is_file() or not 0<master.stat().st_size<=1024**3:raise ValueError('Send the master audio before rendering')
        mapping=body.get('originals')
        if not isinstance(mapping,list) or len(mapping)!=len(recipe['sources']):raise ValueError('Locate every original video')
        source_files={};verified={}
        for item in mapping:
            key=item.get('source') if isinstance(item,dict) else None
            if isinstance(key,bool) or not isinstance(key,int) or key in source_files or key not in [s['key'] for s in recipe['sources']]:raise ValueError('Invalid original source mapping')
            if item.get('original'):
                # Companion validates name, size and edge fingerprint before lookup.
                original=item['original']
                if not isinstance(original,dict) or not isinstance(original.get('name'),str) or '/' in original['name'] or '\\' in original['name'] or not isinstance(original.get('size'),int) or isinstance(original['size'],bool) or not isinstance(original.get('fingerprint'),str) or not re.fullmatch('[a-f0-9]{64}',original['fingerprint']):raise ValueError('Invalid original identity')
                path=find_original(original)
                if path:
                    path=Path(path)
                    with path.open('rb') as handle:
                        first=handle.read(65536);handle.seek(max(0,path.stat().st_size-65536));last=handle.read(65536)
                    if path.stat().st_size!=original['size'] or hashlib.sha256(first+last).hexdigest()!=original['fingerprint']:raise ValueError('Source '+str(key)+' · '+original['name']+': original changed. Reconnect it before exporting.')
            else:
                name=item.get('asset')
                if not isinstance(name,str) or not re.fullmatch(r'montara-render-source-[a-f0-9]{32}\.(mp4|mov|mkv|webm|mts)',name):raise ValueError('Invalid source asset')
                path=folder/name
            if not path or not Path(path).is_file() or Path(path).suffix.lower() not in {'.mp4','.mov','.m4v','.mts','.mkv','.avi','.webm'}:raise ValueError('Source '+str(key)+' · '+str((item.get('original') or {}).get('name') or item.get('asset') or 'video')+': original unavailable. Reconnect its drive and retry.')
            source_files[key]=str(Path(path).resolve())
            if item.get('original'):verified[key]=item['original']
        branding=body.get('branding','none')
        if branding not in ('none','montara','mine'):raise ValueError('Choose a logo option')
        personal_logo=None
        if branding=='mine':
            name=body.get('logo')
            if not isinstance(name,str) or not re.fullmatch(r'montara-render-logo-[a-f0-9]{32}\.png',name):raise ValueError('Send your logo before rendering')
            logo=folder/name
            if logo.is_symlink() or not logo.is_file() or not 0<logo.stat().st_size<=10*1024*1024:raise ValueError('The logo is unavailable')
            import struct
            with logo.open('rb') as handle:header=handle.read(24)
            if len(header)!=24 or header[:8]!=b'\x89PNG\r\n\x1a\n' or header[12:16]!=b'IHDR':raise ValueError('Choose a PNG logo')
            width,height=struct.unpack('>II',header[16:24])
            if not 1<=width<=1600 or not 1<=height<=1600:raise ValueError('Resize your logo before rendering')
            personal_logo=str(logo.resolve())
        with self.lock:
            if sum(j['status'] in ('queued','rendering') for j in self.jobs.values())>=2:raise ValueError('Wait for the current video export')
            token=uuid.uuid4().hex;work=folder/'.montara-renders'/token;work.mkdir(parents=True)
            # Reserve queued outputs too: two exports may request the same name.
            name=re.sub(r'[^\w .()-]','-',str(body.get('name') or 'Montara video'))[:70].strip(' .') or 'Montara video'
            output=folder/(name+'.mp4');suffix=2
            reserved={j['path'] for j in self.jobs.values()}
            while output.exists() or output in reserved:
                output=folder/(name+f' ({suffix}).mp4');suffix+=1
            progress=work/'progress.json'
            manifest={'verified_originals':verified,'personal_logo':personal_logo,'recipe':recipe,'source_files':source_files,'master':str(master),'branding':branding,'work':str(work),'output':str(output),'progress':str(progress)}
            (work/'render.json').write_text(json.dumps(manifest))
            for key in [k for k,j in self.jobs.items() if j['status'] in ('ready','failed','cancelled')][:-30]:self.jobs.pop(key)
            self.jobs[token]={'diagnostics':recipe.get('diagnostics',[]),'status':'queued','progress':0,'path':output,'work':work,'snapshot':progress,'download_name':name+'.mp4',
                              'tasks':[{'id':f'segment-{i+1}','label':f'Shot {i+1}/{len(recipe["segments"])}','percent':0} for i in range(len(recipe['segments']))]}
        threading.Thread(target=self._run,args=(token,),daemon=True).start()
        return token

    def _run(self,token):
        job=self.jobs[token]
        with self.slot:
            with self.lock:
                if job['status']=='cancelled':return
                job['status']='rendering'
                job['started_monotonic']=time.monotonic()
            try:
                with (job['work']/'render.log').open('wb') as log:
                    with self.lock:
                        if job['status']=='cancelled':return
                        process=subprocess.Popen([str(self.home/'venv/bin/python'),str(self.home/'local_video.py'),str(job['work']/'render.json')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                        job['process']=process
                    try:code=process.wait(timeout=21600)
                    except subprocess.TimeoutExpired:
                        self.cancel(token);raise RuntimeError('The video render exceeded its time limit')
                job.pop('process',None)
                with self.lock:
                    if job['status']=='cancelled':return
                    if code or not job['path'].is_file():raise RuntimeError('The original-quality render failed. The diagnostic is saved in the project folder.')
                    job.update(status='ready',progress=1.)
                    try:self._save_completed()
                    except OSError:pass  # The finished video stays downloadable if the index cannot be written.
            except Exception as exc:
                if job['status']!='cancelled':job.update(status='failed',error=str(exc)[:250])

    def cancel(self,token):
        job=self.jobs.get(token)
        if not job:return False
        with self.lock:
            if job['status'] in ('ready','failed'):return True
            job['status']='cancelled'
            process=job.get('process')
        if process and process.poll() is None:
            stop_process_tree(process)
        return True

    def status(self,token):
        job=self.jobs.get(token)
        if not job:return None
        result={k:job[k] for k in ('status','progress','error','tasks','diagnostics') if k in job}
        if job['status']=='rendering' and 'started_monotonic' in job:
            result['elapsed_sec']=round(max(0.,time.monotonic()-job['started_monotonic']),1)
        if job['status']=='rendering':
            try:
                snap=json.loads(job['snapshot'].read_text())
                result.update(progress=min(.99,float(snap.get('progress') or 0)),message=str(snap.get('message') or '')[:200])
                if isinstance(snap.get('tasks'),list):result['tasks']=snap['tasks']
            except (OSError,ValueError,TypeError):pass
        return result

    def output(self,token):
        job=self.jobs.get(token)
        return job['path'] if job and job['status']=='ready' else None
