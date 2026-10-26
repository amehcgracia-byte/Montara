from pathlib import Path
import sys,socket
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_import import reference_url,import_reference
@pytest.mark.parametrize('value',['file:///tmp/audio.mp3','ftp://example.com/a','https://name:secret@example.com/audio','http://127.0.0.1/a','http://[::1]/a','https://open.spotify.com/track/test'])
def test_rejects_unusable_links(value):
 with pytest.raises(ValueError):reference_url(value)
def test_converts_download_to_audio(tmp_path,monkeypatch):
 import numpy as np,soundfile as sf,yt_dlp
 monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
 class Download:
  def __init__(self,options):self.options=options
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def extract_info(self,url,download):
   source=Path(self.options['outtmpl'].replace('%(ext)s','wav'))
   sf.write(source,.1*np.sin(2*np.pi*440*np.arange(44100)/44100),44100)
   return {'title':'Reference test'}
 monkeypatch.setattr(yt_dlp,'YoutubeDL',Download)
 path,title=import_reference('https://example.com/audio',tmp_path)
 assert title=='Reference test' and path.is_file()
 info=sf.info(path);assert info.channels==2 and info.samplerate==44100
 assert not [p for p in tmp_path.glob('reference-*') if p.is_dir()]
