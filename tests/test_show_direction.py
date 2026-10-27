"""Text cues, hand edits, real framing API and render integration."""
import json, os, subprocess, sys, time
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from show_direction import direction


def sample():
    words=[]
    for sentence,start in [('Bienvenidos una vez mas a mi canal.',0),('Esto es una prueba sin ninguna sorpresa.',6),('¿Como fue que sali de Cuba?',14),('Seguimos con las cosas de cada dia.',26),('La verdad es que todo cambio.',44)]:
        for n,text in enumerate(sentence.split()): words.append([text,start+n*.4,start+n*.4+.35])
    shots=[dict(index=i,at=i*2,duration=2,zoom=[1,1.3,1.65][i%3],zoom_end=1.8 if i%4==0 else None,move='glide',aimed=i==17) for i in range(30)]
    return dict(scenes=[dict(words=words)]),dict(duration=60,shots=shots)


def test_meaningful_phrases_and_rests_not_cut_numbers():
    doc,n=sample();d=direction(doc,n)
    assert len(d['emphases'])==2
    assert 'Cuba' in d['emphases'][0]['quote']
    assert all(c['zoom']<=1.25 for c in d['emphases'])
    assert d['emphases'][1]['start']-d['emphases'][0]['end']>=10
    assert d['preserved_manual_shots']==1
    assert all(not (r['start']<=34<r['end']) for r in d['ranges'])
    # A different rapid cut rhythm retains the same textual triggers.
    n['shots']=[dict(s,at=i,duration=1,aimed=False) for i,s in enumerate((n['shots']*2))]
    assert [c['quote'] for c in direction(doc,n)['emphases']]==[c['quote'] for c in d['emphases']]


def test_no_words_no_periodic_fallback_and_skip_manual_phrase():
    doc,n=sample();assert direction(dict(scenes=[]),n)['emphases']==[]
    n['shots'][7]['aimed']=True
    assert len(direction(doc,n)['emphases'])==1
    doc['scenes'][0]['words']=[['¿Sabes',14,14.4],['como',14.4,14.8],['es',14.8,15.2],['esto?',15.2,15.6]]
    assert not direction(doc,n)['emphases']


def test_semantic_choices_still_obey_boundaries_and_manual_edits():
    doc,n=sample()
    plan=direction(doc,n,semantic={1:'Important context'})
    assert plan['method']=='llm-reviewed-text'
    assert len(plan['emphases'])==1
    assert 'prueba' in plan['emphases'][0]['quote']
    assert all(not (r['start']<=34<r['end']) for r in plan['ranges'])
    assert direction(doc,n,semantic={})['emphases']==[]


@pytest.fixture
def directed(tmp_path,monkeypatch):
    data=tmp_path/'data';monkeypatch.setenv('ZUCKER_DATA_ROOT',str(data));monkeypatch.delenv('MONTARA_SESSION_TOKEN',raising=False)
    from app import create_montara_app
    app=create_montara_app(data);c=app.test_client()
    from core.project import create_project
    from core import show_scenes,show_proposals
    p=create_project('Text direction',str(data/'Projects/test.zuckervid'))
    source=p.folder/'talk.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=160x90:r=30:d=60','-f','lavfi','-i','sine=frequency=300:duration=60','-c:v','libx264','-preset','ultrafast','-threads','1','-c:a','aac','-shortest',str(source)],check=True)
    doc,n=sample();words=[dict(index=i,text=w[0],start=w[1],end=w[2]) for i,w in enumerate(doc['scenes'][0]['words'])]
    shots=[dict(start_frame=i*60,end_frame=(i+1)*60,zoom=s['zoom'],zoom_end=s['zoom_end'],move='glide',aimed=s['aimed'],face=[.45,.5],words=[w['index'] for w in words if i*2<=w['start']<(i+1)*2]) for i,s in enumerate(n['shots'])]
    plan=dict(source=str(source),style='fast',fps=30,edited_duration=60,source_duration=60,words=words,shots=shots)
    (p.artifacts_dir/'show_plan.json').write_text(json.dumps(plan))
    show_proposals.save(p.artifacts_dir/'show_proposals.json',[],source=str(source),resources=[])
    show_scenes.save(p.artifacts_dir/'show_scenes.json',dict(identity={},scenes=[dict(id='s1',name='Test',start=0,end=60,effects=[],overlays=[],decision='modified',text=' '.join(w['text'] for w in words))]))
    assert c.post('/api/v1/project/open',json={'folder':str(p.folder)}).status_code==200
    return c,p,plan


