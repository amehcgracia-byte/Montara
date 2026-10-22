"""Single-song mix with the Zucker Mixer engine (submodule ./mixer, never edited here).

The Zucker Mixer is built for multi-hour jam sessions: it detects songs, then
mixes each one. Montara only ever has ONE song, so this adapter skips detection
entirely: it registers the uploaded tracks as one song covering the whole
length and then uses the mixer's own per-song analysis, auto-mix and render.

Usage from Montara:
    job = SingleSongMix(tracks_dir, work_dir)
    plan = job.analyze()                 # auto-mix: faders per track
    job.render(faders_db, out_path)      # final mix (+ optional reference mastering)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

MIXER = Path(__file__).resolve().parents[1] / "mixer"


def _load_mixer(work_dir: Path):
    # The mixer reads its state root once, at import: one root per Montara server.
    os.environ.setdefault("ZUCKER_MIXER_STATE_ROOT", str(work_dir / "state"))
    if str(MIXER) not in sys.path:
        sys.path.insert(0, str(MIXER))
    import jam_app  # noqa: E402  (state root is read at import time)
    import jam_mix_pipeline as pipeline  # noqa: E402

    return jam_app, pipeline


class SingleSongMix:
    def __init__(self, tracks_dir: Path, work_dir: Path, reference: Path | None = None) -> None:
        self.tracks_dir = Path(tracks_dir).resolve()
        self.work_dir = Path(work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.reference = Path(reference).resolve() if reference else None
        self.app, self.pipeline = _load_mixer(self.work_dir)
        self.state: dict[str, Any] | None = None

    # -- one song, no detection --------------------------------------------
    def _register(self) -> dict[str, Any]:
        app, pipeline = self.app, self.pipeline
        app.configure_source_folder(self.tracks_dir)
        pipeline.configure_detection_cache(self.tracks_dir, self.work_dir / "cache")
        stems = pipeline.inspect_stems(self.tracks_dir)
        if not stems:
            raise RuntimeError("No usable audio tracks")
        duration = min(stem.duration for stem in stems)
        segment = pipeline.Segment(start=0.0, end=duration, nominal_end=duration, boundary_source="manual-selection")
        song = {
            "id": 1, "session_id": "montara", "slot_id": "montara:slot-001",
            "source_start": 0.0, "source_end": duration, "manual_start": None, "manual_end": None,
            "revision": 0, "proposal_status": "manual", "cut_reason": "single song",
            "start": 0.0, "end": duration, "duration": duration, "render_end": duration,
            "time": f"0:00 - {pipeline.fmt_time(duration)}", "duration_text": pipeline.fmt_time(duration),
            "assigned_song_number": 1, "spoken_song_number": None, "spoken_last": False,
            "number_mismatch": False, "suspicious": False, "segment": json.loads(json.dumps(segment.__dict__, default=str)),
        }
        state = {
            "stems": stems,
            "segments": [segment],
            "raw_songs": [song],
            "stem_info": [
                {"index": i, "file": s.path.name, "name": s.name, "label": s.name, "role": s.role}
                for i, s in enumerate(stems)
            ],
            "active_stems_by_song": {},
            "audio_scan": pipeline.audio_scan_report(),
            "segmentation_status": "ready",
            "candidate_pending": False,
        }
        app.save_detection_snapshot(state, app.detection_state_signature())
        self.state = state
        return state

    def analyze(self) -> dict[str, Any]:
        """Run the mixer's auto-mix and return one fader per track."""
        state = self.state or self._register()
        plan = self.app.apply_overrides_for_song(1, 1, state_snapshot=state)
        tracks = []
        for stem in state["stems"]:
            params = (plan.get("stems") or {}).get(stem.path.name) or {}
            tracks.append({
                "file": stem.path.name,
                "path": str(stem.path),
                "name": stem.name,
                "role": stem.role,
                "active": stem.path.name in (plan.get("active_stems") or [s.path.name for s in state["stems"]]),
                # Level the auto-mix gives this track, relative to the raw file.
                "auto_gain_db": round(float(params.get("total_gain_db", 0.0) or 0.0) - float(params.get("level_gain_db", 0.0) or 0.0), 2),
                "fader_db": round(float(params.get("level_gain_db", 0.0) or 0.0), 2),
                "pan": float(params.get("pan", 0.0) or 0.0),
                "mute": bool(params.get("mute", False)),
            })
        order = ["kick", "snare", "hh", "drums", "overhead", "bass", "guitar", "keys", "keys_l", "synth", "horn", "sax", "vocal"]
        tracks.sort(key=lambda t: (order.index(t["role"]) if t["role"] in order else len(order), t["name"].lower()))
        return {"duration": state["segments"][0].duration, "target_lufs": plan.get("target_lufs", -14.0), "tracks": tracks}

    def render(self, faders_db: dict[str, float], output: Path, mutes: dict[str, bool] | None = None) -> Path:
        """Render the song with the person's faders (dB on top of the auto-mix)."""
        app, pipeline = self.app, self.pipeline
        state = self.state or self._register()
        overrides = app.load_json(app.OVERRIDES_PATH, {"songs": {}})
        song = overrides.setdefault("songs", {}).setdefault("1", {})
        stems = song.setdefault("stems", {})
        for name, value in (faders_db or {}).items():
            entry = stems.setdefault(name, {})
            entry["fader_db"] = float(value)
            entry["user_confirmed"] = True
            entry["user_fader_confirmed"] = True
        for name, muted in (mutes or {}).items():
            stems.setdefault(name, {})["mute"] = bool(muted)
        app.save_json(app.OVERRIDES_PATH, overrides)
        pipeline.MATCHERING_REFERENCE = str(self.reference) if self.reference else None
        plan = app.apply_overrides_for_song(1, 1, state_snapshot=state)
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        result = pipeline.render_segment(
            state["stems"], state["segments"][0], 1, self.work_dir / "renders",
            output_path=output, verify_announcement=False, prepared_plan=plan, retain_diagnostic_audio=False,
        )
        produced = Path(str(result.get("output_path") or result.get("path") or output))
        if not produced.is_file():
            produced = output
        if produced.suffix.lower() != ".mp3":
            mp3 = output.with_suffix(".mp3")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(produced), "-b:a", "256k", str(mp3)], check=True)
            produced = mp3
        return produced


if __name__ == "__main__":
    import time
    tracks, work = Path(sys.argv[1]), Path(sys.argv[2])
    job = SingleSongMix(tracks, work)
    t = time.time(); info = job.analyze(); print("analyze", round(time.time() - t, 1), "s")
    for track in info["tracks"]:
        print(f"  {track['name']:10s} {track['role']:9s} auto {track['auto_gain_db']:+6.1f} dB  fader {track['fader_db']:+5.1f}  pan {track['pan']:+.2f}  {'' if track['active'] else '(inactive)'}")
    t = time.time(); out = job.render({}, work / "mix.wav"); print("render", round(time.time() - t, 1), "s ->", out)
