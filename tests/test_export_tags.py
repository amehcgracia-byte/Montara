"""Export filenames must not compete with embedded titles or unrelated artwork."""
import json
import subprocess

from mixer_adapter.single_song import clean_song_export


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))


def audio_hash(path):
    # Compressed packets, excluding container/ID3 and cover image.
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                                   '-c:a', 'copy', '-f', 'hash', '-hash', 'sha256', '-'])


def test_export_has_no_tags_or_artwork_and_can_be_renamed_without_reencoding(tmp_path):
    path = tmp_path / '04.mp3'
    cover = tmp_path / 'cover.ppm'
    cover.write_bytes(b'P6\n2 2\n255\n' + bytes([255, 0, 0]) * 4)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-i', str(cover),
                    '-map', '0:a', '-map', '1:v', '-c:v', 'png', '-disposition:v', 'attached_pic',
                    '-metadata', 'album=Old Jam', '-metadata', 'artist=Old artist',
                    '-metadata', 'title=01 - Old song', '-metadata', 'track=4',
                    '-metadata', 'comment=Old comment', '-metadata', 'lyrics=Old lyrics',
                    '-write_id3v1', '1', str(path)], check=True)
    assert len(probe(path)['streams']) == 2
    before = audio_hash(path)
    clean_song_export(path)
    renamed = path.with_name('El nombre que elijo.mp3')
    path.rename(renamed)
    info = probe(renamed)
    assert info['format'].get('tags', {}) == {}
    assert len(info['streams']) == 1 and info['streams'][0]['codec_type'] == 'audio'
    assert info['streams'][0].get('tags', {}) == {}
    assert audio_hash(renamed) == before
    stat = renamed.stat()
    clean_song_export(renamed)
    assert renamed.stat().st_mtime_ns == stat.st_mtime_ns  # Serving again does not recopy/rewrite.
