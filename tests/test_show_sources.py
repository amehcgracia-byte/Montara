from pathlib import Path
from flask import Flask
from show_samples import register_show_samples,show_inputs


def test_show_inputs_are_separate_files_with_distinct_identity():
    root=Path(__file__).parent/'fixtures'
    pod=show_inputs(root,'podcast')['podcast']
    story=show_inputs(root,'storytelling')['story']
    assert len(pod['people'])==5 and len(pod['cameras'])==4
    assert len(story['clips'])==10
    paths=[p['mic'] for p in pod['people']]+[c['path'] for c in pod['cameras']]+[story['narration']['path']]+[c['path'] for c in story['clips']]
    assert len(set(paths))==20 and all(Path(p).is_file() for p in paths)


def test_source_preview_before_project_supports_range_and_denies_other_paths(tmp_path):
    fixture=tmp_path/'fixtures';fixture.mkdir()
    source=fixture/'clip.mp4';source.write_bytes(b'0123456789')
    data=tmp_path/'data';data.mkdir();mic=data/'mic.wav';mic.write_bytes(b'RIFF audio')
    outside=tmp_path/'other.mp4';outside.write_bytes(b'private')
    secret=data/'notes.txt';secret.write_text('not media')
    app=Flask(__name__);register_show_samples(app,fixture,True,data)
    client=app.test_client()
    result=client.get('/montara/show/input',query_string={'path':str(source)},headers={'Range':'bytes=2-5'})
    assert result.status_code==206 and result.data==b'2345'
    assert client.get('/montara/show/input',query_string={'path':str(mic)}).status_code==200
    assert client.get('/montara/show/input',query_string={'path':str(outside)}).status_code==404
    assert client.get('/montara/show/input',query_string={'path':str(secret)}).status_code==404
