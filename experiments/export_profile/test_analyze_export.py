import json
import pytest
from analyze_export import analyze,read

def example(total,cached,mux):
    return {"segment_count":2,"segment_workers":2,"total_wall_sec":total,
        "wall_sec":total-2,"phases":{"mux_sec":mux,"concat_sec":.25},
        "segments":[{"cached":cached},{"cached":cached}]}

def test_cold_warm():
    result=analyze(example(10,False,2),example(4,True,1.5))
    assert result["comparable"] and result["total_reduction_pct"]==60
    assert result["warm_cache_hits"]==2
    assert result["phases"][0]["phase"]=="mux_sec"

def test_mismatched_worker_rejected():
    c=example(10,False,2);w=example(4,True,1);w["segment_workers"]=4
    assert not analyze(c,w)["comparable"]

def test_bad_time_rejected():
    assert not analyze(example(10,False,2),example(0,True,1))["comparable"]

def test_missing_manifest_performance(tmp_path):
    f=tmp_path/"manifest.json";f.write_text(json.dumps({"status":"ok"}))
    with pytest.raises(ValueError,match="missing export performance"):
        read(f)

def test_does_not_sum_parallel_segment_times():
    c=example(12,False,2);w=example(5,True,2)
    w["segments"]=[{"cached":True,"verify_sec":40},{"cached":True,"verify_sec":40}]
    r=analyze(c,w)
    assert r["warm_total_sec"]==5 and "verify_sec" not in r
