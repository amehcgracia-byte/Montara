#!/usr/bin/env python3
"""Mix one song of a full session on this computer (Montara companion, optional mixer).

Runs inside the companion's mixer environment (~/.montara-companion/mixer, made by
`install.sh --mixer`), next to the same files the server uses: mixer_adapter/single_song.py,
mixer_adapter/extract.py, track_types.py and the ZuckerMixer code (mixer/) at the server's commit.

    python local_mix.py plan.json out.mp3

plan.json: the server's /local-plan for one song window, with each track's "path" filled in by
the companion (the original found on this computer) and the song's mix ("faders", "mutes",
"effects", "eq"). Prints one JSON line {"output", "seconds"} when done.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main(plan_path: str, output: str, progress_path: str | None = None) -> None:
    started = time.monotonic()
    plan = json.loads(Path(plan_path).read_text())
    ffmpeg = os.environ.get("MONTARA_FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
    from mixer_adapter.extract import window_command
    from mixer_adapter.render_progress import SongProgress
    progress = SongProgress(progress_path, [t['file'] for t in plan['tracks']])
    work = Path(tempfile.mkdtemp(prefix="montara-mix-"))
    try:
        folder = work / "tracks"
        folder.mkdir()
        for track in plan["tracks"]:   # the same cut, delay and padding as the server's prepare_tracks
            progress.prepare(track['file'])
            subprocess.run(window_command(ffmpeg, track.get("path"), track["source_start"], track["overlap"], track["delay_ms"],
                                          plan["duration"], track["channels"], track["samplerate"], str(folder / track["file"])),
                           check=True)
            progress.prepare(track['file'], done=True)
        os.environ["ZUCKER_MIXER_STATE_ROOT"] = str(work / "state")
        import track_types
        from mixer_adapter.single_song import SingleSongMix, tag_song_export
        present = {t["file"] for t in plan["tracks"]}
        only = lambda values: None if values is None else {k: v for k, v in values.items() if k in present}
        mixer = SingleSongMix(folder, work / "mix", track_types=track_types.validate(plan.get("track_types")))
        mixer.pipeline.PROGRESS_HOOK = progress.callback
        produced = mixer.render(only(plan.get("faders")) or {}, Path(output), only(plan.get("mutes")) or {}, only(plan.get("effects")),
                                eq=only(plan.get("eq")))
        if Path(produced).resolve() != Path(output).resolve():
            shutil.move(str(produced), output)
        tag_song_export(Path(output), plan.get('name') or 'Song', int(plan.get('song') or 1))
        progress.finish()
        print(json.dumps({"output": output, "seconds": round(time.monotonic() - started, 1)}), flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
