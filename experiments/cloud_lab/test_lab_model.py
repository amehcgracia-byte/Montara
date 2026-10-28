import pytest
from lab_model import Scenario, estimate

def s(**kwargs):
    d=dict(input_gib=1,output_gib=.1,upload_mbps=100,download_mbps=100,remote_compute_s=40,local_compute_s=150)
    d.update(kwargs)
    return Scenario(**d)

def test_zero_file_equals_compute():
    assert estimate(s(input_gib=0,output_gib=0))['remote_total_s']==40

def test_network_round_trip():
    r=estimate(s())
    assert r['upload_s']==round(1024**3*8/1e8,2)
    assert r['remote_total_s']>40

def test_queue_can_make_remote_slower():
    assert estimate(s(queue_s=200))['remote_advantage_s']<0

def test_rate_calculation():
    r=estimate(s(input_gib=0,output_gib=0,gpu_usd_per_hour=3.6,startup_s=20,billed_extra_s=40))
    assert r['gpu_compute_bill_usd']==.1

def test_bad_throughput():
    with pytest.raises(ValueError):
        estimate(s(upload_mbps=0))

def test_invalid_nan():
    with pytest.raises(ValueError):
        estimate(s(remote_compute_s=float('nan')))

def test_faster_network_helps():
    assert estimate(s(upload_mbps=1000))['remote_total_s']<estimate(s(upload_mbps=10))['remote_total_s']
