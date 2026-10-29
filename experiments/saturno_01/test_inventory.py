import pytest
from inventory import inventory,merge

def seg(src,start,length,**kw):
    return dict(source_path=src,clip_start_sec=start,duration_sec=length,**kw)

def test_overlap():
    x=inventory([seg("a",0,10),seg("a",5,10)])
    assert x["sources"][0]["intervals_sec"]==[[0,15]]
    assert x["sources"][0]["unique_used_duration_sec"]==15

def test_two_cameras():
    x=inventory({"segments":[seg("a",1,2),seg("b",1,2)]})
    assert (x["source_count"],x["segment_count"])==(2,2)

def test_disjoint():
    assert inventory([seg("a",0,1),seg("a",3,2)])["sources"][0]["intervals_sec"]==[[0,1],[3,5]]

def test_clip_fallback():
    assert inventory([dict(clip_path="x",clip_start_sec=0,duration_sec=2)])["source_count"]==1

@pytest.mark.parametrize("bad",[
    seg("a",0,-1),seg("a",-1,1),seg("a",float("nan"),1),
    dict(source_path="a",clip_start_sec=0),seg("",0,1)
])
def test_reject_bad(bad):
    with pytest.raises(ValueError): inventory([bad])

def test_warns_not_bytes():
    assert "not a transfer estimate" in inventory([seg("a",1,5)])["warnings"][0]

def test_empty():
    with pytest.raises(ValueError): inventory([])

def test_merge_nonmutating():
    xs=[(0,3),(2,5)]
    assert merge(xs)==[[0,5]] and xs==[(0,3),(2,5)]

def test_real_export_plan_shape():
    plan={"platform":"youtube","segments":[
        seg("/media/camA.mp4",1,3,clip_path="/cache/proxy.mp4",master_start_sec=4,
            spherical_shot={"yaw":12},motion={"type":"static"}),
        seg("/media/camA.mp4",3,2,clip_path="/cache/proxy.mp4",master_start_sec=7),
        seg("/media/camB.mp4",12,1,master_start_sec=9)]}
    x=inventory(plan)
    assert x["sources"][0]["intervals_sec"]==[[1,5]]
    assert x["sources"][1]["intervals_sec"]==[[12,13]]

def test_original_precedes_proxy():
    assert inventory([seg("original.mov",0,4,clip_path="proxy.mp4")])["sources"][0]["source"]=="original.mov"
