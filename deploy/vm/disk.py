#!/usr/bin/env python3
"""Disk use of this Montara user (jm) and a safe, explicit cleanup. Nothing is deleted without --apply.

    python3 deploy/vm/disk.py report
    python3 deploy/vm/disk.py clean --session ID [--session ID ...] [--mixer-days N] [--uploads-days N] [--projects-days N] [--apply]

Rules
- Only paths inside ~/montara-data and ~/.cache are touched; never another user's home.
- The newest session is always kept (the one being tested), and so is anything in --keep.
- A session goes only when named with --session. Its uploads go with it unless another kept
  session or project still uses them.
- --mixer-days, --uploads-days and --projects-days remove old single-song mixes, uploads that no
  session uses, and old video projects/renders.
- Without --apply it prints what would be removed and how much space that frees.
"""
import argparse, json, os, shutil, sys, time
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'montara-data'


def size(path: Path) -> int:
    if path.is_symlink() or not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            p = Path(root) / name
            if not p.is_symlink():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total


def gb(n):
    return f'{n / 1e9:6.1f} GB'


def age_days(path: Path) -> float:
    try:
        return (time.time() - path.stat().st_mtime) / 86400
    except OSError:
        return 0.0


def sessions():
    """[(folder, data)] newest first."""
    result = []
    for path in (DATA / 'Sessions').glob('*/session.json'):
        try:
            result.append((path.parent, json.loads(path.read_text())))
        except (OSError, ValueError):
            result.append((path.parent, {}))
    return sorted(result, key=lambda item: item[0].stat().st_mtime, reverse=True)


def uploads_used_by(work: Path, data: dict) -> set[str]:
    """Upload ids a session reads: its tracks (symlinks into Uploads) and its original ranges."""
    uploads = (DATA / 'Uploads').resolve()
    paths = [t.get('path', '') for t in data.get('tracks') or []]
    paths += [str(p.resolve()) for p in (work / 'tracks').glob('*') if p.is_symlink()]
    for f in (work / 'originals').glob('*.json'):
        try:
            paths.append(json.loads(f.read_text()).get('path', ''))
        except (OSError, ValueError):
            pass
    used = set()
    for p in paths:
        try:
            rel = Path(p).resolve().relative_to(uploads)
            used.add(rel.parts[0])
        except (ValueError, IndexError):
            continue
    return used


def report():
    import subprocess
    print(subprocess.run(['df', '-h', str(HOME)], capture_output=True, text=True).stdout)
    print('--- this user, by folder')
    for p in sorted(HOME.iterdir(), key=lambda p: -size(p))[:12]:
        print(f'{gb(size(p))}  {p.name}')
    print('\n--- montara-data, by folder')
    for p in sorted(DATA.iterdir(), key=lambda p: -size(p)) if DATA.is_dir() else []:
        print(f'{gb(size(p))}  {p.name}')
    print('\n--- sessions (newest first; the first one is always kept)')
    all_sessions = sessions()
    used_by = {}
    for work, data in all_sessions:
        for u in uploads_used_by(work, data):
            used_by.setdefault(u, []).append(work.name)
    for i, (work, data) in enumerate(all_sessions):
        mine = uploads_used_by(work, data)
        up = sum(size(DATA / 'Uploads' / u) for u in mine)
        tracks = data.get('tracks') or []
        minutes = max((t.get('duration', 0) for t in tracks), default=0) / 60
        print(f"{work.name}  {time.strftime('%d-%m %H:%M', time.localtime(work.stat().st_mtime))}  {data.get('status', '?'):9}"
              f"  {len(tracks):2} tracks · {minutes:5.0f} min · {len(data.get('songs') or []):2} songs · {len(data.get('results') or []):2} exported"
              f"  | folder {gb(size(work))} + uploads {gb(up)}{'  ← newest, kept' if i == 0 else ''}")
    print('\n--- uploads no session uses (age in days)')
    total = 0
    for u in sorted((DATA / 'Uploads').glob('*')) if (DATA / 'Uploads').is_dir() else []:
        if u.name in used_by:
            continue
        s = size(u); total += s
        try:
            name = json.loads((u / 'upload.json').read_text()).get('name', '?')
        except (OSError, ValueError):
            name = '?'
        if s > 200e6:
            print(f'{gb(s)}  {age_days(u):5.1f} d  {u.name}  {name}')
    print(f'{gb(total)} in uploads no session uses (only those above 200 MB listed)')
    for name in ('Mixer', 'Projects', 'Cache', 'PushPacks', 'WizardUploads', 'Inbox'):
        folder = DATA / name
        if folder.is_dir():
            old = [p for p in folder.iterdir() if age_days(p) > 2]
            print(f'{name}: {gb(size(folder))} total, {len(old)} items older than 2 days ({gb(sum(size(p) for p in old))})')
    print(f"~/.cache: {gb(size(HOME / '.cache'))}")


def clean(args):
    all_sessions = sessions()
    keep = set(args.keep or []) | ({all_sessions[0][0].name} if all_sessions else set())
    targets = []   # (path, why)
    gone_sessions = set()
    for work, _data in all_sessions:
        if work.name in (args.session or []) and work.name not in keep:
            targets.append((work, 'session'))
            gone_sessions.add(work.name)
    unknown = set(args.session or []) - {w.name for w, _ in all_sessions}
    if unknown:
        print('unknown sessions (ignored):', ' '.join(sorted(unknown)))
    if set(args.session or []) & keep:
        print('kept (newest or --keep):', ' '.join(sorted(set(args.session) & keep)))
    still_used = set()
    for work, data in all_sessions:
        if work.name not in gone_sessions:
            still_used |= uploads_used_by(work, data)
    for work, data in all_sessions:
        if work.name in gone_sessions:
            for u in uploads_used_by(work, data) - still_used:
                targets.append((DATA / 'Uploads' / u, f'upload of {work.name}'))
    if args.uploads_days is not None:
        for u in (DATA / 'Uploads').glob('*') if (DATA / 'Uploads').is_dir() else []:
            if u.name not in still_used and age_days(u) > args.uploads_days and all(t[0] != u for t in targets):
                targets.append((u, f'upload no session uses, {age_days(u):.0f} d old'))
    for flag, folder in ((args.mixer_days, 'Mixer'), (args.projects_days, 'Projects')):
        if flag is not None and (DATA / folder).is_dir():
            for p in (DATA / folder).iterdir():
                if p.is_dir() and p.name != 'state' and age_days(p) > flag and p.name not in keep:   # 'state': the mixer's own settings
                    targets.append((p, f'{folder} item {age_days(p):.0f} d old'))
    total = 0
    for path, why in targets:
        assert path.resolve().is_relative_to(DATA.resolve()), path   # never outside montara-data
        s = size(path); total += s
        print(f'{gb(s)}  {why:40}  {path}')
    print(f'\n{len(targets)} items, {gb(total)} {"freed" if args.apply else "would be freed (dry run: add --apply)"}')
    if args.apply:
        for path, _why in targets:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('report')
    c = sub.add_parser('clean')
    c.add_argument('--session', action='append')
    c.add_argument('--keep', action='append')
    c.add_argument('--mixer-days', type=float)
    c.add_argument('--uploads-days', type=float)
    c.add_argument('--projects-days', type=float)
    c.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    report() if args.command == 'report' else clean(args)
