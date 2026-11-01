"""deploy/vm/disk.py: a named session goes with the uploads only it uses; the newest session and shared uploads stay."""
import json, os, subprocess, sys, time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy' / 'vm' / 'disk.py'


def test_clean_removes_only_what_was_named(tmp_path):
    data = tmp_path / 'montara-data'
    for u in ('a', 'b', 'shared', 'orphan'):
        (data / 'Uploads' / u).mkdir(parents=True); (data / 'Uploads' / u / 'x.wav').write_bytes(b'0' * 1000)
    def session(sid, uploads, age):
        work = data / 'Sessions' / sid; work.mkdir(parents=True)
        tracks = [dict(file=f'{u}.wav', path=str(data / 'Uploads' / u / 'x.wav'), duration=60) for u in uploads]
        (work / 'session.json').write_text(json.dumps(dict(status='done', tracks=tracks, songs=[], results=[])))
        os.utime(work, (time.time() - age, time.time() - age))
    (data / 'Uploads' / 'allocation.lock').write_text('')
    session('older', ['a', 'shared'], 7200)
    session('old', ['a', 'shared'], 3600)
    session('new', ['b', 'shared'], 0)
    env = dict(os.environ, HOME=str(tmp_path))
    dry = subprocess.run([sys.executable, str(SCRIPT), 'clean', '--session', 'old', '--session', 'new'], env=env, capture_output=True, text=True).stdout
    assert 'kept (newest or --keep): new' in dry and (data / 'Sessions' / 'old').exists()   # dry run deletes nothing
    listed = subprocess.run([sys.executable, str(SCRIPT), 'clean', '--session', 'old', '--session', 'older', '--uploads-days', '-1'], env=env, capture_output=True, text=True).stdout
    assert listed.count('Uploads/a\n') == 1 and 'allocation.lock' not in listed   # once, and never the lock file
    subprocess.run([sys.executable, str(SCRIPT), 'clean', '--session', 'old', '--session', 'older', '--apply'], env=env, check=True, capture_output=True)
    assert not (data / 'Sessions' / 'old').exists() and not (data / 'Uploads' / 'a').exists() and (data / 'Uploads' / 'allocation.lock').exists()
    assert (data / 'Uploads' / 'shared').exists() and (data / 'Uploads' / 'b').exists() and (data / 'Sessions' / 'new').exists()
    assert (data / 'Uploads' / 'orphan').exists()   # unused uploads only go with --uploads-days
    report = subprocess.run([sys.executable, str(SCRIPT), 'report'], env=env, capture_output=True, text=True)
    assert report.returncode == 0 and 'new' in report.stdout
