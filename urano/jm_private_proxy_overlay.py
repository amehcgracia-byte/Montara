"""I55: version-checked, opt-in patch of ORIGINAL JM's private proxy ceiling.

Never patches Chema's source checkout or installed app in place. A build process
supplies the ORIGINAL reviewed resumable_upload.py text and writes the adapted
copy into a NEW immutable JM candidate bundle. The patch requires exact
source anchors and fails closed on drift, so the private configuration is
auditable and removable. NO second uploader.
"""
from __future__ import annotations

import re
from pathlib import Path

DEFAULT_PRIVATE_PROXY_MIB = 2048
MAX_PRIVATE_PROXY_MIB = 4096
MIN_PRIVATE_PROXY_MIB = 256

_MARKERS = {
    "limit": "    limit = 256 * 1024**2 if os.environ.get('MONTARA_SESSION_TOKEN') else 30 * 1024**3",
    "chunk": '        return PRIVATE_PROXY_CHUNK if data.get("video_preview") and limit > 256 * 1024**2 else CHUNK',
    "limits": '        return jsonify(max_file_bytes=limit, chunk_bytes=CHUNK, free_bytes=shutil.disk_usage(root).free)',
    "size": "        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= limit:",
    "error": "            return failure(f'This environment accepts files up to {limit / 1024**2:.0f} MiB.', 413)",
}


def private_proxy_limit_mib(value: object = DEFAULT_PRIVATE_PROXY_MIB) -> int:
    if type(value) is not int or not MIN_PRIVATE_PROXY_MIB <= value <= MAX_PRIVATE_PROXY_MIB:
        raise ValueError("Untrusted private proxy file limit")
    return value


def patched_original_resumable_upload(original: str) -> str:
    """Produce a new build input only, fail if any JM anchor differs."""
    if not isinstance(original, str):
        raise TypeError("Original JM source text required")
    for name, anchor in _MARKERS.items():
        if original.count(anchor) != 1:
            raise ValueError("Original JM upload implementation drifted: " + name)
    patches = {
        "limit": _MARKERS["limit"] + """
    # MONTARA_PRIVATE_PROXY_LIMIT_MIB is set ONLY inside an isolated Owner
    # worker; no token or config means the untouched Chema behavior.
    _proxy_mib = os.environ.get("MONTARA_PRIVATE_PROXY_LIMIT_MIB")
    proxy_limit = limit
    if os.environ.get('MONTARA_SESSION_TOKEN') and _proxy_mib is not None:
        if (not re.fullmatch(r"[0-9]{3,4}", _proxy_mib)
                or not 256 <= int(_proxy_mib) <= 4096):
            raise ValueError("Invalid private Owner proxy quota")
        proxy_limit = int(_proxy_mib) * 1024**2
""".rstrip(),
        "chunk": '        return PRIVATE_PROXY_CHUNK if data.get("video_preview") and proxy_limit > 256 * 1024**2 else CHUNK',
        "limits": ('        return jsonify(max_file_bytes=proxy_limit, '
                   'max_original_file_bytes=limit, chunk_bytes=CHUNK, '
                   'free_bytes=shutil.disk_usage(root).free)'),
        "size": r"""        # Large files are admitted only when they are Companion previews.
        # Manual original uploads keep the standard JM remote 256 MiB limit.
        # A Companion lossless derivative keeps the source audio extension
        # (e.g. song.mp3.flac / song.wav.wv). This is audio, not an
        # original video; only the reviewed remote proxy ceiling increases.
        # Do not trust an arbitrary video_preview=true on a raw video.
        lossless_audio = bool(isinstance(name, str) and re.search(
            r"\.(?:wav|aif|aiff|mp3|m4a|flac|ogg|opus|wv)\.(?:flac|wv)\Z",
            name, re.IGNORECASE))
        video_proxy = bool(body.get('video_preview') is True
            and isinstance(name, str) and name.lower().endswith('.small.mp4'))
        audio_preview = bool(isinstance(name, str)
            and name.lower().endswith(PREVIEW))
        admitted_limit = proxy_limit if (video_proxy or
            lossless_audio or audio_preview) else limit
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= admitted_limit:""",
        "error": "            return failure(f'This environment accepts files up to {admitted_limit / 1024**2:.0f} MiB.', 413)",
    }
    result = original
    for key in ("limit", "chunk", "limits", "size", "error"):
        result = result.replace(_MARKERS[key], patches[key], 1)
    return result



# Upgrade ONLY the already-reviewed, immutable I56 Owner proxy overlay.
# Do not rebuild from older Chema code, overwrite main or mutate a live bundle.
_REVIEWED_AUDIO_SIZE_ANCHOR = """        preview_file = body.get('video_preview') is True or (
            isinstance(name, str) and name.lower().endswith(PREVIEW))
        admitted_limit = proxy_limit if preview_file else limit"""


def patched_reviewed_private_audio_overlay(reviewed: str) -> str:
    """Produce a separate JM candidate with a matching audio-proxy ceiling."""
    if (not isinstance(reviewed, str)
            or reviewed.count(_REVIEWED_AUDIO_SIZE_ANCHOR) != 1
            or "MONTARA_PRIVATE_PROXY_LIMIT_MIB" not in reviewed
            or "max_original_file_bytes=limit" not in reviewed):
        raise ValueError("Reviewed JM Owner proxy bundle does not match I56")
    replacement = r"""        # Companion-derived lossless audio keeps the source audio suffix
        # before .flac/.wv. Match the existing configured PRIVATE proxy cap;
        # standalone audio files and video originals retain remote limit.
        lossless_audio = bool(isinstance(name, str) and re.search(
            r"\\.(?:wav|aif|aiff|mp3|m4a|flac|ogg|opus|wv)\\.(?:flac|wv)\\Z",
            name, re.IGNORECASE))
        video_proxy = bool(body.get('video_preview') is True
            and isinstance(name, str) and name.lower().endswith('.small.mp4'))
        audio_preview = bool(isinstance(name, str)
            and name.lower().endswith(PREVIEW))
        admitted_limit = proxy_limit if (video_proxy or
            lossless_audio or audio_preview) else limit"""
    candidate = reviewed.replace(_REVIEWED_AUDIO_SIZE_ANCHOR, replacement, 1)
    compile(candidate, "reviewed-private-audio-JM-candidate.py", "exec")
    return candidate


def stage_reviewed_private_audio_overlay(
    reviewed_path: Path, destination_path: Path
) -> None:
    """Write a NEW candidate file, preserving Chema's live I56 bundle."""
    reviewed_path = Path(reviewed_path).resolve(strict=True)
    target = Path(destination_path)
    if reviewed_path == target.resolve() or target.is_symlink() or target.exists():
        raise ValueError("Review and candidate paths must be separate")
    content = patched_reviewed_private_audio_overlay(
        reviewed_path.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        handle.write(content)


def stage_private_jm_resumable(
    original_path: Path, destination_path: Path, *,
    configured_mib: int = DEFAULT_PRIVATE_PROXY_MIB,
) -> None:
    """Build-time only: never patch the same original file in place."""
    private_proxy_limit_mib(configured_mib)
    source = Path(original_path).resolve(strict=True)
    target = Path(destination_path)
    if source == target.resolve() or target.is_symlink():
        raise ValueError("Source must remain immutable and separate")
    if target.exists():
        raise FileExistsError("Refuse overwrite of existing JM bundle file")
    patched = patched_original_resumable_upload(source.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as out:
        out.write(patched)
