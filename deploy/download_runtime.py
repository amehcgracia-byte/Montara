"""Install the tested YouTube runtime in the private Linux preview only.

No browser credentials, remote token providers or CAPTCHA services are used.
"""
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/vercel/sandbox/download-runtime')
YTDLP = '2026.10.21'
EJS = '0.8.0'
DENO = '2.5.6'


def ensure_runtime():
    def version(name):
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None

    if version('yt-dlp') != YTDLP or version('yt-dlp-ejs') != EJS:
        subprocess.run(['uv', 'pip', 'install', '--python', sys.executable,
                        f'yt-dlp[default]=={YTDLP}', f'yt-dlp-ejs=={EJS}'],
                       check=True, timeout=180)
    deno = ROOT / 'node_modules/.bin/deno'
    if not deno.exists():
        ROOT.mkdir(parents=True, exist_ok=True)
        subprocess.run(['npm', 'install', '--prefix', str(ROOT), '--no-audit',
                        '--no-fund', f'deno@{DENO}'], check=True, timeout=180)
    result = subprocess.run([str(deno), '--version'], capture_output=True,
                            text=True, check=True, timeout=15)
    if not result.stdout.startswith(f'deno {DENO} '):
        raise RuntimeError('Unexpected download JavaScript runtime version')
    print(f'Download runtime ready: yt-dlp {YTDLP}, EJS {EJS}, Deno {DENO}')


def enable_runtime():
    """Inherited by all engine, reference and Push downloader calls."""
    directory = str(ROOT / 'node_modules/.bin')
    paths = os.environ.get('PATH', '').split(os.pathsep)
    if directory not in paths:
        os.environ['PATH'] = os.pathsep.join([directory, *paths])


if __name__ == '__main__':
    ensure_runtime()
