import json
import sys
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_media.proxies import prepare, resolve_recipe


def test_local_proxy_preserves_time_and_resolves_to_unchanged_original(tmp_path):
    original = tmp_path / 'original.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=1920x1080:rate=30:duration=2', '-c:v', 'libx264',
                    '-preset', 'ultrafast', str(original)], check=True)
    cache = tmp_path / 'cache'
    record = prepare(original, cache)
    public = record['public']
    assert public['duration'] == pytest.approx(2, abs=.04)
    assert public['proxy_duration'] == pytest.approx(public['duration'], abs=.04)
    assert public['width'] <= 960
    assert public['proxy_bytes'] < original.stat().st_size
    assert str(tmp_path) not in json.dumps(public)
    assert 'original.mp4' not in json.dumps(public)
    assert prepare(original, cache)['source_id'] == record['source_id']
    recipe = {'clips': [{'source_id': record['source_id'], 'start': .5, 'end': 1.5}]}
    assert resolve_recipe(recipe, cache)[0]['original'] == str(original)
    original.touch()
    with pytest.raises(ValueError, match='original changed'):
        resolve_recipe(recipe, cache)
