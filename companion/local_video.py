#!/usr/bin/env python3
"""Render a reviewed Stage plan with verified local originals, in isolation."""
import hashlib,json,os,re,shutil,sys,time,threading
from pathlib import Path


GIB = 1024**3
SPHERICAL_CACHE_LIMIT = 16 * GIB
SPHERICAL_FREE_RESERVE = 8 * GIB


def retain_spherical_cache(shared, targets, *, restore=False):
    """Link completed engine-keyed intermediates, never partial files or copies."""
    if not shared or not targets:
        return 0
    shared = Path(shared)
    if restore and not shared.is_dir():
        return 0
    if not restore:
        shared.mkdir(parents=True, exist_ok=True)
    if shared.is_symlink():
        return 0
    retained = sum(p.stat().st_size for p in shared.glob('equirect-*.mp4')
                   if p.is_file() and not p.is_symlink())
    count = 0
    for target in targets:
        if not re.fullmatch(r'equirect-[a-f0-9]{24}\.mp4', target.name):
            continue
        cached = shared / target.name
        src, dst = (cached, target) if restore else (target, cached)
        try:
            if dst.exists() or src.is_symlink() or not src.is_file():
                continue
            size = src.stat().st_size
            if not size or (not restore and (retained + size > SPHERICAL_CACHE_LIMIT
                                            or shutil.disk_usage(shared).free < SPHERICAL_FREE_RESERVE)):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.link(src, dst)
            count += 1
            if not restore:
                retained += size
        except OSError:
            # Different volumes, permissions or a concurrent link: keep the
            # ordinary per-job cache. Do not copy large data or evict anything.
            continue
    return count


def timing(**data):
    print('[Montara native timing] '+json.dumps(data,sort_keys=True),flush=True)


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
    from core.stages.export import ExportStage, _spherical_sources_to_prepare, _spherical_export_proxy_target
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
    timing(phase='locate originals',seconds=body.get('source_lookup_sec'),sources=len(body['source_files']))
    probe_started=time.monotonic()
    p=create_project('Montara original quality',str(root/'edit.zuckervid'))
    sources={int(k):Path(v) for k,v in body['source_files'].items()}
    records=[]
    probes={}
    for source_index,(key,path) in enumerate(sources.items(),1):
        update(0,f'Checking local camera metadata {source_index}/{len(sources)}')
        expected=body.get('verified_originals',{}).get(str(key))
        if expected:
            with path.open('rb') as handle:
                first=handle.read(65536);handle.seek(max(0,path.stat().st_size-65536));last=handle.read(65536)
            if path.stat().st_size!=expected['size'] or hashlib.sha256(first+last).hexdigest()!=expected['fingerprint']:
                raise ValueError('Original changed while queued: '+expected['name'])
        if path not in probes:
            probes[path]=validate_camera_video_metadata(ffprobe(str(path))).summary
        r=file_record(str(path));r['probe']=dict(probes[path])
        r['camera_role']='handheld';r['camera_id']=str(key);records.append(r)
    timing(phase='check metadata',seconds=round(time.monotonic()-probe_started,3),sources=len(records),probes=len(probes))
    plan_started=time.monotonic()
    p.data['inputs']['videos']=records
    p.data['inputs']['master']=file_record(body['master'])
    p.data['settings']['wizard']={'platform':'youtube'}
    p.data['settings']['edit']['video_light']={'enabled':False}
    p.data['settings']['export'].update(segment_workers=2)
    brand=Path(__file__).parent/'brand'
    state=root/'state';state.mkdir(exist_ok=True)
    config={'branding':{'mode':'none' if body['branding']=='none' else 'custom' if body['branding']=='mine' else 'default','logo_path':str(brand/'montara-logo.png'),'watermark_path':str(brand/'montara-watermark.png'),'intro_card':False,'bookends':'within-content'}}
    if body.get('personal_logo'):config['personal_logo_path']=body['personal_logo']
    atomic_write_json(state/'config.json',config)
    segments=[]
    for raw in recipe['segments']:
        if raw.get('placeholder')=='black':
            segments.append(dict(raw));continue
        key=raw['source'];path=str(sources[key]);r=next(r for r in records if r['path']==path)
        s={k:v for k,v in raw.items() if k!='source'}
        s.update(clip_path=path,source_path=path,probe=r['probe'])
        from core.stages.edit import _camera_id_from_render_path
        s['camera_id']=_camera_id_from_render_path(s)
        if s['clip_start_sec']+s['duration_sec']*s.get('playback_speed',1.0)>float(r['probe']['duration'])+.15:raise ValueError('The original does not cover the shot at this playback speed')
        segments.append(s)
    update(0,'Preparing reviewed shot plan for original-quality export')
    p.save();atomic_write_json(p.artifacts_dir/'edit_plan.json',{'platform':'youtube','segments':segments})
    atomic_write_json(p.artifacts_dir/'coverage.json',{'platform':'youtube','sources':[],'segments':segments})
    timing(phase='prepare plan',seconds=round(time.monotonic()-plan_started,3),shots=len(segments))
    targets=set()
    for info, segment in _spherical_sources_to_prepare(p,segments).values():
        target=_spherical_export_proxy_target(p,info,segment)
        if target is not None:
            targets.add(target)
    cache_started=time.monotonic()
    try:
        restored=retain_spherical_cache(body.get('spherical_cache'),targets,restore=True)
    except OSError:
        restored=0
    timing(phase='restore 360 cache',seconds=round(time.monotonic()-cache_started,3),expected=len(targets),reused=restored)
    update(0,'Starting export engine')
    export_started=time.monotonic()
    timing(phase='export engine start',elapsed=round(export_started-started,3))
    try:
        result=ExportStage().run(p,update)
    except Exception as exc:
        timing(phase='export failed',seconds=round(time.monotonic()-export_started,3),error_type=type(exc).__name__)
        raise
    perf=result.get('performance') or {}
    phases=perf.get('phases',{})
    timing(phase='360 preparation',seconds=phases.get('source_prepare_sec'),sources=phases.get('source_proxy_count'),reused=restored)
    timing(phase='render segments',seconds=perf.get('wall_sec'),segments=perf.get('segment_count'))
    timing(phase='assemble final',concat_sec=phases.get('concat_sec'),cadence_sec=phases.get('cadence_sec'),mux_sec=phases.get('mux_sec'))
    cache_started=time.monotonic()
    try:
        retained=retain_spherical_cache(body.get('spherical_cache'),targets)
    except OSError:
        retained=0
    timing(phase='retain 360 cache',seconds=round(time.monotonic()-cache_started,3),retained=retained)
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
