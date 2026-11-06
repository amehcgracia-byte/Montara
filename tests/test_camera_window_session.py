"""Video-mode indexes microphones but never segments/mixes the entire jam."""
import json
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf

from mixer_adapter.session import execute, read, save
from test_full_session import client


def test_video_mode_flag_is_explicit_and_validated(tmp_path, monkeypatch):
    import full_session
    monkeypatch.setattr(full_session, 'launch', lambda *_: None)
    source=tmp_path/'data'/'mic.wav';source.parent.mkdir();source.write_bytes(b'test')
    c=client(tmp_path)
    assert c.post('/montara/session',json={'tracks':[str(source)],'for_video':'yes'}).status_code==400
    for flag in (False,True):
        response=c.post('/montara/session',json={'tracks':[str(source)],'for_video':flag})
        assert response.status_code==202 and response.json['video_excerpt'] is flag


def test_video_guide_reuses_decode_for_waveform_and_skips_all_song_detection(tmp_path, monkeypatch):
    from mixer_adapter import single_song

    @dataclass
    class Stem:
        path:Path
        offset_seconds:float
        duration:float=6
        samplerate:int=8000
        channels:int=1
        role:str='instrument'

    work=tmp_path/'job';(work/'tracks').mkdir(parents=True)
    stems=[]
    for name,offset,freq in [('bass',5,80),('keys',7,160)]:
        path=work/'tracks'/f'{name}.wav'
        sf.write(path,.1*np.sin(2*np.pi*freq*np.arange(48000)/8000),8000)
        stems.append(Stem(path,offset))
    def forbidden(*_):
        raise AssertionError('Video extraction must not detect all songs in the jam')
    pipeline=SimpleNamespace(configure_detection_cache=lambda *_:None,
        configure_detection_profile=lambda *_:None,inspect_stems=lambda *_:stems,
        ensure_detection_cache=forbidden,detect_segments=forbidden)
    monkeypatch.setattr(single_song,'_load_mixer',lambda *_:(None,pipeline))
    save(work/'session.json',dict(id='a'*12,status='detecting',video_excerpt=True))
    execute(work,'detect')
    result=read(work)
    assert result['status']=='review' and result['duration']==8
    assert [t['offset'] for t in result['tracks']]==[0,2]
    assert result['detection']['id']=='camera-audio-window'
    assert not result['songs'][0]['selected']
    assert not (work/'extras.log').exists() and not (work/'songs').exists()
    assert (work/'listen-all.webm').stat().st_size>0
    waveform=json.loads((work/'waveform.json').read_text())
    assert waveform['source']=='video-sync-guide' and len(waveform['peaks'])==32
    assert any(waveform['peaks'])


def test_video_index_reports_listening_progress(tmp_path):
    c=client(tmp_path);work=tmp_path/'data'/'Sessions'/('a'*12);work.mkdir(parents=True)
    save(work/'session.json',dict(id='a'*12,status='detecting',video_excerpt=True,
                                 started_at=time.time(),progress={'progress':0}))
    (work/'listen.progress').write_text('42')
    assert c.get('/montara/session/'+'a'*12).json['progress']['progress']==42
