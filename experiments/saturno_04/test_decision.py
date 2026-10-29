from dataclasses import replace
import pytest
from decision import Scenario,evaluate

def test_default():
    r=evaluate(Scenario())
    assert r["remote_partial_seconds"]==2310
    assert r["remote_full_seconds"]==7610
    assert r["max_package_gb_to_beat_local"]==26.125
    assert r["partial_faster"]

def test_threshold_boundary():
    s=Scenario()
    threshold=evaluate(s)["max_package_gb_to_beat_local"]
    assert not evaluate(replace(s,package_gb=threshold))["partial_faster"]
    assert evaluate(replace(s,package_gb=threshold-.001))["partial_faster"]

def test_no_possible_speedup():
    r=evaluate(replace(Scenario(),local_render_s=100))
    assert r["max_package_gb_to_beat_local"]==0
    assert r["min_upload_mbps_to_beat_local"] is None

def test_slower_upload():
    s=Scenario()
    assert evaluate(replace(s,upload_mbps=20))["remote_partial_seconds"]>evaluate(s)["remote_partial_seconds"]

def test_full_package_has_preparation_overhead():
    r=evaluate(replace(Scenario(),package_gb=80))
    assert r["remote_partial_seconds"]-r["remote_full_seconds"]==300

@pytest.mark.parametrize("field,value",[("upload_mbps",0),("local_render_s",float("nan")),("package_gb",81),("cloud_usd_hour",-1)])
def test_invalid(field,value):
    with pytest.raises(ValueError):evaluate(replace(Scenario(),**{field:value}))
