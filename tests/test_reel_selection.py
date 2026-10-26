import copy
import numpy as np
from reel_selection import title_intervals, choose_regions, refine_vocal_boundaries
from push_pack import layout_segments


def test_title_cards_excluded_but_static_performance_not_discarded():
    frames=np.random.default_rng(12).integers(40,220,(80,54,96)).astype(float)
    frames[:5]=0;frames[-5:]=255
    excluded=title_intervals(frames)
    assert len(excluded)==2
    regions=choose_regions(80,12,[1]*80,excluded,[8,20,32,44,56,68,74])
    assert len(regions)==4
    assert all(not (r['start']<b and r['end']>a) for r in regions for a,b in excluded)
    assert all(a['end']<=b['start'] for a,b in zip(regions,regions[1:]))
    assert title_intervals(np.zeros((80,54,96)))==[]


def test_phrase_refinement_never_overwrites_manual_cuts_or_words():
    base={'duration':80,'selection':{},'cues':[{'words':[{'start':2,'end':4,'text':'one'},{'start':5,'end':7,'text':'two'}]}],
          'reels':[{'start':3,'end':6,'revision':0,'render':{'status':'idle'},'suggested_bounds':[0,20]}]}
    for flag in [{'cuts_edited':True},{'caption_edits':[{'text':'mine'}]}]:
        data=copy.deepcopy(base);data['reels'][0].update(flag);before=copy.deepcopy(data['reels'])
        refine_vocal_boundaries(data);assert data['reels']==before
    refine_vocal_boundaries(base)
    r=base['reels'][0]
    assert r['start']<=2 and r['end']>=7


def test_mix_and_alternate_have_different_meanings_and_exact_share():
    reel={'id':'1','start':5,'end':35}
    spans=layout_segments({'format':'mix','mix_vertical_ratio':.75},reel)
    assert {s['layout'] for s in spans}=={'vertical','horizontal'}
    assert sum(s['end']-s['start'] for s in spans if s['layout']=='vertical')==22.5
    assert spans[0]['start']==0 and spans[-1]['end']==30
    assert all(a['end']==b['start'] for a,b in zip(spans,spans[1:]))
    assert layout_segments({'format':'mix_vertical_horizontal'},reel)[0]['layout']=='vertical'
    assert layout_segments({'format':'mix_vertical_horizontal'},{**reel,'id':'2'})[0]['layout']=='horizontal'
