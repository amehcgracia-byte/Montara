"""Messaging apps display MP3 tags; renaming a file cannot fix stale session tags."""
import hashlib
import json
import subprocess

from mixer_adapter.single_song import tag_song_export


def test_export_uses_the_chosen_title_and_track_number_without_reencoding(tmp_path):
    path = tmp_path / '04.mp3'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=1',
                    '-metadata', 'album=Jam 2020-01-01', '-metadata', 'artist=ZuckerZauberSessions',
                    '-metadata', 'title=01 - Old song', str(path)], check=True)
    def audio_hash():
        # Hash the compressed audio packets, not the container/ID3 headers.
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                                       '-c:a', 'copy', '-f', 'hash', '-hash', 'sha256', '-'])
        return hashlib.sha256(raw).hexdigest()
    before = audio_hash()
    tag_song_export(path, 'Mi canción 04', 4)
    tags = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(path)]))['format']['tags']
    assert tags['title'] == 'Mi canción 04' and tags['track'] == '4'
    assert 'artist' not in tags and 'album' not in tags
    assert audio_hash() == before
