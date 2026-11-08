"""A missing optional insert goes through browser policy and real native export."""
import json
import subprocess
import time
import uuid
import numpy as np
from test_local_video import VideoJobs, install_layout, fingerprint, ROOT


def test_missing_insert_renders_camera_without_cutting_or_shifting_master(tmp_path, monkeypatch):
    home=tmp_path/'companion';_,sha=install_layout(home)
    folder=tmp_path/'project';folder.mkdir()
    camera=tmp_path/'camera.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=30:duration=2','-c:v','libx264','-threads','1',str(camera)],check=True)
    master=folder/f'montara-render-audio-{uuid.uuid4().hex}.audio'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','aevalsrc=if(lt(t\\,1)\\,0.2*sin(2*PI*440*t)\\,0.2*sin(2*PI*880*t)):s=48000:d=2','-f','wav',str(master)],check=True)
    first={'source':1,'master_start_sec':0,'clip_start_sec':0,'duration_sec':1}
    insert={'source':0,'master_start_sec':1,'clip_start_sec':0,'duration_sec':1}
    replacement={**insert,'source':1,'clip_start_sec':1,'playback_speed':1}
    recipe={'version':1,'platform':'youtube','engine':sha,'sources':[{'key':0,'path':'missing-logo.small.mp4','optional':True},{'key':1,'path':'camera.mp4','optional':False}], 'segments':[first,insert],'fallbacks':{'1':[replacement]}}
    script="const p=require('./web/native-export.js');let r=p.plan(JSON.parse(process.argv[1]),[0]);if(r.blocked)process.exit(1);process.stdout.write(JSON.stringify(r.recipe));"
    planned=json.loads(subprocess.check_output(['node','-e',script,json.dumps(recipe)],cwd=ROOT))
    manager=VideoJobs(home)
    original={'name':camera.name,'size':camera.stat().st_size,'fingerprint':fingerprint(camera)}
    token=manager.start({'project':'test','master':master.name,'recipe':planned,'originals':[{'source':1,'original':original}],'branding':'none'}, {'test':folder}, lambda _:camera)
    deadline=time.monotonic()+180
    while manager.status(token)['status'] not in ('ready','failed') and time.monotonic()<deadline:time.sleep(.2)
    assert manager.status(token)['status']=='ready',(manager.status(token),(folder/'.montara-renders'/token/'render.log').read_text()[-3000:])
    output=manager.output(token)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(output)]))
    assert abs(float(info['format']['duration'])-2)<.1
    assert {s['codec_type'] for s in info['streams']}=={'audio','video'}
    def audio(path):
        return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-ac','1','-ar','48000','-f','f32le','-']),dtype=np.float32)
    expected,actual=audio(master),audio(output)
    n=min(len(expected),len(actual))
    # The exporter intentionally fades programme edges. Compare the interval
    # across the insert boundary: a shift or truncated master moves the tone change.
    lo,hi=int(.8*48000),min(n,int(1.2*48000))
    assert np.corrcoef(expected[lo:hi],actual[lo:hi])[0,1]>.99
    manifest=json.loads((folder/'.montara-renders'/token/'render.json').read_text())
    assert manifest['recipe']['diagnostics']==[{'shot':2,'source':0,'replacement':1,'status':'omitted','name':'missing-logo.small.mp4'}]
    assert set(manifest['source_files'])=={'1'}
    restored=VideoJobs(home)
    assert restored.status(token)['diagnostics']==manifest['recipe']['diagnostics']


