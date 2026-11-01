#!/usr/bin/env python3
"""Check the audio of a Montara session: exported songs (length, silence) and received original ranges.

    python3 deploy/vm/audio_check.py [session id]     (latest session when omitted)
"""
import glob, json, os, re, subprocess, sys

home = os.path.expanduser('~')
sessions = sorted(glob.glob(f'{home}/montara-data/Sessions/*/session.json'), key=os.path.getmtime)
print('sessions (oldest first):', ' '.join(os.path.basename(os.path.dirname(p)) for p in sessions[-6:]))
# Asked session, or the last two that exported something (the current one and the one before).
picked = [p for p in sessions if sys.argv[1:] and sys.argv[1] in p] or \
    [p for p in sessions if glob.glob(os.path.join(os.path.dirname(p), 'results', '*.json'))][-2:]


def duration(p):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def silence(p, total):
    """Seconds of silence (below -50 dB) and where the first long one starts."""
    err = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', p, '-af', 'silencedetect=n=-50dB:d=2', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', err)]
    ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', err)]
    ends += [total] * (len(starts) - len(ends))
    quiet = sum(e - s for s, e in zip(starts, ends))
    return quiet, (starts[0] if starts else None)


def peak(p):
    err = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', p, '-af', 'volumedetect', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = re.search(r'max_volume: (-?[\d.]+|-inf) dB', err)
    return m.group(1) if m else '?'


def check(path):
    work = os.path.dirname(path); d = json.load(open(path))
    print('\n===== session:', os.path.basename(work), d.get('status'), d.get('error') or '')
    songs = {s['id']: s for s in d.get('songs', [])}
    print('--- exported songs')
    for r in sorted(d.get('results') or [json.load(open(f)) for f in glob.glob(f'{work}/results/*.json')], key=lambda r: r['id']):
        want = r['end'] - r['start']
        if not os.path.isfile(r['path']):
            print(f"{r['id']:3} {r['name']}: file missing"); continue
        got = duration(r['path']); quiet, first = silence(r['path'], got)
        print(f"{r['id']:3} {r['name'][:18]:18} want {want:6.1f}s got {got:6.1f}s | silent {quiet:6.1f}s{'' if first is None else f' (first at {first:.1f}s)'}")
    print('--- per-song mixes (muted tracks)')
    for sid, mix in ((d.get('settings') or {}).get('per_song') or {}).items():
        print(f"song {sid}: muted {sorted(k for k, v in (mix.get('mutes') or {}).items() if v)} | faders {len(mix.get('faders') or {})} | effects {len(mix.get('effects') or {})}")
    print('--- received original ranges (shorter than asked = audio cut)')
    bad = 0
    for f in sorted(glob.glob(f'{work}/originals/*.json')):
        o = json.load(open(f)); want = o['window'][1] - o['window'][0]
        got = duration(o['path']) if os.path.isfile(o['path']) else -1
        flag = 'MISSING' if got < 0 else 'SHORT' if got < want - 1 else ''
        bad += bool(flag)
        if flag or len(sys.argv) > 2:
            print(f"{o['file']:16} window {o['window'][0]:7.1f}-{o['window'][1]:7.1f} ({want:5.1f}s) file {got:6.1f}s {flag}")
    print(f"{len(glob.glob(f'{work}/originals/*.json'))} ranges, {bad} missing/short")
    print('--- tracks (peak level of the light copy; -inf or below -60 = empty)')
    for t in d.get('tracks', []):
        print(f"{t['file']:16} {t['duration'] / 60:6.1f} min  offset {t['offset']:6.1f}s  peak {peak(t['path'])} dB")


for p in picked:
    check(p)
