#!/usr/bin/env python3
"""Render a reviewed Stage plan with verified local originals, in isolation."""
import json,os,shutil,sys,time,threading
from pathlib import Path


def run(manifest):
    body=json.loads(Path(manifest).read_text())
    from video_recipe import validate
    recipe=validate(body['recipe'])
    root=Path(body['work']);root.mkdir(parents=True,exist_ok=True)
    os.environ['ZUCKER_DATA_ROOT']=str(root/'state')
    os.environ['ZUCKER_GLOBAL_CACHE']=str(root/'state'/'Cache')
    engine=Path(__file__).parent/'engine'
    sys.path.insert(0,str(engine))
    from core.project import create_project,file_record,atomic_write_json
    from core.ffmpeg import ffprobe
    from core.media_validation import validate_camera_video_metadata
    # The native Mac output uses a higher-resolution 360 intermediate than
    # the lightweight server preview; cache profiles are keyed separately.
    os.environ['MONTARA_360_EXPORT_QUALITY']='high'
    from core.stages.export import ExportStage
    progress=Path(body['progress']);started=time.monotonic();progress_lock=threading.Lock();last_progress_write=0.
    tasks={f'segment-{i+1}':{'id':f'segment-{i+1}','label':f'Shot {i+1}/{len(recipe["segments"])}','percent':0} for i in range(len(recipe['segments']))}
    def update(value,message):
        nonlocal last_progress_write
        with progress_lock:
            task=getattr(message,'task',None)
            if task and task['id'].startswith('segment-'):tasks[task['id']]=dict(task)
            now=time.monotonic()
            if now-last_progress_write<.2 and value<100 and (not task or task.get('percent')!=100):return
            last_progress_write=now
            atomic_write_json(progress,{'status':'rendering','progress':min(.99,max(0,float(value)/100)),'message':str(message)[:200],'tasks':list(tasks.values())})
    update(0,'Preparing original-quality video')
    p=create_project('Montara original quality',str(root/'edit.zuckervid'))
    sources={int(k):Path(v) for k,v in body['source_files'].items()}
    records=[]
    for key,path in sources.items():
        r=file_record(str(path));r['probe']=validate_camera_video_metadata(ffprobe(str(path))).summary
        r['camera_role']='handheld';r['camera_id']=str(key);records.append(r)
    p.data['inputs']['videos']=records
    p.data['inputs']['master']=file_record(body['master'])
    p.data['settings']['wizard']={'platform':'youtube'}
    p.data['settings']['edit']['video_light']={'enabled':False}
    p.data['settings']['export'].update(segment_workers=2)
    brand=Path(__file__).parent/'brand'
    state=root/'state';state.mkdir(exist_ok=True)
    config={'branding':{'mode':'none' if body['branding']=='none' else 'custom' if body['branding']=='mine' else 'default','logo_path':str(brand/'montara-logo.png'),'watermark_path':str(brand/'montara-watermark.png'),'intro_card':False,'bookends':'separate'}}
    if body.get('personal_logo'):config['personal_logo_path']=body['personal_logo']
    atomic_write_json(state/'config.json',config)
    segments=[]
    for raw in recipe['segments']:
        key=raw['source'];path=str(sources[key]);r=next(r for r in records if r['path']==path)
        s={k:v for k,v in raw.items() if k!='source'}
        s.update(clip_path=path,source_path=path,probe=r['probe'])
        from core.stages.edit import _camera_id_from_render_path
        s['camera_id']=_camera_id_from_render_path(s)
        if s['clip_start_sec']+s['duration_sec']*s.get('playback_speed',1.0)>float(r['probe']['duration'])+.15:raise ValueError('The original does not cover the shot at this playback speed')
        segments.append(s)
    p.save();atomic_write_json(p.artifacts_dir/'edit_plan.json',{'platform':'youtube','segments':segments})
    atomic_write_json(p.artifacts_dir/'coverage.json',{'platform':'youtube','sources':[],'segments':segments})
    ExportStage().run(p,update)
    outputs=sorted(p.exports_dir.glob('*.mp4'),key=lambda v:v.stat().st_mtime)
    if not outputs:raise RuntimeError('No final video was produced')
    destination=Path(body['output']);outputs[-1].replace(destination)
    atomic_write_json(progress,{'status':'ready','progress':1.,'seconds':round(time.monotonic()-started,1)})
    # Segment caches are reproducible; keep the final result, plan and diagnostics.
    shutil.rmtree(state/'Cache',ignore_errors=True)
    return destination


if __name__=='__main__':
    try:run(sys.argv[1])
    except Exception as exc:
        print(str(exc),file=sys.stderr);raise
