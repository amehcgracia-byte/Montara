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
