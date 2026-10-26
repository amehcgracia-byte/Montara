"""Continuous, effect-free editing proxies, from the engine's public cut list."""
from __future__ import annotations
import hashlib
import json
import subprocess
import threading
from pathlib import Path
from preview_api import engine_client
from urllib.parse import parse_qs, urlsplit
from flask import jsonify, send_file


def register_show_playback(app, data_root):
    root = Path(data_root) / 'ShowPlayback'
    jobs = {}
    lock = threading.Lock()
    render_lock = threading.Lock()

    def render(key, source, segments, output):
        temporary = output.with_suffix('.working.mp4')
        try:
            with render_lock:
                root.mkdir(parents=True, exist_ok=True)
                info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(source)], timeout=30))
                audio = any(s['codec_type']=='audio' for s in info['streams'])
                start = min(a for a,b in segments)
                end = max(b for a,b in segments)
                graph=[]
                for i,(a,b) in enumerate(segments):
                    graph.append(f'[0:v]trim=start={a-start:.6f}:end={b-start:.6f},setpts=PTS-STARTPTS,scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1[v{i}]')
                    if audio:graph.append(f'[0:a]atrim=start={a-start:.6f}:end={b-start:.6f},asetpts=PTS-STARTPTS[a{i}]')
                labels=''.join(f'[v{i}]'+(f'[a{i}]' if audio else '') for i in range(len(segments)))
                graph.append(labels+f'concat=n={len(segments)}:v=1:a={int(audio)}[v]'+('[a]' if audio else ''))
                args=['ffmpeg','-v','error','-y','-threads','2','-ss',str(start),'-t',str(end-start),'-i',str(source),'-filter_complex_threads','1','-filter_complex',';'.join(graph),'-map','[v]']
                if audio:args+=['-map','[a]','-c:a','aac','-b:a','128k']
                args+=['-c:v','libx264','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p','-r','30','-fps_mode','cfr','-threads','2','-movflags','+faststart',str(temporary)]
                subprocess.run(args,check=True,capture_output=True,timeout=600)
                temporary.replace(output)
                with lock:jobs[key]={'status':'ready','url':f'/montara/show/playback/{key}.mp4'}
        except Exception:
            app.logger.exception('Continuous Show playback failed')
            temporary.unlink(missing_ok=True)
            with lock:jobs[key]={'status':'failed','message':'Could not prepare continuous playback. Try Preview this part.'}

    @app.post('/montara/show/playback/<scene_id>')
    def prepare(scene_id):
        with engine_client(app) as engine:
            response=engine.get('/api/v1/show/scenes')
            if response.status_code!=200:return response.get_json(),response.status_code
            document=response.get_json()
            scene=next((s for s in document['scenes'] if s['id']==scene_id),None)
            if scene is None:return jsonify(message='Choose a part in this video.'),404
            url=document['source_url']
            check=engine.head(url)
            if check.status_code!=200:return jsonify(message='The source video is unavailable.'),404
        source=Path(parse_qs(urlsplit(url).query)['path'][0])
        segments=scene.get('segments') or [[scene['start'],scene['end']]]
        stat=source.stat()
        key=hashlib.sha256(json.dumps([str(source),stat.st_size,stat.st_mtime_ns,segments,'v2']).encode()).hexdigest()[:32]
        output=root/(key+'.mp4')
        with lock:
            if output.is_file():jobs[key]={'status':'ready','url':f'/montara/show/playback/{key}.mp4'}
            if key not in jobs or jobs[key]['status']=='failed':
                jobs[key]={'status':'preparing'}
                threading.Thread(target=render,args=(key,source,segments,output),daemon=True).start()
            return jsonify({**jobs[key], 'poll':f'/montara/show/playback/jobs/{key}'})

    @app.get('/montara/show/playback/jobs/<key>')
    def progress(key):
        with lock:
            if key not in jobs:return jsonify(message='Playback preparation expired. Press Play again.'),404
            return jsonify({**jobs[key], 'poll':f'/montara/show/playback/jobs/{key}'})

    @app.get('/montara/show/playback/<key>.mp4')
    def media(key):
        if len(key)!=32 or any(c not in '0123456789abcdef' for c in key):return '',404
        path=root/(key+'.mp4')
        if not path.is_file():return '',404
        return send_file(path,mimetype='video/mp4',conditional=True)
