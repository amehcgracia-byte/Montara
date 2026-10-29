"""Run with: python -m pytest -q experiments/saturno_03/test_av_timeline_gate.py"""
import hashlib,importlib.util,subprocess
from pathlib import Path
import pytest

SOURCE=Path(__file__).with_name("av_timeline_gate.py")
spec=importlib.util.spec_from_file_location("av_timeline_gate",SOURCE)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def ff(*args):
    subprocess.run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
        *map(str,args)],check=True)

@pytest.fixture(scope="module")
def media(tmp_path_factory):
    d=tmp_path_factory.mktemp("saturn-av")
    src=d/"source.mp4";frag=d/"fragment.mp4";master=d/"master.wav"
    ff("-f","lavfi","-i","testsrc2=size=128x72:rate=30:duration=5",
        "-c:v","libx264","-g","120","-bf","2",src)
    ff("-ss","2.2","-i",src,"-t","1.0","-c","copy",frag)
    ff("-f","lavfi","-i","sine=frequency=440:duration=3",
        "-c:a","pcm_s16le",master)
    return frag,master

def test_pts_are_evidence_not_certification(media):
    f,_=media
    r=gate.check_media(f,0,0.2,0.3)
    assert r["status"]=="BLOCKED_SOURCE_TIMELINE_UNPROVEN"
    assert r["decoded_frame_count"]>0

def test_audio_master_verified(media):
    f,m=media;sha=hashlib.sha256(m.read_bytes()).hexdigest()
    assert gate.check_media(f,0,0.2,0.3,m,sha)["master"]["sha256"]==sha

def test_master_sha_changed(media):
    f,m=media
    with pytest.raises(ValueError,match="master SHA mismatch"):
        gate.check_media(f,0,0.2,0.3,m,"0"*64)

def test_missing_master(media,tmp_path):
    f,_=media
    with pytest.raises(ValueError,match="missing master"):
        gate.check_media(f,0,0.2,0.3,tmp_path/"absent","0"*64)

def test_invalid_time(media):
    f,_=media
    with pytest.raises(ValueError,match="invalid"):
        gate.check_media(f,0,float("nan"),0.3)

def test_missing_fragment(tmp_path):
    with pytest.raises(ValueError,match="missing fragment"):
        gate.check_media(tmp_path/"absent",0,0,1)
