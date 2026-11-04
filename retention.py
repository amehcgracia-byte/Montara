"""Opt-in lab retention. Only old managed projects/sessions; never fixtures or other homes."""
from __future__ import annotations
import fcntl
import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path

LOG = logging.getLogger(__name__)
BUSY = {'running', 'cancelling', 'detecting', 'preparing', 'rendering'}


def _json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _references(value, uploads):
    result = set()
    if isinstance(value, dict):
        for v in value.values():
            result |= _references(v, uploads)
    elif isinstance(value, list):
        for v in value:
            result |= _references(v, uploads)
    elif isinstance(value, str) and value.startswith('/'):
        try:
            result.add(Path(value).resolve().relative_to(uploads).parts[0])
        except (ValueError, IndexError, OSError):
            pass
    return result


def collect(root, *, used_limit, active_project=None, busy=lambda: False, usage=shutil.disk_usage, now=time.time):
    """Trim oldest completed work until volume use is below the configured bytes.

    Newest session AND newest video project, active project, pinned work and work
    modified in the last hour survive. Ambiguous metadata stops cleanup (fail closed).
    Returns deleted relative paths, suitable for a bounded audit log.
    """
    root = Path(root).resolve()
    if used_limit <= 0 or busy() or usage(root).used < used_limit:
        return []
    root.mkdir(parents=True, exist_ok=True)
    with (root/'.retention.lock').open('a') as control:
        try:
            fcntl.flock(control, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return []
        entries = []
        keep = {Path(active_project).resolve()} if active_project else set()
        uploads = (root/'Uploads').resolve()
        for kind, metadata in [('Sessions','session.json'),('Projects','project.json')]:
            group = []
            for path in (root/kind).glob('*/'+metadata):
                work = path.parent
                if work.is_symlink() or path.is_symlink():
                    return []
                data = _json(path)
                if not isinstance(data, dict):
                    return []
                group.append((path.stat().st_mtime, work, data))
                if data.get('status') in BUSY or (work/'.keep').exists():
                    keep.add(work.resolve())
            group.sort(reverse=True)
            if group:
                keep.add(group[0][1].resolve())
            entries.extend(group)
        entries.sort()
        deleted = []
        # Hold every worker lock while planning/deleting: a live session wins.
        handles = []
        try:
            for _, work, _ in entries:
                lock = work/'worker.lock'
                if lock.exists():
                    handle = lock.open('a');handles.append(handle)
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        return []
            for modified, work, data in list(entries):
                if busy() or usage(root).used < used_limit:
                    break
                if work.resolve() in keep or now()-modified < 3600:
                    continue
                # Look at every surviving project's JSON artifacts as well as inputs.
                # A normalized upload referenced by any survivor must remain.
                references = set()
                for _, other, metadata in entries:
                    if other == work:
                        continue
                    references |= _references(metadata, uploads)
                    for artifact in (other/'artifacts').glob('*.json'):
                        content = _json(artifact)
                        if content is None:
                            return deleted
                        references |= _references(content, uploads)
                candidates = _references(data, uploads)
                for artifact in (work/'artifacts').glob('*.json'):
                    candidates |= _references(_json(artifact), uploads)
                # Do not follow directory links or ever touch paths outside this data root.
                if work.resolve().parent not in {root/'Sessions',root/'Projects'}:
                    continue
                shutil.rmtree(work)
                deleted.append(str(work.relative_to(root)))
                entries = [row for row in entries if row[1] != work]
                for name in candidates-references:
                    path = uploads/name
                    if path.is_dir() and not path.is_symlink():
                        shutil.rmtree(path)
                        deleted.append(str(path.relative_to(root)))
        finally:
            for handle in handles:
                handle.close()
        if deleted:
            with (root/'retention.jsonl').open('a') as log:
                log.write(json.dumps({'at': int(now()), 'deleted': deleted})+'\n')
        return deleted


def start(app, root):
    limit = float(os.environ.get('MONTARA_RETENTION_USED_GB', '0')) * 1e9
    if limit <= 0:
        return
    state = app.config['ZUCKER_STATE']
    def busy():
        if state.wizard.status().get('status') in BUSY:
            return True
        # A session can work in a separate Python process between FFmpeg calls.
        for path in (Path(root)/'Sessions').glob('*/worker.lock'):
            with path.open('a') as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return True
        return False
    def worker():
        while True:
            try:
                if busy():
                    (Path(root)/'.last-activity').write_text(str(int(time.time())))
                project = state.project
                collect(root, used_limit=limit, active_project=project.folder if project else None, busy=busy)
            except Exception:
                LOG.exception('Retention skipped; data preserved')
            time.sleep(60)
    threading.Thread(target=worker, daemon=True, name='montara-retention').start()
