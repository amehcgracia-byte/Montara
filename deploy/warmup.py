"""Explicitly prepare persistent CPU Whisper assets before the first user test.

Downloads the chosen existing Whisper model; no LLM/provider key, no paid API.
Run with no user jobs active: python -m deploy.warmup --data /data
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import time


def prepare(data, model='small'):
    data = Path(data).expanduser().resolve()
    forbidden = (Path.home() / 'ZuckerVideos').resolve()
    if data == forbidden or data.is_relative_to(forbidden):
        raise ValueError('Choose a separate Montara data folder.')
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
    target = data / 'Cache/WhisperModels' / model
    started = time.monotonic()
    download_model(model, output_dir=str(target), cache_dir=str(data / 'Cache/huggingface/hub'))
    downloaded = time.monotonic()
    whisper = WhisperModel(str(target), device='cpu', compute_type='int8', cpu_threads=2,
                           local_files_only=True)
    loaded = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='whisper-check-', dir=data) as folder:
        wav = Path(folder) / 'silence.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'lavfi',
                        '-i', 'anullsrc=r=16000:cl=mono', '-t', '1', str(wav)], check=True, timeout=30)
        segments, _ = whisper.transcribe(str(wav), language='en', beam_size=1, vad_filter=False)
        list(segments)  # Decode actually runs lazily; this is a smoke test, not an accuracy test.
    checked = time.monotonic()
    digest = hashlib.sha256()
    with (target / 'model.bin').open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    report = {'model': model, 'model_sha256': digest.hexdigest(), 'device': 'cpu', 'compute_type': 'int8',
              'asset_download_or_cache_check_seconds': round(downloaded - started, 3),
              'model_load_seconds': round(loaded - downloaded, 3),
              'silence_decode_smoke_seconds_including_fixture': round(checked - loaded, 3),
              'not_an_accuracy_or_product_latency_benchmark': True}
    (data / 'whisper-warmup.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--model', choices=['tiny', 'base', 'small'], default='small')
    args = parser.parse_args()
    print(json.dumps(prepare(args.data, args.model), indent=2))
