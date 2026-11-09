"""The next export reuses the exact completed 360 source, without copying it."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'companion'), str(ROOT / 'engine')]
from local_video import retain_spherical_cache


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='requires FFmpeg')
def test_two_render_jobs_share_the_engine_keyed_360_intermediate(tmp_path, monkeypatch):
    from core.project import Project
    from core.stages import export

    src = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x160:r=30:d=4',
                    '-c:v','libx264','-preset','ultrafast',str(src)], check=True)
    info = {'source_path': str(src), 'probe': {'projection': 'equirect', 'duration': 4}}
    monkeypatch.setattr(export, 'SPHERICAL_EXPORT_PROXY_WIDTH', 320)
    monkeypatch.setattr(export, 'SPHERICAL_EXPORT_PROXY_HEIGHT', 160)
    monkeypatch.setattr('local_video.SPHERICAL_FREE_RESERVE', 0)
    cache = tmp_path/'shared'
    project = Project(tmp_path/'one', {})
    monkeypatch.setenv('ZUCKER_GLOBAL_CACHE', str(tmp_path/'job-one'))
    target = export._spherical_export_proxy_target(project, info, {})
    start = time.perf_counter()
    export._spherical_export_source_info(project, info, {})
    cold = time.perf_counter()-start
    assert retain_spherical_cache(cache, {target}) == 1
    assert (cache/target.name).samefile(target)
    shutil.rmtree(target.parent)
    monkeypatch.setenv('ZUCKER_GLOBAL_CACHE', str(tmp_path/'job-two'))
    target = export._spherical_export_proxy_target(project, info, {})
    def no_encode(*args, **kwargs):
        pytest.fail('The completed 360 cache should avoid FFmpeg')
    monkeypatch.setattr(export, '_run_ffmpeg_progress', no_encode)
    start = time.perf_counter()
    assert retain_spherical_cache(cache, {target}, restore=True) == 1
    export._spherical_export_source_info(project, info, {})
    warm = time.perf_counter()-start
    assert (cache/target.name).samefile(target)
    src.touch()
    changed = export._spherical_export_proxy_target(project, info, {})
    assert changed != target
    assert retain_spherical_cache(cache, {changed}, restore=True) == 0
    print(f'360 preparation: cold={cold:.4f}s warm={warm:.4f}s')


def test_partial_and_over_budget_cache_are_not_retained(tmp_path, monkeypatch):
    shared = tmp_path/'shared'
    partial = tmp_path/('equirect-'+'a'*24+'.tmp.mp4')
    complete = tmp_path/('equirect-'+'b'*24+'.mp4')
    partial.write_bytes(b'partial')
    complete.write_bytes(b'complete')
    monkeypatch.setattr('local_video.SPHERICAL_CACHE_LIMIT', 1)
    monkeypatch.setattr('local_video.SPHERICAL_FREE_RESERVE', 0)
    assert retain_spherical_cache(shared, {partial, complete}) == 0
    assert not list(shared.iterdir())
