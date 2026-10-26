import copy
import json
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from flask import Flask

from push_pack import PushPacks, clipped_cues, register_push_pack, suggest_regions, write_ass


def seeded(tmp_path):
    store = PushPacks(tmp_path, tmp_path / 'fixtures')
    data = {'id': uuid.uuid4().hex, 'status': 'ready', 'duration': 80, 'length': 15, 'format': '9:16',
            'layout_version':2, 'message': '', 'source': str(tmp_path / 'input.mp4'), 'url': '', 'title': 'Test', 'revision': 0,
            'captions_status': 'ready', 'captions_message': '', 'cues': [{'start': 19, 'end': 22, 'text': 'A real phrase'}],
            'reels': suggest_regions(80, 15, [1]*80)}
    store.save(data)
    return store, data


def test_four_distinct_regions_follow_energy_and_fit_source():
    energies = [0]*120
    for peak in [10, 40, 70, 100]:
        energies[peak:peak+5] = [10]*5
    regions = suggest_regions(120, 5, energies)
    assert len(regions) == 4
    assert [r['start'] for r in regions] == [10, 40, 70, 100]
    assert all(a['end'] <= b['start'] for a, b in zip(regions, regions[1:]))
    short = suggest_regions(20, 30, [])
    assert [(r['start'], r['end']) for r in short] == [(0,5), (5,10), (10,15), (15,20)]


def test_clip_words_at_boundaries_and_retime_to_reel():
    cues = [{'start': 8, 'end': 14, 'text': 'before inside after', 'words': [
        {'start':8,'end':9,'text':'before'}, {'start':10,'end':11,'text':'inside'}, {'start':13,'end':14,'text':'after'}]}]
    result = clipped_cues(cues, 9.5, 12)
    assert result[0]['text'] == 'inside'
    assert result[0]['words'][0]['start'] == .5
    assert 0 <= result[0]['start'] < result[0]['end'] <= 2.5


def test_stale_changes_and_invalid_caption_are_atomic(tmp_path):
    store, data = seeded(tmp_path)
    store.patch(data['id'], '1', {'revision':0, 'start':1, 'end':12})
    before = store.load(data['id'])
    with pytest.raises(ValueError, match='changed'):
        store.patch(data['id'], '1', {'revision':0, 'start':2})
    with pytest.raises(ValueError, match='caption'):
        store.patch(data['id'], '1', {'revision':1, 'start':3, 'captions':[{'start':0,'end':99,'text':'invalid'}]})
    assert store.load(data['id']) == before


def test_manual_words_survive_retiming_in_source_time(tmp_path):
    store, data = seeded(tmp_path)
    store.patch(data['id'], '1', {'revision':0, 'captions':[{'start':4,'end':8,'text':'Corrected lyric'}]})
    current = store.patch(data['id'], '1', {'revision':1, 'start':5, 'end':14})
    cue = current['reels'][0]['captions'][0]
    assert cue['start'] == 0 and cue['end'] == 3 and cue['text'] == 'Corrected lyric'


def test_render_failure_does_not_stop_other_reels_or_export_unselected(tmp_path, monkeypatch):
    store, data = seeded(tmp_path)
    def render(data, reel):
        if reel['id'] == '2':
            raise ValueError('Test failure')
        (store.folder(data['id']) / f"reel-{reel['id']}.mp4").write_bytes(b'export')
    monkeypatch.setattr(store, 'render_one', render)
    store.export(data['id'], ['1','2','4'])
    deadline = time.time()+5
    while time.time()<deadline:
        result = store.load(data['id'])
        if all(r['render']['status'] not in {'queued','running'} for r in result['reels']):
            break
        time.sleep(.02)
    assert [r['render']['status'] for r in result['reels']] == ['ready','failed','idle','ready']
    assert not (store.folder(data['id'])/'reel-3.mp4').exists()
    monkeypatch.setattr(store, 'render_one', lambda d,r: None)
    store.export(data['id'], ['2'])
    deadline = time.time()+5
    while time.time()<deadline and store.load(data['id'])['reels'][1]['render']['status'] != 'ready':
        time.sleep(.02)
    assert store.load(data['id'])['reels'][0]['render']['status'] == 'ready'


