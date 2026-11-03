"""Original-quality rendering jobs; all filesystem access is resolved locally."""
import hashlib,json,os,re,signal,subprocess,threading,time,uuid
from pathlib import Path
from video_recipe import validate


class VideoJobs:
    def __init__(self,home):
        self.home=Path(home)/'video';self.jobs={};self.lock=threading.Lock();self.slot=threading.Semaphore(1)

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
        source_files={}
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
                    if path.stat().st_size!=original['size'] or hashlib.sha256(first+last).hexdigest()!=original['fingerprint']:raise ValueError('An original video changed. Add it again before exporting.')
            else:
                name=item.get('asset')
                if not isinstance(name,str) or not re.fullmatch(r'montara-render-source-[a-f0-9]{32}\.(mp4|mov|mkv|webm|mts)',name):raise ValueError('Invalid source asset')
                path=folder/name
            if not path or not Path(path).is_file() or Path(path).suffix.lower() not in {'.mp4','.mov','.m4v','.mts','.mkv','.avi','.webm'}:raise ValueError('An original video is unavailable. Reconnect its drive and retry.')
            source_files[key]=str(Path(path).resolve())
        branding=body.get('branding','none')
        if branding not in ('none','montara'):raise ValueError('Native export with a personal logo is not available yet')
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
            manifest={'recipe':recipe,'source_files':source_files,'master':str(master),'branding':branding,'work':str(work),'output':str(output),'progress':str(progress)}
            (work/'render.json').write_text(json.dumps(manifest))
            for key in [k for k,j in self.jobs.items() if j['status'] in ('ready','failed','cancelled')][:-30]:self.jobs.pop(key)
            self.jobs[token]={'status':'queued','progress':0,'path':output,'work':work,'snapshot':progress}
        threading.Thread(target=self._run,args=(token,),daemon=True).start()
        return token

    def _run(self,token):
        job=self.jobs[token]
        with self.slot:
            with self.lock:
                if job['status']=='cancelled':return
                job['status']='rendering'
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
            except Exception as exc:
                if job['status']!='cancelled':job.update(status='failed',error=str(exc)[:250])

    def cancel(self,token):
        job=self.jobs.get(token)
        if not job:return False
        with self.lock:
            if job['status'] in ('ready','failed','cancelled'):return True
            job['status']='cancelled'
            process=job.get('process')
        if process and process.poll() is None:
            # Kill only this worker's descendants, even when FFmpeg starts a
            # separate process group for its watchdog. Never match by name.
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
        return True

    def status(self,token):
        job=self.jobs.get(token)
        if not job:return None
        result={k:job[k] for k in ('status','progress','error') if k in job}
        if job['status']=='rendering':
            try:
                snap=json.loads(job['snapshot'].read_text())
                result.update(progress=min(.99,float(snap.get('progress') or 0)),message=str(snap.get('message') or '')[:200])
            except (OSError,ValueError,TypeError):pass
        return result

    def output(self,token):
        job=self.jobs.get(token)
        return job['path'] if job and job['status']=='ready' else None