def test_engine_api_keeps_cuts_manual_sound_and_idempotency(directed):
    c,p,before=directed
    r=c.post('/montara/show/direction',json={});assert r.status_code==200,r.get_json()
    audit=r.get_json();assert audit['applied'] and len(audit['emphases'])==2,audit
    after=json.loads((p.artifacts_dir/'show_plan.json').read_text())
    assert [(s['start_frame'],s['end_frame']) for s in after['shots']]==[(s['start_frame'],s['end_frame']) for s in before['shots']]
    assert after['shots'][17]==before['shots'][17]
    assert after['words']==before['words'] and after['source']==before['source']
    assert all(s.get('zoom_end') is None for i,s in enumerate(after['shots']) if i!=17)
    assert c.post('/montara/show/direction',json={}).get_json()['applied'] is False
    # Undo is a user choice; reopening does not reapply the policy.
    assert c.post('/api/v1/show/narrator/framing',json={'project_id':str(p.folder),'op':'undo'}).status_code==200
    undone=(p.artifacts_dir/'show_plan.json').read_bytes()
    assert c.post('/montara/show/direction',json={}).get_json()['applied'] is False
    assert (p.artifacts_dir/'show_plan.json').read_bytes()==undone


def test_other_modes_remain_unchanged(directed):
    c,p,plan=directed;plan['style']='podcast';path=p.artifacts_dir/'show_plan.json';path.write_text(json.dumps(plan));before=path.read_bytes()
    assert c.post('/montara/show/direction',json={}).get_json()['applied'] is False
    assert path.read_bytes()==before


def test_shared_ai_choices_reach_framing_without_changing_manual_shots(directed):
    c,p,before=directed
    class Reviewed:
        configured=True
        model='simulated-contract-model'
        def review(self,task,evidence):
            assert task.name=='show.gamer.emphases'
            assert str(p.folder) not in json.dumps(evidence)
            return dict(status='reviewed',value={'emphases':[{'id':1,'reason':'Important context'}]},cached=False)
    c.application.extensions['montara_ai']=Reviewed()
    response=c.post('/montara/show/direction',json={})
    assert response.status_code==200,response.get_json()
    audit=response.get_json()
    assert audit['method']=='llm-reviewed-text' and audit['ai_review']['status']=='reviewed'
    assert len(audit['emphases'])==1 and 'prueba' in audit['emphases'][0]['quote']
    after=json.loads((p.artifacts_dir/'show_plan.json').read_text())
    assert after['shots'][17]==before['shots'][17]


def test_directed_preview_renders_with_audio(directed):
    c,p,plan=directed
    assert c.post('/montara/show/direction',json={}).status_code==200
    # Real render, rather than only checking saved JSON.
    response=c.post('/api/v1/show/scenes/s1/preview',json={'next':[]})
    assert response.status_code in (200,202),response.get_json()
    for _ in range(300):
        preview=c.get('/api/v1/show/scenes').get_json()['scenes'][0].get('preview') or {}
        if preview.get('status') in ('ready','failed'):break
        time.sleep(.2)
    assert preview.get('status')=='ready',preview
    media=c.get(preview['url']);assert media.status_code==200
    target=p.folder/'directed-preview.mp4';target.write_bytes(media.data)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(target)]))
    assert abs(float(info['format']['duration'])-60)<.15
    assert {'audio','video'} <= {s['codec_type'] for s in info['streams']}
