"""Exercise the actual music import/placement/audio APIs with real media."""
from pathlib import Path
import io,json,os,subprocess,sys,time
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

@pytest.fixture
def shelf(tmp_path,monkeypatch):
    monkeypatch.setenv('ZUCKER_DATA_ROOT',str(tmp_path/'data'))
    monkeypatch.delenv('MONTARA_SESSION_TOKEN',raising=False)
    from app import create_montara_app
    app=create_montara_app(tmp_path/'data');client=app.test_client()
    from core.project import create_project
    from core import show_scenes,show_proposals
    p=create_project('Music test',str(tmp_path/'show.zuckervid'));source=p.folder/'talk.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x90:r=30:d=3','-f','lavfi','-i','sine=frequency=300:duration=3','-c:v','libx264','-threads','1','-c:a','aac','-shortest',str(source)],check=True)
    plan={'source':str(source),'fps':30,'edited_duration':3,'cuts':0,'words':[], 'shots':[{'start_frame':0,'end_frame':90,'words':[]}]}
    (p.artifacts_dir/'show_plan.json').write_text(json.dumps(plan))
    show_proposals.save(p.artifacts_dir/'show_proposals.json',[],source=str(source),resources=[])
    show_scenes.save(p.artifacts_dir/'show_scenes.json',dict(identity={},scenes=[dict(id='s1',name='Test',start=0,end=3,effects=[],overlays=[],decision='modified',text='Test')]))
    assert client.post('/api/v1/project/open',json={'folder':str(p.folder)}).status_code==200
    return client,p

def test_catalog_ranges_and_no_path_access(shelf):
    c,p=shelf;items=c.get('/montara/music').get_json()['items'];assert len(items)==13 and sum(i['license']=='CC0' for i in items)==1 and sum(i['license']=='CC BY 4.0' for i in items)==12
    r=c.get(items[0]['url'],headers={'Range':'bytes=0-63'});assert r.status_code==206 and len(r.data)==64
    assert c.get('/montara/music/file/not-a-track').status_code==404
    assert 'path' not in items[0]
    assert all(sum(t['category']==mood for t in items)==2 for mood in ('Tension','Horror','Emotional piano'))
    assert len(c.get('/montara/samples?platform=reel').get_json()['master'])==1

def test_place_volume_retime_remove_and_source_ownership(shelf):
    c,p=shelf;t=next(t for t in c.get('/montara/music').get_json()['items'] if t['license']=='CC BY 4.0');body=dict(project_id=str(p.folder),scene_id='s1',at=.2,duration=2,start=1,volume=.25,under_voice=True)
    assert c.post('/montara/music/place/'+t['id'],json={**body,'project_id':'wrong'}).status_code==400
    assert c.post('/montara/music/place/'+t['id'],json={**body,'volume':float('nan')}).status_code==400
    r=c.post('/montara/music/place/'+t['id'],json=body);assert r.status_code==201,r.get_json();item=r.get_json()['proposal'];assert item['params']['volume']==.25 and item['params']['start']==1
    assert Path(item['params']['path']).is_relative_to(p.folder/'assets/music')
    assert c.patch('/api/v1/show/review/'+item['id'],json={'at':.4,'duration':1.5}).status_code==200
    r=c.patch('/api/v1/show/audio/tracks/'+item['id'],json={'project_id':str(p.folder),'volume':.1,'mode':'mix','under_voice':True});assert r.get_json()['params']['volume']==.1
    assert b'Creative Commons Attribution 4.0' in c.get('/montara/music/credits',query_string={'project_id':str(p.folder)}).data
    assert c.patch('/api/v1/show/review/'+item['id'],json={'status':'discarded'}).status_code==200
    from core import show_proposals
    assert not show_proposals.render_inputs(show_proposals.load(p.artifacts_dir/'show_proposals.json')['proposals'])[1]
    assert c.get('/montara/music/credits',query_string={'project_id':str(p.folder),'format':'json'}).get_json()['required']==0

def test_music_reaches_actual_render(shelf):
    c,p=shelf
    import numpy as np,wave
    wav=io.BytesIO();samples=(np.sin(2*np.pi*880*np.arange(48000*3)/48000)*.3*32767).astype('<i2')
    with wave.open(wav,'wb') as audio:audio.setparams((1,2,48000,0,'NONE','not compressed'));audio.writeframes(samples.tobytes())
    wav.seek(0);r=c.post('/montara/music/import',data={'file':(wav,'test-music.wav')},content_type='multipart/form-data');assert r.status_code==201,r.get_json();t=r.get_json()
    r=c.post('/montara/music/place/'+t['id'],json=dict(project_id=str(p.folder),scene_id='s1',at=0,duration=3,start=0,volume=.6,under_voice=True));assert r.status_code==201,r.get_json()
    r=c.post('/api/v1/show/scenes/s1/preview',json={'next':[]});assert r.status_code in (200,202),r.get_json()
    for _ in range(180):
        r=c.get('/api/v1/show/scenes').get_json();preview=r['scenes'][0].get('preview') or {}
        if preview.get('status') in ('ready','failed','done'):break
        time.sleep(.2)
    assert preview.get('status')=='ready',preview
    url=preview.get('url');assert url,preview
    media=c.get(url);assert media.status_code==200
    output=p.folder/'verified-preview.mp4';output.write_bytes(media.data)
    result=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type','-of','json',str(output)]));assert any(s['codec_type']=='audio' for s in result['streams'])
    # A 300 Hz narrator tone plus non-tonal music must contain energy away from the narrator frequency.
    import numpy as np
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-vn','-ar','16000','-ac','1','-f','f32le','-']);x=np.frombuffer(raw,dtype='<f4');spec=np.abs(np.fft.rfft(x));freq=np.fft.rfftfreq(len(x),1/16000)
    assert float(np.sum(spec[(freq>500)&(freq<6000)]**2))>float(np.sum(spec**2))*.01

