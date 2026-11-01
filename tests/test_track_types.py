"""Track types the person chooses: validation, mixer roles, stereo sides, music never muted as noise."""
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import track_types
from mixer_adapter.single_song import SingleSongMix


def test_validate_keys_by_track_and_drops_unknown_types():
    types = track_types.validate({'Bass.wav.opus': {'type': 'bass', 'chosen': True, 'side': 'X'},
                                  'Robi.wav': {'type': 'podcast_voice'}, 'Bad.wav': {'type': 'kazoo'}, 'x': 'bass'})
    assert types == {'bass': {'type': 'bass', 'side': '', 'chosen': True},
                     'robi': {'type': 'podcast_voice', 'side': '', 'chosen': False}}
    files = track_types.for_files(types, ['/s/Bass.wav', '/s/Robi.wav', '/s/Keys.wav'])
    assert set(files) == {'Bass.wav', 'Robi.wav'}
    assert track_types.noise_exempt(files) == {'Bass.wav'}  # only what the person chose


def test_roles_and_stereo_sides():
    types = {'Keys L.wav': {'type': 'keys', 'side': 'L', 'chosen': True},
             'Keys R.wav': {'type': 'keys', 'side': 'R', 'chosen': True},
             'Narr.wav': {'type': 'narration', 'side': '', 'chosen': True}}
    assert track_types.mixer_roles(types) == {'Keys L.wav': 'keys_l', 'Keys R.wav': 'keys_r', 'Narr.wav': 'vocal'}
    assert track_types.stereo_sides(types) == {'Keys L.wav': 'L', 'Keys R.wav': 'R'}


def test_page_list_matches_server_list():
    js = (ROOT / 'web' / 'track-types.js').read_text()
    block = js[js.index('const TYPES = ['):js.index('];', js.index('const TYPES = ['))]
    assert set(re.findall(r"\['([a-z_]+)',", block)) == set(track_types.TYPES)


def test_single_song_mixer_uses_the_chosen_role_and_side(tmp_path):
    tracks = tmp_path / 'tracks'; tracks.mkdir()
    sr = 22050
    tone = (.1 * np.sin(2 * np.pi * 220 * np.arange(sr * 2) / sr)).astype('float32')
    for name in ('Robi.wav', 'Novation.wav'):
        sf.write(tracks / name, tone, sr, subtype='FLOAT')
    types = track_types.validate({'Robi.wav': {'type': 'bass', 'chosen': True}, 'Novation.wav': {'type': 'strings', 'side': 'R', 'chosen': True}})
    job = SingleSongMix(tracks, tmp_path / 'job', track_types=types)
    state = job._register()
    roles = {s.path.name: s.role for s in state['stems']}
    assert roles == {'Robi.wav': 'bass', 'Novation.wav': 'synth'}
    assert job.pipeline.NOISE_EXEMPT_STEMS == {'Robi.wav', 'Novation.wav'}
    assert job.pipeline.enforced_pan('synth', 'Novation') == 1.0
    # Another job without types must not inherit these globals.
    other = SingleSongMix(tracks, tmp_path / 'other')
    other._register()
    assert other.pipeline.NOISE_EXEMPT_STEMS == set() and other.pipeline.STEREO_SIDES == {}


def test_every_type_has_a_dictionary_entry_with_the_same_role():
    sys.path.insert(0, str(ROOT / 'mixer'))
    import instrument_dictionary
    for key, (_label, role) in track_types.TYPES.items():
        assert instrument_dictionary.INSTRUMENTS[key]['role'] == role, key


def test_the_mixer_gets_the_instrument_of_each_track(tmp_path):
    tracks = tmp_path / 'tracks'; tracks.mkdir()
    sr = 44100
    sf.write(tracks / 'Host.wav', (.1 * np.sin(np.arange(sr) / 5)).astype('float32'), sr, subtype='FLOAT')
    job = SingleSongMix(tracks, tmp_path / 'job', track_types=track_types.validate({'Host.wav': {'type': 'podcast_voice', 'chosen': True}}))
    job._register()
    assert job.pipeline.STEM_INSTRUMENTS == {'Host.wav': 'podcast_voice'}
    assert job.pipeline.role_eq_bands('vocal', name='Host.wav')[0][2] == 80
