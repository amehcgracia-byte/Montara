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
import hashlib
import math
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

MIXER = Path(__file__).resolve().parents[1] / "mixer"


def validate_effects(effects, names):
    if not isinstance(effects, dict) or set(effects) - set(names):
        raise ValueError("Unknown track or invalid FX settings")
    result = {}
    for name, settings in effects.items():
        if not isinstance(settings, dict) or set(settings) - {"reverb", "delay"}:
            raise ValueError("Only reverb and delay are available")
        result[name] = {}
        for effect in ("reverb", "delay"):
            value = settings.get(effect, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("FX intensity must be between 0 and 1")
            result[name][effect] = float(value)
    return result


EQ_KEYS = {"eq_low_cut_hz": (20.0, 1000.0), "eq_mid_gain_db": (-15.0, 15.0), "eq_air_gain_db": (-15.0, 15.0)}


def validate_eq(eq, names):
    """Per-track EQ the person set: the mixer's own low cut, mid and air bands."""
    if not isinstance(eq, dict) or set(eq) - set(names):
        raise ValueError("Unknown track or invalid EQ settings")
    result = {}
    for name, settings in eq.items():
        if not isinstance(settings, dict) or set(settings) - set(EQ_KEYS):
            raise ValueError("Only low cut, mid and air can be set")
        result[name] = {}
        for key, value in settings.items():
            low, high = EQ_KEYS[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("EQ value out of range")
            result[name][key] = float(value)
    return result


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

    def _activate(self) -> None:
        # The vendor keeps its active folder in module globals. Every operation
        # must restore this job, even when another mix was analyzed meanwhile.
        self.app.configure_source_folder(self.tracks_dir)
        self.pipeline.configure_detection_cache(self.tracks_dir, self.work_dir / "cache")

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
        self._activate()
        plan = self.app.apply_overrides_for_song(1, 1, state_snapshot=state, overrides_snapshot={"songs": {}})
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
                # The mixer's EQ for this role: the page shows it and the person can change it.
                "eq": {slot: {"type": kind, "hz": float(freq), "q": float(q), "db": float(gain)}
                       for slot, kind, freq, q, gain in self.pipeline.role_eq_bands(stem.role)},
            })
        order = ["kick", "snare", "hh", "drums", "overhead", "bass", "guitar", "keys", "keys_l", "synth", "horn", "sax", "vocal"]
        tracks.sort(key=lambda t: (order.index(t["role"]) if t["role"] in order else len(order), t["name"].lower()))
        return {"duration": state["segments"][0].duration, "target_lufs": plan.get("target_lufs", -14.0), "tracks": tracks}

    def effect_track(self, name: str, effect: str) -> Path:
        """Cache a wet-only track using the original mixer's fixed DSP, for preview and export."""
        import numpy as np
        import soundfile as sf
        if effect not in {"reverb", "delay"}:
            raise ValueError("Unknown effect")
        state = self.state or self._register()
        stem = next((s for s in state["stems"] if s.path.name == name), None)
        if stem is None:
            raise ValueError("Unknown track")
        stamp = f"fx017-native-channels:{stem.path}:{stem.path.stat().st_mtime_ns}:{stem.path.stat().st_size}:{effect}"
        target = self.work_dir / "fx" / (hashlib.sha256(stamp.encode()).hexdigest() + ".wav")
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            return target
        temporary = target.with_suffix(".tmp.wav")
        memory = {}
        try:
            with sf.SoundFile(stem.path) as source, sf.SoundFile(temporary, "w", samplerate=source.samplerate, channels=min(stem.channels, 2), subtype="FLOAT") as dest:
                while True:
                    block = source.read(65536, dtype="float32", always_2d=True)
                    if not len(block):
                        break
                    stereo = np.repeat(block, 2, axis=1) if block.shape[1] == 1 else block[:, :2]
                    wet = self.pipeline.plate_reverb_streaming(stereo, source.samplerate, 1.7, memory) if effect == "reverb" else self.pipeline.slap_delay_streaming(stereo, source.samplerate, 90.0, memory)
                    # Keep mono tracks mono: duplicating them into stereo
                    # changes the vendor pan law and boosts their dry signal 3 dB.
                    dest.write(wet.mean(axis=1, keepdims=True) if stem.channels == 1 else wet)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def _effect_stems(self, effects):
        import numpy as np
        import soundfile as sf
        state = self.state or self._register()
        result = []
        for stem in state["stems"]:
            settings = effects.get(stem.path.name, {})
            wet_paths = [(self.effect_track(stem.path.name, key), amount) for key, amount in settings.items() if amount > 0]
            if not wet_paths:
                result.append(stem)
                continue
            target = self.work_dir / "fx-input" / stem.path.name
            # Use WAV containers even when the registered name ends in .mp3.
            target.parent.mkdir(exist_ok=True)
            from contextlib import ExitStack
            with ExitStack() as stack:
                source = stack.enter_context(sf.SoundFile(stem.path))
                readers = [(stack.enter_context(sf.SoundFile(path)), amount) for path, amount in wet_paths]
                dest = stack.enter_context(sf.SoundFile(target, "w", format="WAV", samplerate=source.samplerate, channels=min(stem.channels, 2), subtype="FLOAT"))
                while True:
                    block = source.read(65536, dtype="float32", always_2d=True)
                    if not len(block):
                        break
                    stereo = block[:, :min(stem.channels, 2)].copy()
                    for reader, amount in readers:
                        stereo += reader.read(len(block), dtype="float32", always_2d=True) * amount
                    dest.write(stereo)
            result.append(replace(stem, path=target, channels=min(stem.channels, 2)))
        return result

    def render(self, faders_db: dict[str, float], output: Path, mutes: dict[str, bool] | None = None, effects: dict | None = None, *, base_gains: dict[str, float] | None = None, eq: dict | None = None) -> Path:
        """Render the song with the person's faders (dB on top of the auto-mix)."""
        app, pipeline = self.app, self.pipeline
        state = self.state or self._register()
        self._activate()
        if effects is not None:
            effects = validate_effects(effects, [s.path.name for s in state["stems"]])
        settings_path = self.work_dir / "montara_mix_settings.json"
        overrides = app.load_json(settings_path, {"songs": {}})
        song = overrides.setdefault("songs", {}).setdefault("1", {})
        stems = song.setdefault("stems", {})
        for name, value in (base_gains or {}).items():
            # A full session shares the audible baseline of its reviewed mix.
            # Do not silently rebalance each song underneath the common faders.
            stems.setdefault(name, {}).update(makeup_gain_db=float(value), manual_makeup_gain_db=True)
        for name, value in (faders_db or {}).items():
            entry = stems.setdefault(name, {})
            entry["fader_db"] = float(value)
            entry["user_confirmed"] = True
            entry["user_fader_confirmed"] = True
        for name, muted in (mutes or {}).items():
            stems.setdefault(name, {})["mute"] = bool(muted)
        for name, values in validate_eq(eq or {}, [s.path.name for s in state["stems"]]).items():
            stems.setdefault(name, {}).update(values)
        if effects is not None:
            for stem in state["stems"]:
                # Explicit controls replace automatic sends; never apply the effects twice.
                stems.setdefault(stem.path.name, {}).update(effects_user_confirmed=True, space_enabled=False, echo_enabled=False)
        app.save_json(app.OVERRIDES_PATH, overrides)
        app.save_json(settings_path, overrides)
        plan = app.apply_overrides_for_song(1, 1, state_snapshot=state, overrides_snapshot=overrides)
        pipeline.MATCHERING_REFERENCE = str(self.reference) if self.reference else None
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        result = pipeline.render_segment(
            self._effect_stems(effects) if effects is not None else state["stems"], state["segments"][0], 1, self.work_dir / "renders",
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