def test_routes_validate_sources_and_pack_identifiers(tmp_path):
    app = Flask(__name__)
    register_push_pack(app, tmp_path, tmp_path/'fixtures')
    client = app.test_client()
    assert client.post('/montara/push/packs', json={'source':'/etc/passwd'}).status_code == 400
    assert client.post('/montara/push/packs', json={'source':'one.mp4','url':'https://example.com'}).status_code == 400
    assert client.post('/montara/push/packs', json={'url':'http://127.0.0.1/video.mp4'}).status_code == 400
    assert client.get('/montara/push/packs/not-an-id').status_code == 400
    assert client.get('/montara/push/packs/not-an-id/media').status_code == 404


def test_restart_preserves_edits_and_exposes_interrupted_job(tmp_path):
    store, data = seeded(tmp_path)
    data['reels'][0]['start'] = 2
    data['reels'][0]['render']['status'] = 'running'
    data['captions_status'] = 'running'
    store.save(data)
    restarted = PushPacks(tmp_path, tmp_path/'fixtures')
    restored = restarted.load(data['id'])
    assert restored['reels'][0]['start'] == 2
    assert restored['reels'][0]['render']['status'] == 'failed'
    assert restored['captions_status'] == 'failed'


@pytest.mark.parametrize('zoom',[.25,1.4])
@pytest.mark.parametrize('fmt,style', [('9:16','clean'),('16:9','words'),('mix','glow'),('mix_vertical_horizontal','bold')])
def test_real_ffmpeg_independent_export_audio_captions_and_duration(tmp_path, fmt, style, zoom):
    source = tmp_path/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=320x180:r=25:d=3','-f','lavfi','-i','sine=f=440:d=3',
                    '-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(source)], check=True)
    store, data = seeded(tmp_path)
    data['source'] = str(source)
    data['format'] = fmt
    reel = data['reels'][1]
    reel['framing']={'x':.8,'y':.3,'zoom':zoom}
    reel.update(start=.4, end=1.6, caption_style=style, caption_edits=[{'start':.5,'end':1.2,'text':'A lyric {not ASS code}'}])
    store.save(data)
    store.render_one(data, reel)
    output = store.folder(data['id'])/'reel-2.mp4'
    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(output)]))
    assert abs(float(info['format']['duration'])-1.2) < .12
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    assert (video['width'],video['height']) == (720,1280)
    assert any(s['codec_type']=='audio' for s in info['streams'])
    assert not (store.folder(data['id'])/'reel-1.mp4').exists()
    assert not output.with_suffix('.part.mp4').exists()
    ass = (store.folder(data['id'])/'reel-2.ass').read_text()
    assert '{not ASS code}' not in ass and '(not' in ass and 'code)' in ass


def test_corrected_words_keep_acoustic_timing_and_alignment_is_not_uniform(tmp_path, monkeypatch):
    import numpy as np
    import push_pack
    from faster_whisper import audio
    store,data=seeded(tmp_path)
    monkeypatch.setattr(store,'transcription_audio',lambda _: tmp_path/'speech.wav')
    monkeypatch.setattr(audio,'decode_audio',lambda *a,**k: np.zeros(80*16000,dtype=np.float32))
    monkeypatch.setattr(push_pack,'align_text',lambda *a:[{'text':'Corrected','start':2.2,'end':2.5},{'text':'lyric','start':3.5,'end':4.6}])
    data['language']='en';data['reels'][0]['caption_edits']=[{'start':4,'end':8,'text':'Corrected lyric'}];store.save(data)
    store.align_reel(data['id'],'1')
    result=store.public(data['id'])['reels'][0]
    assert result['alignment_status']=='ready'
    assert [w['start'] for w in result['captions'][0]['words']]==[4.2,5.5]
    saved=store.patch(data['id'],'1',{'revision':result['revision'],'captions':[{'start':result['captions'][0]['start'],'end':result['captions'][0]['end'],'text':'Corrected lyric'}]})
    assert saved['reels'][0]['captions'][0]['words']==result['captions'][0]['words']


def test_framing_validation_is_atomic_and_changes_only_one_reel(tmp_path):
    store,data=seeded(tmp_path)
    before=store.load(data['id'])
    for invalid in [{'x':float('nan')},{'zoom':0},{'y':2}]:
        with pytest.raises(ValueError):store.patch(data['id'],'1',{'revision':0,'framing':invalid})
        assert store.load(data['id'])==before
    result=store.patch(data['id'],'1',{'revision':0,'framing':{'x':.8,'y':.3,'zoom':1.6}})
    assert result['reels'][0]['framing']=={'x':.8,'y':.3,'zoom':1.6}
    assert result['reels'][1]['framing']=={'x':.5,'y':.5,'zoom':1.}


