"""A small licensed music shelf; all engine changes use its HTTP API."""
from __future__ import annotations
import hashlib, io, json, math, threading, tempfile
from urllib.parse import urlsplit, quote
from pathlib import Path
from flask import jsonify, request, Response
from preview_api import engine_client


def fetch_library_track(item, target):
    """Download only a reviewed filename from the official catalogue, never a supplied URL."""
    import requests
    name=item['source_file']
    if '/' in name or '\\' in name or not name.endswith('.mp3'):raise ValueError('Invalid library track.')
    url='https://incompetech.com/music/royalty-free/mp3-royaltyfree/'+quote(name)
    total=0
    with requests.get(url,stream=True,timeout=(10,45),allow_redirects=False) as response:
        if response.status_code!=200:raise ValueError('The music catalogue is temporarily unavailable. Try again later.')
        with Path(target).open('wb') as out:
            for chunk in response.iter_content(65536):
                total+=len(chunk)
                if total>50*1024*1024:raise ValueError('This music file is too large.')
                out.write(chunk)
    return target


def register_music_shelf(app, data_root: Path, bundled: Path):
    root = data_root / 'MusicShelf'
    lock = threading.RLock()
    online = {"status":"empty"}
    library_job = {"status":"empty"}
    def pool():
        path=bundled/"more.json"
        return json.loads(path.read_text()) if path.is_file() else []
    def read():
        p=root/'catalog.json'
        return json.loads(p.read_text()) if p.is_file() else {}
    def save(doc):
        root.mkdir(parents=True,exist_ok=True)
        p=root/'catalog.tmp';p.write_text(json.dumps(doc,ensure_ascii=False,indent=2));p.replace(root/'catalog.json')
    def fail(message,code=400):return jsonify(error={'message':message}),code
    def proxy(response):
        return Response(response.data,status=response.status_code,content_type=response.content_type)
    def seed(engine):
        doc=read();manifest=bundled/'catalog.json'
        for item in json.loads(manifest.read_text()) if manifest.is_file() else []:
            existing=next((id for id,r in doc.items() if r.get('bundled_id')==item['id']),None)
            if existing:
                doc[existing]={**doc[existing],**item,'bundled_id':item['id'],'id':existing}
                continue
            source=bundled/item['file']
            if not source.is_file():continue
            with source.open('rb') as stream:
                response=engine.post('/api/v1/music/import',data={'file':(stream,item['title']+'.mp3')},content_type='multipart/form-data')
            if response.status_code!=201:raise ValueError('Could not prepare the bundled music. Try again.')
            track=response.get_json();doc[track['id']]={**item,'bundled_id':item['id'],'id':track['id']}
        save(doc)
    @app.get('/montara/music')
    def montara_music_catalog():
        try:
            with lock, engine_client(app) as engine:
                seed(engine);response=engine.get('/api/v1/music/library')
                if response.status_code!=200:return proxy(response)
                meta=read();items=[]
                tracks=response.get_json()['items']
                # Retire only the former demo choices; project-owned copies stay intact.
                if not (root/'.curated-029').exists():
                    for t in tracks:
                        if 'allminds' in ''.join(c for c in t['name'].lower() if c.isalnum()) and not meta.get(t['id'],{}).get('bundled_id'):
                            meta.setdefault(t['id'],{})['hidden']=True
                    save(meta);(root/'.curated-029').touch()
                for track in tracks:
                    m=meta.get(track['id'],{})
                    if m.get('hidden') or m.get('bundled_id')=='our-expanse':continue
                    items.append({'id':track['id'],'name':m.get('title') or track['name'],'artist':m.get('artist','Your music'),
                                  'mood':m.get('mood','Own music'),'category':m.get('category','Your music'),'license':m.get('license','User supplied — check permission'),
                                  'page':m.get('page',''),'duration':track.get('duration',0),'url':'/montara/music/file/'+track['id']})
                order={r['id']:i for i,r in enumerate(json.loads((bundled/'catalog.json').read_text()))}
                items.sort(key=lambda t:({'Tension':0,'Horror':1,'Emotional piano':2,'Creator classics':3,'Retro':4}.get(t['category'],2),order.get(meta.get(t['id'],{}).get('bundled_id'),999),t['name'].casefold()))
                known={m.get('bundled_id') for m in meta.values()}
                return jsonify(items=items,more_available=sum(t['id'] not in known for t in pool()),library_total=len(order)+len(pool()))
        except (ValueError,OSError):
            app.logger.exception('Music shelf unavailable')
            return fail('Could not load the music library. Try again.',503)
    @app.get('/montara/music/file/<track_id>')
    def montara_music_file(track_id):
        if len(track_id)!=64 or any(c not in '0123456789abcdef' for c in track_id):return '',404
        with engine_client(app) as engine:
            response=engine.get('/api/v1/music/file/'+track_id,headers={'Range':request.headers.get('Range','')})
            result=proxy(response)
            for key in ['Accept-Ranges','Content-Range','Content-Length']:
                if key in response.headers:result.headers[key]=response.headers[key]
            return result
    @app.post('/montara/music/import')
    def montara_music_upload():
        f=request.files.get('file')
        if f is None:return fail('Choose an audio file.')
        with lock,engine_client(app) as engine:
            response=engine.post('/api/v1/music/import',data={'file':(f.stream,f.filename)},content_type='multipart/form-data')
            if response.status_code==201:
                doc=read();entry=doc.get(response.get_json()['id'])
                if entry and entry.get('hidden'):
                    entry.pop('hidden',None);save(doc)
            return proxy(response)
    @app.get('/montara/music/link')
    def montara_music_link_status():
        with lock:return jsonify(dict(online))
    @app.post('/montara/music/link')
    def montara_music_link_import():
        from reference_import import reference_url, import_reference
        body=request.get_json(silent=True) or {}
        try:
            url=str(body.get('url') or '').strip()
            host=(urlsplit(url).hostname or '').lower()
            if host not in {'youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be'}:
                raise ValueError('Use a public YouTube link, or upload an audio file.')
            url=reference_url(url)
        except ValueError as exc:return fail(str(exc))
        with lock:
            if online['status']=='importing':return fail('A music link is already being prepared.',409)
            online.clear();online.update(status='importing')
        def worker():
            try:
                root.mkdir(parents=True,exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='online-',dir=root) as folder:
                    target,title=import_reference(url,Path(folder))
                    with lock,engine_client(app) as engine,target.open('rb') as audio:
                        response=engine.post('/api/v1/music/import',data={'file':(audio,title+'.wav')},content_type='multipart/form-data')
                        if response.status_code!=201:raise ValueError('Could not add this music. Try an audio file.')
                        track=response.get_json();doc=read()
                        # Importing a URL never grants rights, nor replaces verified bundled attribution.
                        if track['id'] not in doc:
                            doc[track['id']]={'title':title,'artist':'User supplied','mood':'Online music','license':'Check permission','page':url}
                            save(doc)
                        online.clear();online.update(status='ready',id=track['id'],title=title)
            except Exception as exc:
                app.logger.exception('Online music import failed')
                with lock:
                    online.clear();online.update(status='failed',message=str(exc) if isinstance(exc,ValueError) else 'Could not retrieve this music. Try an audio file.')
        threading.Thread(target=worker,daemon=True).start()
        return jsonify(status='importing'),202
    @app.post('/montara/music/place/<track_id>')
    def montara_music_place(track_id):
        body=request.get_json(silent=True) or {}
        try:
            volume=float(body.get('volume',.28));start=float(body.get('start',0))
            if not math.isfinite(volume+start) or not 0<=volume<=1 or start<0:raise ValueError()
            if not isinstance(body.get('under_voice',True),bool):raise ValueError()
        except (ValueError,TypeError):return fail('Choose a valid music level and start point.')
        with lock,engine_client(app) as engine:
            tracks=engine.get('/api/v1/music/library').get_json().get('items',[])
            track=next((r for r in tracks if r['id']==track_id),None)
            if track is None:return fail('Choose music from this library.',404)
            if start>=float(track.get('duration') or 0):return fail('Choose a start point inside the music.')
            try:duration=min(float(body.get('duration',10)),float(track['duration'])-start)
            except (ValueError,TypeError):return fail('Choose a valid duration.')
            if not math.isfinite(duration) or duration<.1:return fail('Choose a valid duration.')
            response=engine.post('/api/v1/music/place/'+track_id,json={**body,'duration':duration})
            if response.status_code!=201:return proxy(response)
            result=response.get_json();proposal=result['proposal'];pid=proposal['id']
            # Source position and volume use the same APIs as the existing effect inspector.
            edit=engine.patch('/api/v1/show/review/'+pid,json={'start':start})
            if edit.status_code!=200:return proxy(edit)
            edit=engine.patch('/api/v1/show/audio/tracks/'+pid,json={'project_id':body.get('project_id'),'volume':volume,'mode':'mix','under_voice':body.get('under_voice',True)})
            if edit.status_code!=200:return proxy(edit)
            result['proposal']=edit.get_json();m=read().get(track_id,{})
            key=hashlib.sha256(str(body.get('project_id','')).encode()).hexdigest();path=root/(key+'-credits.json')
            credits=json.loads(path.read_text()) if path.is_file() else {}
            credits[track_id]={'name':m.get('title') or track['name'],'artist':m.get('artist','User supplied'),'license':m.get('license','Check permission'),'page':m.get('page',''),'license_url':m.get('license_url','')}
            root.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(credits,ensure_ascii=False,indent=2))
            return jsonify(result),201
    @app.get('/montara/music/credits')
    def montara_music_credits():
        project=request.args.get('project_id','');key=hashlib.sha256(project.encode()).hexdigest();p=root/(key+'-credits.json')
        ledger=json.loads(p.read_text()) if p.is_file() else {}
        with engine_client(app) as engine:
            response=engine.get('/api/v1/show/scenes')
            doc=response.get_json() if response.status_code==200 else {}
        referenced={id for scene in doc.get('scenes',[]) for id in scene.get('effects',[])}
        active={Path(r.get('params',{}).get('path','')).stem for r in doc.get('proposals',[]) if r.get('id') in referenced and r.get('status')=='approved'}
        items=[r for id,r in ledger.items() if id in active]
        required=[r for r in items if r.get('license')=='CC BY 4.0']
        text='\n\n'.join(f"{r['name']} — {r['artist']}\nLicensed under Creative Commons Attribution 4.0\n{r['page']}\n{r['license_url']}\nExcerpted and mixed with narration in Montara." for r in required)
        if request.args.get('format')=='json':return jsonify(items=items,required=len(required),text=text)
        return Response(text or 'No attribution-required library music is currently used in this project.',mimetype='text/plain',headers={'Content-Disposition':'attachment; filename="music-attribution.txt"'})
    @app.get('/montara/music/more')
    def montara_more_music_status():
        with lock:return jsonify(dict(library_job))
    @app.post('/montara/music/more')
    def montara_more_music():
        with lock:
            if library_job['status']=='importing':return fail('More music is already being prepared.',409)
            known={r.get('bundled_id') for r in read().values()}
            choices=[t for t in pool() if t['id'] not in known][:3]
            if not choices:return jsonify(status='ready',added=0)
            library_job.clear();library_job.update(status='importing',added=0)
        def worker():
            added=0
            try:
                root.mkdir(parents=True,exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='catalogue-',dir=root) as directory:
                    for item in choices:
                        target=fetch_library_track(item,Path(directory)/(item['id']+'.mp3'))
                        with lock,engine_client(app) as engine,Path(target).open('rb') as audio:
                            response=engine.post('/api/v1/music/import',data={'file':(audio,item['title']+'.mp3')},content_type='multipart/form-data')
                            if response.status_code!=201:raise ValueError('Could not prepare this music. Try again later.')
                            id=response.get_json()['id'];doc=read();doc[id]={**item,'bundled_id':item['id'],'id':id};save(doc)
                            added+=1;library_job['added']=added
                with lock:library_job.update(status='ready',added=added)
            except Exception:
                app.logger.exception('More music unavailable')
                with lock:library_job.update(status='failed',added=added,message='Could not retrieve all songs. Any songs already added are ready to use. Try again later.')
        threading.Thread(target=worker,daemon=True).start()
        return jsonify(status='importing'),202
