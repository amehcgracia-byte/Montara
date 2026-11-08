import hashlib
import importlib.util
import json
from pathlib import Path
from resumable_upload import preview_original

ROOT=Path(__file__).resolve().parents[1]

def test_completed_video_proxy_retains_upload_identity_without_audio_restore(tmp_path):
    path=tmp_path/'logo.small.mp4';path.write_bytes(b'preview')
    original={'name':'logo.MOV','size':123,'fingerprint':'a'*64}
    (tmp_path/'upload.json').write_text(json.dumps({'name':path.name,'complete':True,'preview_of':original}))
    assert preview_original(path)==original
    assert preview_original(tmp_path/'different.small.mp4') is None

def test_companion_revalidates_stale_cache_and_reconnects_registered_renamed_bytes(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'companion'))
    monkeypatch.setenv('MONTARA_COMPANION_HOME',str(tmp_path/'home'))
    spec=importlib.util.spec_from_file_location('identity_companion',ROOT/'companion/companion.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    monkeypatch.setattr(helper,'locate',lambda *args:None)
    stale=tmp_path/'old.mp4';stale.write_bytes(b'changed')
    fresh=tmp_path/'renamed.mov';fresh.write_bytes(b'original')
    original={'name':'old.mp4','size':8,'fingerprint':helper.fingerprint(fresh)}
    key=hashlib.sha256(f"{original['name']}|{original['size']}|{original['fingerprint']}".encode()).hexdigest()[:24]
    helper.sources[key]=stale
    assert helper.find_original(original) is None
    helper.sources['new-name']=fresh
    assert helper.find_original(original)==fresh
    fresh.unlink()
    assert helper.find_original(original) is None