def test_word_export_uses_acoustic_times_without_even_spacing(tmp_path):
    target=tmp_path/'captions.ass'
    write_ass(target,[{'start':0,'end':4,'text':'first second','words':[{'text':'first','start':.3,'end':.7},{'text':'second','start':2.1,'end':3.8}]}],'words',720,1280)
    content=target.read_text()
    assert '0:00:00.30,0:00:00.70' in content and '0:00:02.10,0:00:03.80' in content


def test_detected_lyrics_can_replace_manual_override_explicitly(tmp_path):
    store,data=seeded(tmp_path)
    data['reels'][1]['caption_edits']=[{'start':21,'end':23,'text':'Written by hand'}]
    store.save(data)
    before=store.public(data['id'])['reels'][1]
    assert before['captions_edited']
    result=store.patch(data['id'],'2',{'revision':0,'use_detected_captions':True})
    assert not result['reels'][1]['captions_edited']
    assert result['reels'][1]['captions'][0]['text']=='A real phrase'


def test_only_the_exact_included_link_reuses_original_source(tmp_path):
    store,data=seeded(tmp_path);root=tmp_path/'fixtures/push-links';root.mkdir(parents=True)
    (root/'source.mp4').write_bytes(b'raw source, not a prepared reel')
    (root/'catalog.json').write_text(json.dumps({'youtube:example-id':{'file':'source.mp4','title':'Original'}}))
    path,title=store.download(data['id'],'https://www.youtube.com/watch?v=example-id')
    assert path==root/'source.mp4' and title=='Original'
    assert store.public(data['id'])['cached_source'] is True


