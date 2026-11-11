"""Safe selection of existing local originals for the native Companion E2E.

Only reads selected files. Original videos never enter GitHub, Actions, or any
remote service. The caller must use a scratch output outside media roots.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

CAMERA_EXT = {".mov", ".mp4", ".m4v", ".insv"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".aif", ".aiff"}


def validate_real_sources(cameras: list[str], master: str, output: Path) -> tuple[list[Path], Path]:
    if len(cameras) != 2:
        raise ValueError("Native real acceptance currently requires exactly two cameras")
    files = [Path(p).expanduser() for p in (*cameras, master)]
    if any(not p.is_absolute() or p.is_symlink() or not p.is_file() for p in files):
        raise ValueError("All input files must exist as regular, non-symlink absolute paths")
    files = [p.resolve(strict=True) for p in files]
    if len(set(files)) != 3:
        raise ValueError("Two different cameras and a separate master are required")
    if any(f.suffix.lower() not in CAMERA_EXT for f in files[:2]):
        raise ValueError("Unsupported camera file extension")
    if files[2].suffix.lower() not in AUDIO_EXT:
        raise ValueError("Master must be an existing audio file")
    if len({f.name.lower() for f in files}) != len(files):
        raise ValueError("Input basenames must be unique for source attestation")
    out = Path(output).expanduser().resolve(strict=False)
    for source in files:
        if out == source.parent or out.is_relative_to(source.parent):
            raise ValueError("Scratch output cannot overlap any original media directory")
    if out.exists() and out.is_symlink():
        raise ValueError("Scratch output cannot be a symlink")
    return files[:2], files[2]


def hash_streamed(path: Path, *, block_size: int = 4 * 1024 * 1024) -> bytes:
    """Avoid reading entire 4K/360 originals into RAM while attesting recipes."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(block_size), b""):
            digest.update(chunk)
    return digest.digest()
