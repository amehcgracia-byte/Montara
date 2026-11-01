"""The FFmpeg command that cuts one track for one song window.

Shared by the server (mixer_adapter/session.py) and the companion's local mixer
(companion/local_mix.py), so a song mixed on the person's computer starts from exactly the
same samples as one mixed on the server. Standard library only.
"""
from __future__ import annotations


def window_command(ffmpeg: str, source: str | None, source_start: float, overlap: float, delay_ms: int,
                   duration: float, channels: int, samplerate: int, target: str) -> list[str]:
    """Cut [source_start, +overlap) of `source`, delay it by `delay_ms`, pad to `duration`.

    A track that does not play in the window (overlap <= 0) becomes silence of the right length."""
    layout = 'mono' if int(channels) == 1 else 'stereo'
    if overlap <= 0 or not source:
        command = [ffmpeg, '-v', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i', f'anullsrc=r={samplerate}:cl={layout}']
        filters = 'anull'
    else:
        command = [ffmpeg, '-v', 'error', '-nostdin', '-y', '-ss', str(source_start), '-t', str(overlap), '-i', str(source)]
        filters = f'adelay={int(delay_ms)}:all=1,apad'
    return command + ['-vn', '-af', filters, '-t', str(duration), '-ac', str(min(int(channels), 2)),
                      '-ar', str(samplerate), '-c:a', 'pcm_f32le', str(target)]
