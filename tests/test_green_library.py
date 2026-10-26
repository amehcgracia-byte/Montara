import json,subprocess
from pathlib import Path
import pytest


def test_curated_clip_can_be_imported_placed_and_keyed_without_network(tmp_path,monkeypatch):
    import app as montara
    fixtures=tmp_path/'fixtures';root=fixtures/'greenscreens';root.mkdir(parents=True)
    clip=root/'quote.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=0x00ff00:s=160x90:r=24:d=3','-f','lavfi','-i','sine=frequency=300:duration=3','-c:v','libx264','-threads','1','-c:a','aac','-shortest',str(clip)],check=True)
    outside=tmp_path/'other.mp4';outside.write_bytes(clip.read_bytes())
    (root/'catalog.json').write_text(json.dumps({'items':[dict(id='one',name='Test phrase',category='quotes',file='quote.mp4',duration=3,bytes=clip.stat().st_size,source_url='https://youtube.com/watch?v=test',matte='green'),dict(id='escape',name='Other',category='scenes',file='../other.mp4',duration=3,bytes=1,source_url='')]}))
    monkeypatch.setattr(montara,'FIXTURES',fixtures);data=tmp_path/'data';monkeypatch.setenv('ZUCKER_DATA_ROOT',str(data));monkeypatch.delenv('MONTARA_SESSION_TOKEN',raising=False)
    app=montara.create_montara_app(data,samples=False);c=app.test_client()
    from core.project import create_project
    p=create_project('Curated clip test',str(data/'Projects/test.zuckervid'))
    (p.artifacts_dir/'show_proposals.json').write_text(json.dumps({'version':1,'proposals':[],'resources':[]}))
    assert c.post('/api/v1/project/open',json={'folder':str(p.folder)}).status_code==200
    catalog=c.get('/montara/greenscreens').json
    assert [i['id'] for i in catalog['items']]==['one']
    assert [i['name'] for i in catalog['categories']]==['Quotes','Escenas','Pinturas','Textos']
    assert c.post('/montara/greenscreens/escape/use',json={}).status_code==404
    r=c.post('/montara/greenscreens/one/use',json={'project_id':str(p.folder)})
    assert r.status_code==200,r.json
    asset=r.json['asset'];assert asset['default_audio'] and asset['matte']=='green'
    assert Path(asset['path']).is_relative_to(p.folder)
    # Choosing from the library does not insert an effect until the user places it.
    stored=p.artifacts_dir/'show_proposals.json'
    assert not stored.exists() or not json.loads(stored.read_text()).get('proposals')
