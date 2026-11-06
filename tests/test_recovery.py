import json
import os
from flask import Flask
from recovery import register_recovery


def write(root, relative, data, timestamp):
    p = root / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    os.utime(p, (timestamp, timestamp))
    return p


def test_recovery_orders_projects_and_audio_sessions_not_just_old_jam(tmp_path):
    app = Flask(__name__); register_recovery(app, tmp_path)
    c = app.test_client()
    assert c.get('/montara/recovery/latest').status_code == 404
    session = write(tmp_path, 'Sessions/123456abcdef/session.json', {'id':'123456abcdef'}, 10)
    project = write(tmp_path, 'Projects/Current.zuckervid/project.json',
                    {'name':'Current', 'inputs':{'videos':[{'path':'camera.mp4'}]}}, 20)
    assert c.get('/montara/recovery/latest').json == {'kind':'project','path':str(project.parent), 'name':'Current','platform':'youtube'}
    write(tmp_path, 'Projects/Empty.zuckervid/project.json', {'inputs':{}}, 30)
    write(tmp_path, 'Projects/Broken.zuckervid/project.json', [], 40)
    assert c.get('/montara/recovery/latest').json['name'] == 'Current'
    os.utime(session, (50,50))
    assert c.get('/montara/recovery/latest').json == {'kind':'session', 'id':'123456abcdef'}


def test_recovery_ignores_symlink_and_invalid_session_id(tmp_path):
    app = Flask(__name__); register_recovery(app, tmp_path)
    foreign = tmp_path / 'foreign'; foreign.mkdir()
    (foreign/'project.json').write_text(json.dumps({'inputs':{'videos':[1]}}))
    (tmp_path/'Projects').mkdir()
    (tmp_path/'Projects'/'linked').symlink_to(foreign, target_is_directory=True)
    write(tmp_path, 'Sessions/123456abcdef/session.json', {'id':'different'}, 30)
    assert app.test_client().get('/montara/recovery/latest').status_code == 404
