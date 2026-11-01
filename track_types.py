"""Track types the person can choose for each audio track, and the mixer role each one uses.

The page pre-fills the type from the file name (same rules as the mixer) and the person can
change it. A type the person chose themselves also tells the mixer the track is music: it is
never muted as empty or noisy. Types without a mixer role of their own yet use the nearest
one (until ZuckerMixer's instrument dictionary has them).
"""
from __future__ import annotations

from pathlib import Path

# value: (label shown in the page, ZuckerMixer role)
TYPES: dict[str, tuple[str, str]] = {
    "kick": ("Kick", "kick"),
    "snare": ("Snare", "snare"),
    "hh": ("Hi-hat", "hh"),
    "overhead": ("Overhead", "overhead"),
    "drums": ("Drums (other)", "drums"),
    "percussion": ("Percussion", "drums"),
    "bass": ("Bass", "bass"),
    "guitar_electric": ("Electric guitar", "guitar"),
    "guitar_acoustic": ("Acoustic guitar", "guitar"),
    "keys": ("Piano / keys", "keys"),
    "synth": ("Synth", "synth"),
    "sax": ("Saxophone", "sax"),
    "trumpet": ("Trumpet", "horn"),
    "trombone": ("Trombone", "horn"),
    "flute": ("Flute", "horn"),
    "violin": ("Violin", "horn"),
    "strings": ("Strings", "synth"),
    "vocal": ("Lead vocal", "vocal"),
    "backing_vocal": ("Backing vocal", "vocal"),
    "podcast_voice": ("Podcast voice", "vocal"),
    "narration": ("Narration voice", "vocal"),
    "room": ("Room / audience", "room"),
    "other": ("Other", "other"),
}
SIDES = {"", "L", "R"}


AUDIO_SUFFIXES = {".wav", ".flac", ".wv", ".opus", ".aif", ".aiff", ".mp3", ".m4a"}


def track_key(name) -> str:
    """'Bass.wav', 'Bass.wav.opus' (a preview) and 'Bass.wav.flac' are the same track: 'bass'."""
    path = Path(str(name)).name
    while Path(path).suffix.lower() in AUDIO_SUFFIXES:
        path = path[: -len(Path(path).suffix)]
    return path.lower()


def validate(raw) -> dict[str, dict]:
    """{track key: {type, side, chosen}}; unknown types are dropped."""
    result = {}
    if not isinstance(raw, dict):
        return result
    for name, item in list(raw.items())[:200]:
        if not isinstance(item, dict) or item.get("type") not in TYPES:
            continue
        side = item.get("side") if item.get("side") in SIDES else ""
        result[track_key(name)] = {"type": item["type"], "side": side, "chosen": item.get("chosen") is True}
    return result


def for_files(types, files) -> dict[str, dict]:
    """The types that apply to these file names, keyed by file name."""
    types = types or {}
    return {Path(str(f)).name: types[track_key(f)] for f in files if track_key(f) in types}


def mixer_roles(types: dict[str, dict]) -> dict[str, str]:
    """Mixer role per file. Keys with a side become keys_l / keys_r (the mixer's stereo keys)."""
    roles = {}
    for name, item in (types or {}).items():
        role = TYPES[item["type"]][1]
        if role == "keys" and item.get("side") in {"L", "R"}:
            role = "keys_l" if item["side"] == "L" else "keys_r"
        roles[name] = role
    return roles


def stereo_sides(types: dict[str, dict]) -> dict[str, str]:
    return {name: item["side"] for name, item in (types or {}).items() if item.get("side") in {"L", "R"}}


def noise_exempt(types: dict[str, dict]) -> set[str]:
    """Tracks whose type the person chose: they are music, never muted as noise."""
    return {name for name, item in (types or {}).items() if item.get("chosen") and item["type"] != "other"}


def apply(pipeline, stems, types):
    """Give the mixer the person's types: roles on the stems, stereo sides, noise exemptions.

    `types` is keyed by file name (see for_files). Returns the stems with their roles replaced.
    """
    from dataclasses import replace
    roles = mixer_roles(types)
    pipeline.STEREO_SIDES = stereo_sides(types)
    pipeline.NOISE_EXEMPT_STEMS = noise_exempt(types)
    # The instrument dictionary refines each track's processing (EQ, compressor, pan, level, sends).
    pipeline.STEM_INSTRUMENTS = {name: item["type"] for name, item in (types or {}).items()}
    return [replace(s, role=roles[s.path.name]) if s.path.name in roles else s for s in stems]
