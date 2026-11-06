"""A video adopts a completed song mix, never the session guide or arbitrary path."""
import json
from pathlib import Path
from mixer_adapter.session import save
from test_full_session import client


def test_video_master_requires_finished_result_inside_its_session(tmp_path):
    c = client(tmp_path)
    work = tmp_path / 'data' / 'Sessions' / ('b' * 12)
    work.mkdir(parents=True)
    path = work / 'master.mp3'; path.write_bytes(b'finished song')
    data = {'id':'b'*12, 'status':'done', 'results':[{'id':1, 'name':'Song', 'path':str(path)}]}
    save(work / 'session.json', data)
    url = '/montara/session/' + 'b'*12 + '/video-master'
    assert c.post(url, json={'song':1}).json['master'] == str(path)
    assert c.post(url, json={'song':2}).status_code == 409
    assert c.post(url, json={'song':True}).status_code == 400
    outside = tmp_path / 'outside.mp3'; outside.write_bytes(b'private')
    data['results'][0]['path'] = str(outside); save(work / 'session.json', data)
    assert c.post(url, json={'song':1}).status_code == 400


def test_video_guide_waits_for_session_preparation(tmp_path):
    c = client(tmp_path)
    work = tmp_path / 'data' / 'Sessions' / ('b' * 12)
    work.mkdir(parents=True)
    save(work / 'session.json', {'id':'b'*12, 'status':'detecting'})
    assert c.get('/montara/session/' + 'b'*12 + '/video-source').status_code == 409
