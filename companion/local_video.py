#!/usr/bin/env python3
"""Render a reviewed Stage plan with verified local originals, in isolation."""
import json,os,shutil,sys,time
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
    from core.stages.export import ExportStage
    p=create_project('Montara original quality',str(root/'edit.zuckervid'))
    sources={int(k):Path(v) for k,v in body['source_files'].items()}
    records=[]
    for key,path in sources.items():
        r=file_record(str(path));r['probe']=validate_camera_video_metadata(ffprobe(str(path))).summary
        r['camera_role']='handheld';r['camera_id']=str(key);records.append(r)
    p.data['inputs']['videos']=records
    p.data['inputs']['master']=file_record(body['master'])
    p.data['settings']['wizard']={'platform':'youtube'}
    p.data['settings']['edit']['video_light']={'enabled':any('video_light' in s for s in recipe['segments'])}
    p.data['settings']['export'].update(segment_workers=2)
    brand=Path(__file__).parent/'brand'
    state=root/'state';state.mkdir(exist_ok=True)
    atomic_write_json(state/'config.json',{'branding':{'mode':'none' if body['branding']=='none' else 'default','logo_path':str(brand/'montara-logo.png'),'watermark_path':str(brand/'montara-watermark.png'),'intro_card':False}})
    segments=[]
    for raw in recipe['segments']:
        key=raw['source'];path=str(sources[key]);r=next(r for r in records if r['path']==path)
        s={k:v for k,v in raw.items() if k!='source'}
        s.update(clip_path=path,source_path=path,probe=r['probe'])
        from core.stages.edit import _camera_id_from_render_path
        s['camera_id']=_camera_id_from_render_path(s)
        if s['clip_start_sec']+s['duration_sec']>float(r['probe']['duration'])+.15:raise ValueError('The original does not cover this shot')
        segments.append(s)
    p.save();atomic_write_json(p.artifacts_dir/'edit_plan.json',{'platform':'youtube','segments':segments})
    atomic_write_json(p.artifacts_dir/'coverage.json',{'platform':'youtube','sources':[],'segments':segments})
    progress=Path(body['progress']);started=time.monotonic()
    def update(value,message):
        atomic_write_json(progress,{'status':'rendering','progress':min(.99,max(0,float(value)/100)),'message':str(message)[:200]})
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
