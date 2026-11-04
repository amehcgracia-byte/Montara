import json
import os
from collections import namedtuple
from pathlib import Path
from retention import collect

Usage=namedtuple('Usage','total used free')

def make(root, kind, name, stamp, data=None):
    folder=root/kind/name;folder.mkdir(parents=True)
    metadata=folder/('session.json' if kind=='Sessions' else 'project.json')
    metadata.write_text(json.dumps(data or {}));os.utime(metadata,(stamp,stamp))
    return folder


def test_oldest_pruned_newest_active_pinned_and_shared_upload_preserved(tmp_path):
    root=tmp_path;upload=root/'Uploads'/'shared';upload.mkdir(parents=True);(upload/'audio.wav').write_bytes(b'a')
    old=make(root,'Sessions','old',1,{'tracks':[{'path':str(upload/'audio.wav')}]})
    latest=make(root,'Sessions','latest',4,{'tracks':[{'path':str(upload/'audio.wav')}]})
    active=make(root,'Projects','active',2)
    pinned=make(root,'Projects','pinned',3);(pinned/'.keep').touch()
    new=make(root,'Projects','new',4)
    assert collect(root,used_limit=60,active_project=active,usage=lambda _: Usage(100,80,20),now=lambda:10000)==['Sessions/old']
    assert all(p.exists() for p in [latest,active,pinned,new,upload]) and not old.exists()


def test_busy_or_uncertain_metadata_deletes_nothing(tmp_path):
    old=make(tmp_path,'Sessions','old',1);make(tmp_path,'Sessions','new',2)
    usage=lambda _:Usage(100,80,20)
    assert collect(tmp_path,used_limit=60,busy=lambda:True,usage=usage)==[]
    (old/'session.json').write_text('bad')
    assert collect(tmp_path,used_limit=60,usage=usage)==[]
    assert old.exists()


def test_stops_at_threshold_and_never_follows_foreign_symlink(tmp_path):
    root=tmp_path/'data';old=make(root,'Sessions','old',1);make(root,'Sessions','new',2)
    foreign=tmp_path/'examples';foreign.mkdir();(foreign/'video.mp4').write_bytes(b'keep')
    (root/'Sessions'/'foreign').symlink_to(foreign,target_is_directory=True)
    usage=lambda _:Usage(100,40 if not old.exists() else 80,20)
    assert collect(root,used_limit=60,usage=usage,now=lambda:10000)==['Sessions/old']
    assert (foreign/'video.mp4').read_bytes()==b'keep'
    assert collect(root,used_limit=60,usage=usage)==[]


def test_worker_lock_prevents_cleanup(tmp_path):
    import fcntl
    old=make(tmp_path,'Sessions','old',1);make(tmp_path,'Sessions','new',2)
    with (old/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert collect(tmp_path,used_limit=60,usage=lambda _:Usage(100,80,20))==[]
    assert old.exists()
