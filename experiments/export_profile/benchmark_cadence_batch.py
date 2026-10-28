"""Isolated FFprobe cadence-window experiment; never touches the Zucker engine."""
from __future__ import annotations
import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path


def run(video: Path, starts: list[float], duration: float, repetitions: int = 3):
    base = ['ffprobe', '-v', 'error', '-select_streams', 'v:0']
    tail = ['-show_entries', 'frame=best_effort_timestamp_time', '-of', 'csv=p=0', str(video)]
    specs = [f'{t}%+{duration}' for t in starts]

    def probe(interval):
        return subprocess.run(
            base + ['-read_intervals', interval] + tail,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()

    individual, batch, identical = [], [], []
    for _ in range(repetitions):
        started = time.perf_counter()
        separate = [line for interval in specs for line in probe(interval)]
        individual.append(time.perf_counter() - started)
        started = time.perf_counter()
        combined = probe(','.join(specs))
        batch.append(time.perf_counter() - started)
        identical.append(separate == combined)
    return {
        'windows': len(starts), 'duration_per_window': duration,
        'repetitions': repetitions,
        'individual_seconds': [round(t, 4) for t in individual],
        'batch_seconds': [round(t, 4) for t in batch],
        'individual_median_s': round(statistics.median(individual), 4),
        'batch_median_s': round(statistics.median(batch), 4),
        'all_timestamps_match': all(identical),
        'timestamp_comparisons': identical,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('video', type=Path)
    parser.add_argument('--starts', default='0,2.8,7,14,21,25.2,28')
    parser.add_argument('--duration', type=float, default=2)
    parser.add_argument('--runs', type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1 or args.duration <= 0:
        parser.error('runs and duration must be positive')
    result = run(args.video, [float(t) for t in args.starts.split(',')], args.duration, args.runs)
    print(json.dumps(result, indent=2))
    if not result['all_timestamps_match']:
        raise SystemExit('Unsafe result: timestamps differ')
