"""Real project edits: split/delete, synchronized ripple, undo and real output."""
import copy,json,subprocess,time
from pathlib import Path
from test_show_direction import directed


def state(p):
    from show_cut_edit import read_state
    return read_state(p.artifacts_dir)


def edit(c,p,op,**body):
    doc=c.get('/api/v1/edit/timeline?kind=show').get_json()
    return c.post('/montara/show/cuts',json=dict(project_id=str(p.folder),revision=doc['revision'],op=op,**body))


def test_split_twice_delete_middle_and_undo(directed):
    c,p,plan=directed
    # Add a long real music bed and a later effect; both must follow the cut.
    track=next(t for t in c.get('/montara/music').get_json()['items'] if t['name']=='Heartbreaking')
    r=c.post('/montara/music/place/'+track['id'],json=dict(project_id=str(p.folder),scene_id='s1',at=1,duration=49,start=2,volume=.1,under_voice=True));assert r.status_code==201,r.get_json()
    original=state(p)
    first=edit(c,p,'split',at=14.5);assert first.status_code==200,first.get_json()
    second=edit(c,p,'split',at=15);assert second.status_code==200,second.get_json()
    before_delete=state(p);assert len(before_delete['show_plan.json']['shots'])==32
    removed=edit(c,p,'delete',index=8);assert removed.status_code==200,removed.get_json();assert removed.get_json()['removed']==.5
    after=state(p);assert after['show_plan.json']['edited_duration']==59.5
    assert after['show_scenes.json']['scenes'][0]['end']==59.5
    assert len(after['show_plan.json']['shots'])==31
    songs=[i for i in after['show_proposals.json']['proposals'] if i['kind']=='jingle']
    assert len(songs)==2
    assert [(s['at'],s['duration'],s['params']['start']) for s in songs]==[(1,13.5,2),(14.5,35,16)]
    from core.show import edited_words
    timed=edited_words(after['show_plan.json']);assert next(w for w in timed if w[0]=='La')[1]==43.5
    # Undo restores the entire edit, including source offsets, effects and part edges.
    for response,expected in [(removed,before_delete),(second,None),(first,original)]:
        undo=edit(c,p,'undo',operation_id=response.get_json()['operation_id']);assert undo.status_code==200,undo.get_json()
        if expected:assert state(p)==expected


def test_stale_selection_last_shot_and_newer_edits_are_protected(directed):
    c,p,plan=directed;doc=c.get('/api/v1/edit/timeline?kind=show').get_json()
    assert edit(c,p,'split',at=3).status_code==200
    assert c.post('/montara/show/cuts',json=dict(op='delete',index=0,project_id=str(p.folder),revision=doc['revision'])).status_code==409
    assert edit(c,p,'split',at=float('nan')).status_code==400
    assert edit(c,p,'split',at=0).status_code==400
    assert edit(c,p,'delete',index=-1).status_code==400
    r=edit(c,p,'delete',index=1);assert r.status_code==200
    # An effect edit after this deletion must be undone before restoring a snapshot.
    scenes=p.artifacts_dir/'show_scenes.json';d=json.loads(scenes.read_text());d['scenes'][0]['decision']='plain';scenes.write_text(json.dumps(d))
    assert edit(c,p,'undo',operation_id=r.get_json()['operation_id']).status_code==409
    path=p.artifacts_dir/'show_plan.json';d=json.loads(path.read_text());d['shots']=d['shots'][:1];path.write_text(json.dumps(d))
    assert edit(c,p,'delete',index=0).status_code==400


def test_delete_reaches_render_and_keeps_sound(directed):
    c,p,plan=directed
    # A distinct tone exists only in the removed source interval. It must not
    # survive in the rendered sound, not merely disappear from the JSON.
    import numpy as np,wave
    wav=p.folder/'distinct.wav';rate=16000;t=np.arange(rate*60)/rate
    samples=(.2*np.sin(2*np.pi*np.where((t>=14)&(t<16),1000,300)*t)*32767).astype('<i2')
    with wave.open(str(wav),'wb') as out:out.setparams((1,2,rate,0,'NONE','not compressed'));out.writeframes(samples.tobytes())
    source=Path(plan['source']);replacement=p.folder/'replacement.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-i',str(wav),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-shortest',str(replacement)],check=True);replacement.replace(source)
    assert edit(c,p,'delete',index=7).status_code==200
    response=c.post('/api/v1/show/scenes/s1/preview',json={'next':[]});assert response.status_code in (200,202),response.get_json()
    for _ in range(300):
        preview=c.get('/api/v1/show/scenes').get_json()['scenes'][0].get('preview') or {}
        if preview.get('status') in {'ready','failed'}:break
        time.sleep(.2)
    assert preview.get('status')=='ready',preview
    output=p.folder/'deleted-preview.mp4';output.write_bytes(c.get(preview['url']).data)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
    assert abs(float(info['format']['duration'])-58)<.15
    assert {'video','audio'}<={s['codec_type'] for s in info['streams']}
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-vn','-ar','16000','-ac','1','-f','f32le','-'])
    sound=np.frombuffer(raw,dtype='<f4');spectrum=np.abs(np.fft.rfft(sound))**2;freq=np.fft.rfftfreq(len(sound),1/16000)
    assert float(spectrum[(freq>990)&(freq<1010)].sum()/spectrum.sum())<.001


def test_whole_scene_removed_and_later_scene_ripples(directed):
    c,p,plan=directed
    path=p.artifacts_dir/'show_scenes.json';d=json.loads(path.read_text());s=d['scenes'][0];d['scenes']=[dict(s,id='first',start=0,end=2),dict(s,id='rest',start=2,end=60)];path.write_text(json.dumps(d))
    assert edit(c,p,'delete',index=0).status_code==200
    scenes=c.get('/api/v1/show/scenes').get_json()['scenes'];assert len(scenes)==1
    assert scenes[0]['id']=='rest' and scenes[0]['start']==0 and scenes[0]['end']==58


def test_editor_actions_do_not_probe_or_build_full_previews(directed,monkeypatch):
    c,p,plan=directed
    from core import ffmpeg
    def forbidden(*a,**k):raise AssertionError('Editing must not probe media or render previews')
    monkeypatch.setattr(ffmpeg,'ffprobe',forbidden)
    original=c.application.view_functions['api_show_scenes']
    c.application.view_functions['api_show_scenes']=forbidden
    response=edit(c,p,'split',at=3)
    assert response.status_code==200,response.get_json()
    data=response.get_json();assert 'editor' in data and data['processing_ms']>=0
    assert len(data['editor']['timeline']['shots'])==31
    assert c.get('/montara/show/editor').status_code==200
    c.application.view_functions['api_show_scenes']=original
