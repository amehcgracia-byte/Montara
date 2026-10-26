import json,subprocess
from pathlib import Path
from test_show_direction import directed
from source_cache import find_source,source_key

def test_equivalent_youtube_links_and_no_cross_workspace_files(tmp_path):
    assert source_key('https://youtu.be/abc?t=4')==source_key('https://www.youtube.com/shorts/abc')==source_key('https://youtube.com/watch?v=abc')
    data=tmp_path/'mine';fixtures=tmp_path/'fixtures';outside=tmp_path/'other.mp4';outside.write_bytes(b'not shared')
    root=data/'PushPacks/a';root.mkdir(parents=True)
    path=root/'pack.json';path.write_text(json.dumps(dict(status='ready',url='https://youtu.be/abc',source=str(outside))))
    assert find_source(data,fixtures,'https://youtube.com/watch?v=abc') is None
    own=data/'own.mp4';own.write_bytes(b'own');path.write_text(json.dumps(dict(status='ready',url='https://youtu.be/abc',source=str(own),title='Own')))
    assert find_source(data,fixtures,'https://youtube.com/watch?v=abc')==(own,'Own','workspace_download')
    assert find_source(tmp_path/'different',fixtures,'https://youtu.be/abc') is None

def test_show_import_uses_actual_push_source_without_network(directed,monkeypatch):
    c,p,plan=directed
    from flask import current_app
    from core import show_clips
    # A completed Push download in this workspace. No special included-video case.
    data=p.folder.parent.parent;root=data/'PushPacks/a';root.mkdir(parents=True)
    (root/'pack.json').write_text(json.dumps(dict(status='ready',url='https://youtu.be/testsource',source=plan['source'],title='Push original')))
    import yt_dlp
    monkeypatch.setattr(yt_dlp.YoutubeDL,'download',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Network must not be used')))
    r=c.post('/api/v1/show/references/video',json=dict(url='https://youtube.com/watch?v=testsource',start=5,end=8,scene_id='s1',at=0,duration=3,project_id=str(p.folder)))
    assert r.status_code==201,r.get_json()
    r=c.post('/api/v1/show/references/video/'+r.json['id']+'/download',json={'duration':3})
    assert r.status_code==201,r.get_json()
    assert r.json['source_origin']=='workspace_download'
    clip=Path(r.json['proposal']['params']['clip']);assert clip.is_relative_to(p.folder) and clip.is_file()
    assert json.loads(clip.with_suffix('.mp4.json').read_text())['origin']=='workspace_download'
    seconds=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(clip)]))
    assert 2.9<=seconds<=3.2
