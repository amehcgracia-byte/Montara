"""Import a mastering reference without changing the editor or mixer vendors."""
from __future__ import annotations

import ipaddress
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def reference_url(value: str) -> str:
    value = str(value or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Paste a public audio or video link beginning with https://")
    if parsed.hostname.lower() in {"open.spotify.com", "spotify.com", "www.spotify.com", "spotify.link"}:
        raise ValueError("Spotify does not provide the full audio file for mastering. Use the song's YouTube link or choose an audio file from your computer.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except (OSError, ValueError) as exc:
        raise ValueError("This address could not be reached. Check the link.") from exc
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Use a public internet link, not a local or private address.")
    return value


def import_reference(url: str, work_dir: Path) -> tuple[Path, str]:
    from yt_dlp import YoutubeDL
    url = reference_url(url)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reference-", dir=work_dir) as temporary:
        root = Path(temporary)
        options = {
            "format": "bestaudio/best", "noplaylist": True, "quiet": True,
            "no_warnings": True, "noprogress": True, "socket_timeout": 20,
            "retries": 1, "fragment_retries": 1, "max_filesize": 100 * 1024 * 1024,
            "outtmpl": str(root / "source.%(ext)s"),
            "match_filter": lambda info, *, incomplete: "Choose a reference shorter than 15 minutes." if (info.get("duration") or 0) > 900 else None,
        }
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(url, download=True) or {}
        except Exception as exc:
            message = str(exc).lower()
            if any(word in message for word in ("sign in", "not a bot", "cookies", "private", "drm")):
                raise ValueError("This service requires access or browser verification. Choose an audio file or another public link.") from exc
            raise ValueError("Could not retrieve audio from this link. Try a public song link or choose an audio file.") from exc
        source = next((p for p in root.glob("source.*") if p.is_file() and p.suffix not in {".part", ".json", ".ytdl"}), None)
        if source is None:
            raise ValueError("The link returned no audio. Choose one song shorter than 15 minutes.")
        if source.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("Choose a smaller reference audio file.")
        output = root / "ready.wav"
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(source), "-t", "900", "-map", "0:a:0", "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s24le", str(output)], check=True, capture_output=True, timeout=180)
        except (subprocess.SubprocessError, OSError) as exc:
            raise ValueError("This link did not contain readable audio. Choose an audio file or another link.") from exc
        target = work_dir / "reference-link.wav"
        output.replace(target)
        return target, str(info.get("title") or "Online reference")
