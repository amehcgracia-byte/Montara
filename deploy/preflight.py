"""Offline server readiness checks; optional tiny CPU render, no account needed.

    python -m deploy.preflight --data /data --server --smoke --output report.json

The report never includes environment values, passwords or user file paths.
This is an installation check, not an application E2E or capacity benchmark.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('flask', 'numpy', 'scipy', 'numba', 'librosa',
            'opencv-python-headless', 'faster-whisper', 'ctranslate2',
            'soundfile', 'pyloudnorm', 'matchering', 'yt-dlp', 'yt-dlp-ejs')


def container_limits():
    """cgroup v2 limits, not guessed from the host's CPU count or RAM."""
    result = {}
    try:
        memory = Path('/sys/fs/cgroup/memory.max').read_text().strip()
        result['memory_limit_bytes'] = int(memory) if memory != 'max' else None
    except (OSError, ValueError):
        result['memory_limit_bytes'] = None
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        result['cpu_quota_cores'] = int(quota) / int(period) if quota != 'max' else None
    except (OSError, ValueError, ZeroDivisionError):
        result['cpu_quota_cores'] = None
    return result


def command(argv, timeout=15):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, ''


def collect(data, *, server=False, smoke=False, min_free_gib=5):
    checks = []

    def check(name, ok, detail=None, required=True):
        checks.append(dict(name=name, status='ok' if ok else ('failed' if required else 'pending'),
                           **({'detail': detail} if detail is not None else {})))

    data = Path(data).expanduser().resolve()
    # Never inspect/create the desktop Editor's private data, even by accident.
    forbidden = (Path.home() / 'ZuckerVideos').resolve()
    if data == forbidden or data.is_relative_to(forbidden):
        return {'ready': False, 'checks': [{'name': 'data_isolation', 'status': 'failed'}]}
    check('linux', platform.system() == 'Linux', required=server)
    versions = {}
    for name in (*PACKAGES, *(('gunicorn',) if server else ())):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            check('package:' + name, False)
    check('engine_sources', (ROOT / 'engine/server/api.py').is_file())
    check('mixer_sources', (ROOT / 'mixer/jam_mix_pipeline.py').is_file())
    from app import SAMPLE_SETS
    expected = set().union(*map(set, SAMPLE_SETS.values()))
    expected.update({'show/manifest.json', 'show/podcast/setup.json', 'show/storytelling/kit.json'})
    missing = sorted(name for name in expected if not (ROOT / 'tests/fixtures' / name).is_file())
    check('example_sources', not missing, {'missing': missing})
    check('private_access', len(os.environ.get('MONTARA_PREVIEW_PASSWORD', '')) >= 16,
          required=server)
    try:
        data.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=data) as probe:
            probe.write(b'montara-preflight'); probe.flush()
        free = shutil.disk_usage(data).free
        check('persistent_data_writable', True)
        check('disk_headroom', free >= min_free_gib * 2**30,
              {'free_bytes': free, 'required_bytes': int(min_free_gib * 2**30)})
    except OSError:
        check('persistent_data_writable', False)
    for tool in ('ffmpeg', 'ffprobe'):
        ok, output = command([tool, '-version'])
        check(tool, ok, output.splitlines()[0] if ok else 'not available')
    from deploy.download_runtime import DENO, EJS, YTDLP
    ok, output = command(['deno', '--version'])
    check('download_runtime', ok and output.startswith('deno ' + DENO + ' ')
          and versions.get('yt-dlp') == YTDLP and versions.get('yt-dlp-ejs') == EJS,
          {'deno': output.splitlines()[0] if ok else 'not available',
           'yt-dlp': versions.get('yt-dlp'), 'ejs': versions.get('yt-dlp-ejs')}, required=server)
    ok, output = command(['fc-match', '-f', '%{family}', 'DejaVu Sans'])
    check('caption_font', ok and 'DejaVu Sans' in output)
    if smoke and not any(c['name'] in {'persistent_data_writable', 'ffmpeg', 'ffprobe'}
                         and c['status'] == 'failed' for c in checks):
        with tempfile.TemporaryDirectory(prefix='montara-check-', dir=data) as temporary:
            target = Path(temporary) / 'probe.mp4'
            started = time.monotonic()
            ok, _ = command(['ffmpeg', '-v', 'error', '-nostdin', '-y',
                             '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=25:duration=1',
                             '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=1',
                             '-vf', "drawtext=font='DejaVu Sans':text='Montara':x=8:y=8:fontsize=20",
                             '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                             '-c:a', 'aac', '-shortest', str(target)], timeout=60)
            elapsed = time.monotonic() - started
            probed, metadata = command(['ffprobe', '-v', 'error', '-show_streams',
                                         '-show_format', '-of', 'json', str(target)]) if ok else (False, '')
            try:
                result = json.loads(metadata) if probed else {}
                streams = result.get('streams', [])
                valid = (any(s.get('codec_name') == 'h264' and s.get('width') == 320 for s in streams)
                         and any(s.get('codec_name') == 'aac' for s in streams)
                         and .9 <= float(result.get('format', {}).get('duration', 0)) <= 1.2)
            except (ValueError, TypeError):
                valid = False
            decoded, _ = command(['ffmpeg', '-v', 'error', '-nostdin', '-xerror',
                                    '-i', str(target), '-f', 'null', '-']) if valid else (False, '')
            check('cpu_video_audio_caption_export', ok and valid and decoded,
                  {'fixture': 'synthetic 1s 320x180 25fps + sine',
                   'encode_seconds': round(elapsed, 3),
                   'not_a_product_render_benchmark': True})
    def revision(name):
        value = os.environ.get('MONTARA_' + name.upper() + '_SHA', '')
        return value if re.fullmatch('[a-f0-9]{40}', value) else 'unknown'

    return {'ready': not any(c['status'] == 'failed' for c in checks),
            'system': {'os': platform.system(), 'architecture': platform.machine(),
                       'host_logical_cpus': os.cpu_count(), 'python': platform.python_version(),
                       'container_limits': container_limits()},
            'build': {name: revision(name)
                      for name in ('build', 'engine', 'mixer')},
            'packages': versions, 'checks': checks,
            'deferred': ['Abacus credentials and real model calls', 'GPU and CorridorKey',
                         'fresh YouTube access', 'real 30GB files and customer concurrency',
                         'macOS Vision features need a selected portable replacement']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path(os.environ.get('MONTARA_DATA', Path.home() / 'MontaraData')))
    parser.add_argument('--server', action='store_true', help='Require Linux, private access and exact download runtime.')
    parser.add_argument('--smoke', action='store_true', help='Create, inspect, decode and remove a one-second synthetic export.')
    parser.add_argument('--min-free-gib', type=float, default=5)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.min_free_gib < 0 or not args.min_free_gib < float('inf'):
        parser.error('Free-space requirement must be finite and non-negative.')
    report = collect(args.data, server=args.server, smoke=args.smoke, min_free_gib=args.min_free_gib)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n')
    print(text)
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
