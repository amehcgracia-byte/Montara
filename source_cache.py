"""Reuse included originals and completed Push downloads within one workspace."""
import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit,parse_qs


def source_key(url):
    p=urlsplit(str(url));host=(p.hostname or '').lower().removeprefix('www.').removeprefix('m.')
    if host=='youtu.be':return 'youtube:'+p.path.strip('/').split('/')[0]
    if host=='youtube.com':
        key=parse_qs(p.query).get('v',[''])[0]
        if p.path.startswith(('/shorts/','/live/','/embed/')):key=p.path.split('/')[2]
        if key:return 'youtube:'+key
    return str(url)


def find_source(data_root,fixtures,url):
    key=source_key(url);root=(Path(fixtures)/'push-links').resolve()
    try:
        entry=json.loads((root/'catalog.json').read_text()).get(key)
        if entry:
            path=(root/entry['file']).resolve()
            if path.is_relative_to(root) and path.is_file():return path,entry.get('title',path.stem),'included_original'
    except (OSError,ValueError,TypeError,KeyError):pass
    own=Path(data_root).resolve();packs=own/'PushPacks'
    for manifest in sorted(packs.glob('*/pack.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            item=json.loads(manifest.read_text())
            if item.get('status')!='ready' or source_key(item.get('url',''))!=key:continue
            path=Path(item['source']).resolve()
            if path.is_relative_to(own) and path.is_file():return path,item.get('title',path.stem),'workspace_download'
        except (OSError,ValueError,TypeError,KeyError):continue
    return None


def register_source_cache(app,data_root,fixtures):
    from core import show_clips
    from flask import request
    @app.after_request
    def imported_source_origin(response):
        if request.method=='POST' and request.path.startswith('/api/v1/show/references/video/') and request.path.endswith('/download') and response.status_code==201:
            data=response.get_json(silent=True) or {}
            path=Path(str(data.get('proposal',{}).get('params',{}).get('clip','')))
            try:
                origin=json.loads(path.with_suffix(path.suffix+'.json').read_text()).get('origin')
                if origin in {'included_original','workspace_download'}:
                    data['source_origin']=origin;response.set_data(app.json.dumps(data))
            except (OSError,ValueError,TypeError):pass
        return response
    app.config['MONTARA_SOURCE_CACHE']=(Path(data_root),Path(fixtures))
    if getattr(show_clips.download,'montara_cache',False):return
    original=show_clips.download
    def download(project,reference,ffmpeg):
        from flask import current_app,has_app_context
        roots=current_app.config.get('MONTARA_SOURCE_CACHE') if has_app_context() else None
        if not roots:return original(project,reference,ffmpeg)
        url=show_clips.check_link(reference.get('url'))
        cached=find_source(*roots,url)
        if not cached:return original(project,reference,ffmpeg)
        import math
        start,end=float(reference['start']),float(reference['end'])
        if not math.isfinite(start+end) or not 0<=start<end or end-start>show_clips.MAX_SECONDS:raise ValueError('Choose an interval of up to 30 seconds.')
        source,title,origin=cached
        key=hashlib.sha256(json.dumps([str(source),source.stat().st_mtime_ns,start,end]).encode()).hexdigest()[:24]
        folder=show_clips.folder(project);folder.mkdir(parents=True,exist_ok=True);target=folder/('reused-'+key+'.mp4')
        if not target.is_file():
            pending=folder/('.'+uuid.uuid4().hex+'.mp4')
            try:
                subprocess.run([ffmpeg,'-v','error','-nostdin','-y','-ss',str(start),'-i',str(source),'-t',str(end-start),'-map','0:v:0','-map','0:a:0?','-vf','fps=30,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','22','-c:a','aac','-ar','48000','-ac','2','-movflags','+faststart',str(pending)],check=True,capture_output=True,timeout=120)
                pending.replace(target)
                target.with_suffix('.mp4.json').write_text(json.dumps({'title':title,'source_url':url,'origin':origin}))
            finally:pending.unlink(missing_ok=True)
        return target
    download.montara_cache=True
    show_clips.download=download
