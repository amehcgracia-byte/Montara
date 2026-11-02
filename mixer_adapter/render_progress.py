"""Small atomic progress snapshots, shared by isolated server/companion song workers.

Percentages describe completed work stages, not a promise of remaining wall time.
During mixing every stem advances together: the mixer processes all stems per chunk.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class SongProgress:
    def __init__(self, path, tracks):
        self.path = Path(path) if path else None
        self.lock = threading.RLock()
        self.started = time.monotonic()
        self.state = dict(status='working', phase='preparing', progress=0,
                          tracks=[dict(file=name, progress=0, active=False) for name in tracks])
        self.write()

    def write(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({**self.state, 'elapsed': round(time.monotonic() - self.started, 1)}))
            temporary.replace(self.path)

    def prepare(self, name, done=False):
        with self.lock:
            for track in self.state['tracks']:
                if track['file'] == name:
                    track.update(progress=.15 if done else .01, active=not done)
            self.state['progress'] = sum(t['progress'] for t in self.state['tracks']) / max(1, len(self.state['tracks']))
            self.write()

    def callback(self, update):
        phase = update.get('current_stage', '')
        # The vendor resets its counter between analysis, mixing and mastering.
        # Only mixing's chunk counter is a measured fraction of the song audio.
        value = {'mastering': .9, 'encoding': .96}.get(phase, .16)
        if phase == 'mixing':
            value = .25 + .63 * min(1, max(0, float(update.get('song_progress', 0)) / 88))
        with self.lock:
            self.state.update(phase=phase, progress=max(self.state['progress'], value))
            for track in self.state['tracks']:
                track.update(progress=max(track['progress'], value), active=True)
            self.write()

    def finish(self):
        with self.lock:
            self.state.update(status='ready', phase='ready', progress=1)
            for track in self.state['tracks']:
                track.update(progress=1, active=False)
            self.write()