def test_tuneup_80_shots_16_missing_inserts_render_without_any_camera_fallback(tmp_path, monkeypatch):
    """Regression: no sync coverage exists for a replacement, and the last shot is absent."""
    import os
    home=tmp_path/'companion';_,sha=install_layout(home,os.environ.get('MONTARA_TEST_EDITOR'))
    folder=tmp_path/'project';folder.mkdir()
    camera=tmp_path/'original.mp4';seconds=32
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'testsrc2=size=640x360:rate=30:duration={seconds}',
                    '-c:v','libx264','-crf','15','-threads','1',str(camera)],check=True)
    master=folder/f'montara-render-audio-{uuid.uuid4().hex}.audio'
    # Changing frequency exposes shifts anywhere in the montage, not just at one cut.
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'aevalsrc=0.15*sin(2*PI*(220*t+7*t*t)):s=48000:d={seconds}',
                    '-f','wav',str(master)],check=True)
    shots=[{'source':0 if (i+1)%5==0 else 1,'master_start_sec':i*12/30,'clip_start_sec':i*12/30,'duration_sec':12/30,
            'video_light':{'auto':False,'light':0,'shadows':0}} for i in range(80)]
    recipe={'version':1,'platform':'youtube','engine':sha,'sources':[{'key':0,'path':'Tuneup short logo vid.small.mp4','optional':True},
             {'key':1,'path':'original.mp4','optional':False}], 'segments':shots,'fallbacks':{}}
    before=json.dumps(recipe,sort_keys=True)
    script="const p=require('./web/native-export.js');const r=p.plan(JSON.parse(process.argv[1]),[0]);if(r.blocked)process.exit(1);process.stdout.write(JSON.stringify({recipe:r.recipe,warnings:p.warnings(r.diagnostics)}));"
    result=json.loads(subprocess.check_output(['node','-e',script,json.dumps(recipe)],cwd=ROOT))
    planned=result['recipe']
    assert len(result['warnings'])==1 and '16' in result['warnings'][0] and 'black' in result['warnings'][0]
    assert len(planned['diagnostics'])==16
    assert json.dumps(recipe,sort_keys=True)==before
    for i,shot in enumerate(planned['segments']):
        assert (shot['master_start_sec'],shot['duration_sec'])==(i*12/30,12/30)
        if (i+1)%5:assert shot==shots[i]
        else:assert shot['placeholder']=='black' and 'source' not in shot
    manager=VideoJobs(home)
    original={'name':camera.name,'size':camera.stat().st_size,'fingerprint':fingerprint(camera)}
    token=manager.start({'project':'test','master':master.name,'recipe':planned,'originals':[{'source':1,'original':original}],
                         'branding':'none'}, {'test':folder}, lambda _:camera)
    deadline=time.monotonic()+600
    while manager.status(token)['status'] not in ('ready','failed') and time.monotonic()<deadline:time.sleep(.5)
    assert manager.status(token)['status']=='ready',(manager.status(token),(folder/'.montara-renders'/token/'render.log').read_text()[-5000:])
    output=manager.output(token)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(output)]))
    assert abs(float(info['format']['duration'])-seconds)<1/30+.01
    video=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (video['width'],video['height'])==(1920,1080)
    def audio(path):
        return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-ac','1','-ar','48000','-f','f32le','-']),dtype=np.float32)
    expected,actual=audio(master),audio(output)
    for i in range(1,79):
        lo,hi=int((i*.4+.1)*48000),int((i*.4+.3)*48000)
        assert np.corrcoef(expected[lo:hi],actual[lo:hi])[0,1]>.99, i+1
    # Decode the complete movie and sample the centre of EVERY slot in one pass.
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-vf',"select='eq(mod(n,12),6)',scale=64:36",'-fps_mode','vfr','-pix_fmt','gray','-f','rawvideo','-'])
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,36,64)
    assert len(frames)==80
    # Compare camera slots with an independent original-quality
    # export with the same cut boundaries and programme fades. Comparing 360p source
    # gray values directly to tagged HD output confounds colour-range conversion
    # with changes to the edit. This control must retain camera pixels as well.
    control={'version':1,'platform':'youtube','engine':sha,'sources':[{'key':1}],
             'segments':[{**s,'source':1} for s in shots]}
    baseline=manager.start({'project':'test','master':master.name,'recipe':control,
                'originals':[{'source':1,'original':original}],'branding':'none','name':'Control'}, {'test':folder}, lambda _:camera)
    deadline=time.monotonic()+600
    while manager.status(baseline)['status'] not in ('ready','failed') and time.monotonic()<deadline:time.sleep(.5)
    assert manager.status(baseline)['status']=='ready',manager.status(baseline)
    reference=subprocess.check_output(['ffmpeg','-v','error','-i',str(manager.output(baseline)),'-vf',"select='eq(mod(n,12),6)',scale=64:36",'-fps_mode','vfr','-pix_fmt','gray','-f','rawvideo','-'])
    reference=np.frombuffer(reference,dtype=np.uint8).reshape(-1,36,64)
    for i,frame in enumerate(frames):
        if (i+1)%5==0:assert frame.max()<5,(i+1,frame.max())
        elif 0<i<79:assert np.abs(frame.astype(float)-reference[i]).mean()<3,(i+1,np.abs(frame.astype(float)-reference[i]).mean())
    manifest=json.loads((folder/'.montara-renders'/token/'render.json').read_text())
    assert len(manifest['recipe']['diagnostics'])==16
    assert set(manifest['source_files'])=={'1'}
    assert VideoJobs(home).status(token)['diagnostics']==manifest['recipe']['diagnostics']
    # Retain a compact CI proof and movie when an artifact directory is requested.
    if os.environ.get('MONTARA_CONTINUITY_PROOF'):
        import shutil
        from pathlib import Path
        target=Path(os.environ['MONTARA_CONTINUITY_PROOF']);target.mkdir(parents=True,exist_ok=True)
        shutil.copy2(output,target/'render.mp4')
        (target/'summary.json').write_text(json.dumps({'passed':True,'shots':80,'missing_inserts':16,'warnings':result['warnings'],
            'seconds':float(info['format']['duration']),'resolution':[video['width'],video['height']],
            'audio_correlation_min':min(float(np.corrcoef(expected[int((i*.4+.1)*48000):int((i*.4+.3)*48000)],actual[int((i*.4+.1)*48000):int((i*.4+.3)*48000)])[0,1]) for i in range(1,79)),
            'authored_recipe_unchanged':True},indent=2))
