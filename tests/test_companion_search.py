"""The companion finds originals on any disk, quickly, remembers where they were, and makes small versions."""
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'companion'))
import companion


def described(path):
    raw = path.read_bytes()
    return path.name, len(raw), hashlib.sha256(raw[:65536] + raw[max(0, len(raw) - 65536):]).hexdigest()


@pytest.fixture
def search(tmp_path, monkeypatch):
    home = tmp_path / 'home'; home.mkdir()
    volumes = tmp_path / 'Volumes'; volumes.mkdir()
    monkeypatch.setattr(companion.Path, 'home', lambda: home)
    monkeypatch.setattr(companion, 'VOLUMES', volumes)
    monkeypatch.setattr(companion, 'PLACES', tmp_path / 'places.json')
    monkeypatch.setattr(companion.sys, 'platform', 'linux')   # no Spotlight here
    monkeypatch.delenv('MONTARA_COMPANION_ROOTS', raising=False)
    companion.sources.clear(); companion.walked_files.clear(); companion.walkers.clear()
    return volumes


def test_the_link_to_the_system_disk_is_not_searched(search, tmp_path):
    (search / 'Macintosh HD').symlink_to(tmp_path)
    (search / '.timemachine').mkdir()
    (search / 'ExternalDisk').mkdir()
    roots = companion.search_roots()
    assert search / 'ExternalDisk' in roots and search / 'Macintosh HD' not in roots and search / '.timemachine' not in roots


def test_a_slow_disk_does_not_hold_up_the_others(search, monkeypatch):
    slow, fast = search / 'AAA slow', search / 'ExternalDisk'
    slow.mkdir(); (fast / 'deep' / 'er').mkdir(parents=True)
    clip = fast / 'deep' / 'er' / 'clip.MP4'; clip.write_bytes(b'video' * 100)
    release = threading.Event()
    real_walk = os.walk

    def walk(root):
        if Path(root) == slow:
            release.wait(30)
        return real_walk(root)

    monkeypatch.setattr(companion.os, 'walk', walk)
    started = time.monotonic()
    try:
        assert companion.locate(*described(clip)) == clip
        assert time.monotonic() - started < 5
    finally:
        release.set()


def test_the_folder_of_a_found_file_survives_a_restart(search, monkeypatch):
    folder = search / 'ExternalDisk' / 'session'; folder.mkdir(parents=True)
    first, second = folder / 'one.mov', folder / 'two.mov'
    first.write_bytes(b'one'); second.write_bytes(b'two')
    assert companion.locate(*described(first)) == first
    companion.sources.clear(); companion.walked_files.clear()   # the companion restarted
    monkeypatch.setattr(companion, 'search_roots', lambda: [])  # and no walk can help
    assert companion.locate(*described(second)) == second


def test_a_file_that_is_nowhere_is_reported_when_the_walks_end(search):
    (search / 'ExternalDisk').mkdir()
    started = time.monotonic()
    assert companion.locate('missing.mov', 10, 'f' * 64) is None
    assert time.monotonic() - started < 5


PLAN = dict(fps=30, hdr=False, duration=2.0, codec='h264', size=[3840, 2160], pix_fmt='yuv420p', rotation=0)


def picture_filters(command):
    return command[command.index('-vf') + 1]


@pytest.mark.parametrize('rotation, turn', [(0, None), (90, 'transpose_vt=dir=cclock'), (180, 'transpose_vt=dir=reversal'), (270, 'transpose_vt=dir=clock')])
def test_the_hardware_way_turns_the_picture_as_the_file_says(monkeypatch, tmp_path, rotation, turn):
    monkeypatch.setattr(companion, 'HW_H264', True); monkeypatch.setattr(companion, 'HW_SCALE', True)
    fast, safe = companion.proxy_commands(tmp_path / 'a.mov', tmp_path / 'b.mp4', {**PLAN, 'rotation': rotation})
    assert 'scale_vt' in picture_filters(fast) and 'scale_vt' not in picture_filters(safe)
    assert (turn in picture_filters(fast)) if turn else 'transpose' not in picture_filters(fast)


@pytest.mark.parametrize('changes', [dict(hdr=True), dict(pix_fmt='yuv420p10le'), dict(pix_fmt='yuv422p10le'), dict(codec='prores')])
def test_what_the_chip_cannot_take_goes_the_software_way(monkeypatch, tmp_path, changes):
    monkeypatch.setattr(companion, 'HW_H264', True); monkeypatch.setattr(companion, 'HW_SCALE', True)
    commands = companion.proxy_commands(tmp_path / 'a.mov', tmp_path / 'b.mp4', {**PLAN, **changes})
    assert len(commands) == 1 and 'scale_vt' not in picture_filters(commands[0])


def test_a_failing_fast_way_falls_back_to_the_safe_one(tmp_path, monkeypatch):
    source = tmp_path / 'clip.mov'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1280x720:rate=25:duration=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)], check=True)
    monkeypatch.setattr(companion, 'CACHE', tmp_path / 'cache'); (tmp_path / 'cache').mkdir()
    real = companion.proxy_commands
    monkeypatch.setattr(companion, 'proxy_commands', lambda *args: [['ffmpeg', '-v', 'error', '-i', str(tmp_path / 'nothing.mov')], *real(*args)[-1:]])
    key = 'a' * 24
    companion.sources[key] = source; companion.jobs[key] = dict(status='working', progress=0.0)
    companion.make_proxy(key)
    assert companion.jobs[key]['status'] == 'ready' and companion.output_path(key).stat().st_size


@pytest.mark.skipif(not companion.HW_SCALE, reason='only on a Mac with the VideoToolbox filters')
@pytest.mark.parametrize('rotation', [0, 90, -90, 180])
def test_the_hardware_way_gives_the_same_picture_as_the_software_way(tmp_path, rotation):
    plain = tmp_path / 'plain.mp4'; source = tmp_path / 'turned.mov'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30:duration=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(plain)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-display_rotation', str(rotation), '-i', str(plain), '-c', 'copy', str(source)], check=True)
    p = companion.plan(companion.probe(source))
    assert p['rotation'] == rotation % 360
    fast, safe = tmp_path / 'fast.mp4', tmp_path / 'safe.mp4'
    hardware, software = companion.proxy_commands(source, fast, p)
    subprocess.run(hardware, check=True, capture_output=True)
    subprocess.run([*software[:-1], str(safe)], check=True, capture_output=True)
    sizes = [json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-select_streams', 'v:0', '-of', 'json', str(f)]))['streams'][0] for f in (fast, safe)]
    assert (sizes[0]['width'], sizes[0]['height']) == (sizes[1]['width'], sizes[1]['height'])
    assert not any('rotation' in d for d in sizes[0].get('side_data_list', []))
    assert sizes[0]['color_space'] == 'bt709' and sizes[0]['pix_fmt'] == 'yuv420p'
    report = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(fast), '-i', str(safe), '-lavfi', 'psnr', '-f', 'null', '-'], capture_output=True, text=True).stderr
    assert float(report.rsplit('average:', 1)[1].split()[0]) > 15   # right way up about 24 dB here, the wrong way up about 5
