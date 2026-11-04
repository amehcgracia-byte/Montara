from types import SimpleNamespace
from pathlib import Path
import numpy as np
from mixer_adapter.single_song import SingleSongMix


def test_reuses_mix_analysis_does_not_decode_and_preserves_exact_instrument_types():
    job=SingleSongMix.__new__(SingleSongMix)
    calls=[]
    def load(path):
        calls.append(path)
        return {'segment_envelopes':{'sax.wav':np.array([0.,.1,.2]),'flute.wav':np.ones(3),
                                    'piano.wav':np.array([.1,.2,.1]),'muted.wav':np.ones(3)}}
    job.pipeline=SimpleNamespace(load_analysis_cache=load)
    job.track_types={'sax':{'type':'sax'},'flute':{'type':'flute'},'piano':{'type':'keys'}}
    tracks=[{'file':file,'role':role,'active':True,'mute':False} for file,role in
            [('sax.wav','sax'),('flute.wav','horn'),('piano.wav','keys'),('muted.wav','bass')]]
    tracks[-1]['mute']=True
    evidence=job._instrument_activity({'analysis_cache_path':'analysis.npz'},tracks)
    assert calls==[Path('analysis.npz')]
    assert [t['role'] for t in evidence['tracks']]==['sax','keys']
    assert evidence['tracks'][0]['db']==[-120.,-20.,-14.]
    assert evidence['interval_sec']==1


def test_missing_analysis_stays_unknown():
    job=SingleSongMix.__new__(SingleSongMix)
    job.pipeline=SimpleNamespace(load_analysis_cache=lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    assert job._instrument_activity({'analysis_cache_path':'absent'},[]) is None