def test_transcript_cache_is_bound_to_exact_source_and_model(tmp_path):
    import hashlib
    store,data=seeded(tmp_path);source=Path(data['source']);source.write_bytes(b'original media')
    data['cached_source']=True;store.save(data)
    folder=tmp_path/'fixtures/push-links';folder.mkdir(parents=True)
    cache={'model':'large-v3','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'language':'en','cues':[{'start':4,'end':5,'text':'Actual','words':[{'start':4,'end':5,'text':'Actual'}]}]}
    (folder/'captions-large-v3.json').write_text(json.dumps(cache))
    assert store.restore_transcript_cache(data['id'])
    assert store.public(data['id'])['cached_captions'] is True
    source.write_bytes(b'different media')
    assert not store.restore_transcript_cache(data['id'])


def test_music_markers_trigger_the_same_medium_fallback_as_native_reader(tmp_path,monkeypatch):
    from types import SimpleNamespace as NS
    import push_pack
    store,data=seeded(tmp_path);calls=[]
    monkeypatch.setattr(store,'transcription_audio',lambda _:tmp_path/'speech-16k.wav')
    def model(name=None):
        calls.append(name)
        text='🎵 Music' if name=='small' else 'Real lyric'
        words=[NS(word=w,start=i+1,end=i+1.5) for i,w in enumerate(text.split())]
        return NS(transcribe=lambda *a,**k:(iter([NS(text=text,words=words,end=4)]),NS(language='en')))
    monkeypatch.setattr(push_pack,'speech_model',model)
    store.transcribe(data['id'])
    assert calls==['small','medium']
    result=store.load(data['id'])
    assert result['captions_model']=='medium' and result['captions_sample_rate']==16000
    assert [c['text'] for c in result['cues']]==['Real lyric']


def test_resume_is_available_after_a_new_browser_origin_without_skipping_setup(tmp_path):
    app=Flask(__name__);register_push_pack(app,tmp_path,tmp_path/'fixtures')
    store,data=seeded(tmp_path)
    result=app.test_client().get('/montara/push/packs/latest')
    assert result.status_code==200 and result.json['id']==data['id']
    before=(store.folder(data['id'])/'pack.json').stat().st_mtime_ns
    PushPacks(tmp_path,tmp_path/'fixtures')
    assert (store.folder(data['id'])/'pack.json').stat().st_mtime_ns==before


def test_case_correction_preserves_clipped_acoustic_words(tmp_path):
    store,data=seeded(tmp_path)
    data['cues']=[{'start':18,'end':23,'text':'outside inside','words':[{'start':18,'end':19,'text':'outside'},{'start':21,'end':22,'text':'inside'}]}]
    store.save(data)
    current=store.public(data['id'])['reels'][1]
    assert current['captions'][0]['text']=='inside'
    result=store.patch(data['id'],'2',{'revision':0,'captions':[{'start':0,'end':3,'text':'INSIDE!'}]})
    cue=result['reels'][1]['captions'][0]
    assert cue['text']=='INSIDE!' and cue['words']==[{'start':1,'end':2,'text':'INSIDE!'}]


def test_reread_selected_moved_reel_uses_new_audio_range_and_replaces_only_its_text(tmp_path,monkeypatch):
    from types import SimpleNamespace as NS
    import push_pack
    store,data=seeded(tmp_path)
    data['reels'][0].update(start=31,end=49,caption_edits=[{'start':4,'end':6,'text':'old manual text'}])
    store.save(data);commands=[]
    monkeypatch.setattr(store,'transcription_audio',lambda _:tmp_path/'speech.wav')
    monkeypatch.setattr(push_pack,'run',lambda cmd,**kw:commands.append(cmd))
    monkeypatch.setattr(push_pack,'speech_model',lambda _:NS(transcribe=lambda path,**kw:(iter([NS(text='New words',words=[NS(word='New',start=1,end=1.3),NS(word='words',start=2,end=2.8)],end=3)]),NS(language='en'))))
    store.transcribe(data['id'],'1',(31,49))
    current=store.load(data['id']);reel=store.public(data['id'])['reels'][0]
    assert commands[0][commands[0].index('-ss')+1]=='31'
    assert commands[0][commands[0].index('-t')+1]=='18'
    assert reel['captions'][0]['text']=='New words'
    assert reel['captions'][0]['words'][0]['start']==1
    assert reel['lyrics_region']==[31,49] and reel['lyrics_status']=='ready'
    assert current['cues']==data['cues'] and current['reels'][1:]==data['reels'][1:]
    assert not list(store.folder(data['id']).glob('read-*.wav'))


def test_failed_reel_read_preserves_manual_text_and_can_retry(tmp_path,monkeypatch):
    import push_pack
    store,data=seeded(tmp_path)
    data['reels'][0]['caption_edits']=[{'start':4,'end':6,'text':'Keep my text'}];store.save(data)
    monkeypatch.setattr(store,'transcription_audio',lambda _: (_ for _ in ()).throw(RuntimeError('test')))
    store.transcribe(data['id'],'1',(0,15))
    assert store.load(data['id'])['reels'][0]['caption_edits']==data['reels'][0]['caption_edits']
    assert store.public(data['id'])['reels'][0]['lyrics_status']=='failed'


def test_changing_layout_keeps_cuts_captions_and_independent_frames(tmp_path):
    store,data=seeded(tmp_path)
    data['reels'][0]['framing']['zoom']=.25;data['reels'][1]['render']={'status':'ready'};store.save(data)
    updated=store.set_format(data['id'],{'revision':0,'format':'mix'})
    assert updated['format']=='mix' and updated['reels'][0]['framing']['zoom']==.25
    assert updated['reels'][0]['start']==data['reels'][0]['start']
    assert all(r['render']['status']=='idle' for r in updated['reels'])
    with pytest.raises(ValueError):store.set_format(data['id'],{'revision':0,'format':'9:16'})


def test_previous_layout_export_invalidated_without_losing_user_work(tmp_path):
    store,data=seeded(tmp_path);data.pop('layout_version');data['format']='16:9'
    data['reels'][0].update(start=2,end=9,caption_edits=[{'start':3,'end':4,'text':'My words'}],render={'status':'ready'})
    store.save(data)
    restored=PushPacks(tmp_path,tmp_path/'fixtures').load(data['id'])
    assert restored['layout_version']==2
    assert restored['reels'][0]['start']==2 and restored['reels'][0]['end']==9
    assert restored['reels'][0]['caption_edits']==data['reels'][0]['caption_edits']
    assert restored['reels'][0]['render']['status']=='idle'


def test_ratio_change_invalidates_exports_but_preserves_cuts_and_text(tmp_path):
    store,data=seeded(tmp_path);before=copy.deepcopy(data)
    for value in ['nonsense',float('nan'),1.5]:
        with pytest.raises(ValueError):store.set_format(data['id'],{'revision':0,'mix_vertical_ratio':value})
    assert store.load(data['id'])==before
    updated=store.set_format(data['id'],{'revision':0,'format':'mix','mix_vertical_ratio':.75})
    assert updated['mix_vertical_ratio']==.75
    assert updated['reels'][0]['start']==before['reels'][0]['start']