def test_youtube_music_import_and_failure(shelf, monkeypatch, tmp_path):
    import reference_import,shutil
    c,p=shelf
    monkeypatch.setattr(reference_import,'reference_url',lambda url:url)
    def imported(url,folder):
        target=folder/'music.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=730:duration=2',str(target)],check=True)
        return target,'My online song'
    monkeypatch.setattr(reference_import,'import_reference',imported)
    assert c.post('/montara/music/link',json={'url':'http://127.0.0.1/private.mp3'}).status_code==400
    assert c.post('/montara/music/link',json={'url':'https://youtube.com.evil.example/watch?v=x'}).status_code==400
    assert c.post('/montara/music/link',json={'url':'https://www.youtube.com/watch?v=example'}).status_code==202
    for _ in range(100):
        result=c.get('/montara/music/link').get_json()
        if result['status']!='importing':break
        time.sleep(.05)
    assert result['status']=='ready',result
    track=next(r for r in c.get('/montara/music').get_json()['items'] if r['id']==result['id'])
    assert track['name']=='My online song' and track['license']=='Check permission'
    assert c.get(track['url'],headers={'Range':'bytes=0-63'}).status_code==206
    assert not list(tmp_path.glob('data/MusicShelf/online-*'))
    def blocked(url,folder):raise ValueError('This service requires access or browser verification.')
    monkeypatch.setattr(reference_import,'import_reference',blocked)
    assert c.post('/montara/music/link',json={'url':'https://youtu.be/example'}).status_code==202
    for _ in range(100):
        result=c.get('/montara/music/link').get_json()
        if result['status']!='importing':break
        time.sleep(.05)
    assert result['status']=='failed' and 'verification' in result['message']


def test_more_music_and_attribution_without_duplicate_charges(shelf, monkeypatch):
    import music_shelf
    c,p=shelf
    initial=c.get('/montara/music').get_json();assert initial['more_available']==15 and initial['library_total']==28
    assert next(t for t in initial['items'] if t['name']=='Face The Facts')['category']=='Retro'
    def fetch(item,target):
        # Different real audio for each catalogue item, without a third-party download in tests.
        tone=500+sum(map(ord,item['id']))%1000
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'sine=frequency={tone}:duration=2','-c:a','libmp3lame',str(target)],check=True)
        return target
    monkeypatch.setattr(music_shelf,'fetch_library_track',fetch)
    assert c.post('/montara/music/more',json={}).status_code==202
    for _ in range(200):
        result=c.get('/montara/music/more').get_json()
        if result['status']!='importing':break
        time.sleep(.05)
    assert result['status']=='ready' and result['added']==3,result
    data=c.get('/montara/music').get_json();assert len(data['items'])==16 and data['more_available']==12
    t=next(t for t in data['items'] if t['name']=='Fluffing a Duck')
    result=c.post('/montara/music/place/'+t['id'],json=dict(project_id=str(p.folder),scene_id='s1',at=0,duration=1,start=0,volume=.2,under_voice=True))
    assert result.status_code==201,result.get_json()
    credit=c.get('/montara/music/credits',query_string={'project_id':str(p.folder),'format':'json'}).get_json()
    assert credit['required']==1 and 'Fluffing a Duck' in credit['text'] and 'Kevin MacLeod' in credit['text']
    assert c.get('/montara/plans').status_code==200


def test_restart_reopens_saved_project_without_reanalysis(shelf,monkeypatch,tmp_path):
    import shutil
    c,p=shelf
    data=tmp_path/'data';saved=data/'Projects/Retained.zuckervid';saved.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(p.folder,saved)
    # Project JSON paths are not used as a source of authorization; the configured folder must belong to this instance.
    marker=saved/'artifacts/show_resume.json';marker.write_text(json.dumps({'reopen_review':True}))
    assert c.post('/api/v1/wizard/projects/open',json={'path':str(saved)}).status_code==200
    from app import create_montara_app
    restarted=create_montara_app(data).test_client()
    status=restarted.get('/api/v1/wizard/status').get_json()
    assert status['status']=='waiting_show_review' and status['project_path']==str(saved)
    assert restarted.get('/api/v1/show/scenes').get_json()['scenes'][0]['id']=='s1'
