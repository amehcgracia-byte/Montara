"""Real FFmpeg: finish a mixed stereo signal without stem analysis/rebalancing."""
import json
import subprocess
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from flask import Flask
from mastering import register_mastering


def make_app(tmp_path):
    app=Flask(__name__)
    register_mastering(app,tmp_path/'data',tmp_path/'fixtures')
    return app.test_client()


def wait(client, key):
    for _ in range(300):
        job=client.get(f'/montara/master/{key}').get_json()
        if job['status'] in {'done','failed','cancelled'}:return job
        time.sleep(.05)
    raise AssertionError('Mastering did not finish')


def test_stereo_finished_mix_preserves_balance_duration_and_checks_encoded_peaks(tmp_path):
    sr=48000;t=np.arange(sr*8)/sr
    left=.85*np.sin(2*np.pi*330*t)
    source=tmp_path/'finished.wav';sf.write(source,np.column_stack([left,left*.5]),sr,subtype='FLOAT')
    client=make_app(tmp_path)
    response=client.post('/montara/master',json={'tracks':[str(source)]})
    assert response.status_code==202
    job=wait(client,response.get_json()['id'])
    assert job['status']=='done',job
    assert job['after']['true_peak_db']<=-1
    assert abs(job['after']['lufs']+15)<1
    result=client.get(f"/montara/master/{job['id']}/result")
    assert result.status_code==200 and result.mimetype=='audio/mpeg'
    output=tmp_path/'out.mp3';output.write_bytes(result.data)
    decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-f','f32le','-acodec','pcm_f32le','-'])
    audio=np.frombuffer(decoded,dtype=np.float32).reshape(-1,2)
    assert abs(len(audio)/sr-8)<.1
    rms=np.sqrt(np.mean(audio.astype(np.float64)**2,axis=0))
    assert abs(20*np.log10(rms[0]/rms[1])-6.0206)<.15
    tags=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(output)]))['format'].get('tags',{})
    assert not {'title','artist','album','track'}.intersection(k.lower() for k in tags)
    assert not list((tmp_path/'data'/'Mastering').glob('*/master.wav'))
    assert source.is_file()
    (tmp_path/'data'/'Mastering'/job['id']/'master.mp3').unlink()
    assert client.get(f"/montara/master/{job['id']}/result").status_code==404


def test_mastering_rejects_separate_stems_and_foreign_remote_paths(tmp_path, monkeypatch):
    a=tmp_path/'a.wav';b=tmp_path/'b.wav'
    sf.write(a,np.ones(4800)*.01,48000);sf.write(b,np.ones(4800)*.02,48000)
    client=make_app(tmp_path)
    assert client.post('/montara/master',json={'tracks':[str(a),str(b)]}).status_code==400
    monkeypatch.setenv('MONTARA_SESSION_TOKEN','private-test')
    assert client.post('/montara/master',json={'tracks':[str(a)]}).status_code==400


def test_silent_input_fails_without_releasing_a_master(tmp_path):
    source=tmp_path/'silent.wav';sf.write(source,np.zeros(48000),48000)
    client=make_app(tmp_path);started=client.post('/montara/master',json={'tracks':[str(source)]}).get_json()
    job=wait(client,started['id'])
    assert job['status']=='failed' and 'No measurable audio' in job['error']
    assert client.get(f"/montara/master/{job['id']}/result").status_code==409


def test_cancel_stops_processing_and_keeps_original(tmp_path):
    source=tmp_path/'long.wav'
    sr=48000;t=np.arange(sr*60)/sr
    sf.write(source,.1*np.sin(2*np.pi*220*t),sr)
    client=make_app(tmp_path)
    key=client.post('/montara/master',json={'tracks':[str(source)]}).get_json()['id']
    assert client.delete(f'/montara/master/{key}').status_code==200
    job=wait(client,key)
    assert job['status']=='cancelled'
    assert not list((tmp_path/'data'/'Mastering').glob('*/master.wav'))
    assert client.get(f'/montara/master/{key}/result').status_code==409
    assert source.is_file()
