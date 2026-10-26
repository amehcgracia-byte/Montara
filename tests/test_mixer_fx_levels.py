"""Regression: switching FX on must not change a track's channel/pan gain."""
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mixer_adapter.single_song import SingleSongMix


@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("effect", ["reverb", "delay"])
def test_effect_preserves_dry_level_and_channel_layout(tmp_path, channels, effect):
    tracks = tmp_path / "tracks"
    tracks.mkdir()
    sr = 44100
    tone = (.1 * np.sin(2 * np.pi * 440 * np.arange(sr) / sr)).astype("float32")
    dry = tone[:, None] if channels == 1 else np.column_stack((tone, .3 * tone))
    sf.write(tracks / "vocal.wav", dry, sr, subtype="FLOAT")
    job = SingleSongMix(tracks, tmp_path / "job")
    job._register()
    wet, _ = sf.read(job.effect_track("vocal.wav", effect), always_2d=True)
    assert wet.shape == dry.shape
    stem = job._effect_stems({"vocal.wav": {effect: 1e-7}})[0]
    audio, _ = sf.read(stem.path, always_2d=True)
    assert stem.channels == channels
    before = job.pipeline.apply_stereo_pan(dry[:, 0] if channels == 1 else dry, .25)
    after = job.pipeline.apply_stereo_pan(audio[:, 0] if channels == 1 else audio, .25)
    delta_db = 20 * np.log10(np.sqrt(np.mean(after ** 2)) / np.sqrt(np.mean(before ** 2)))
    assert abs(delta_db) < .001
    stem = job._effect_stems({"vocal.wav": {effect: .65}})[0]
    audio, _ = sf.read(stem.path, always_2d=True)
    np.testing.assert_allclose(audio, dry + .65 * wet, atol=1e-7)
