import pytest
from hardware_gate import examine,run

def test_low_duration():
    with pytest.raises(ValueError): examine(seconds=0)

def test_high_duration():
    with pytest.raises(ValueError): examine(seconds=11)

def test_missing_ffmpeg_fails_cleanly():
    r=examine(binary="/definitely/no/montara/ffmpeg",seconds=1)
    assert not r["cpu_runtime_usable"] and not r["gpu_runtime_usable"]

def test_bad_command():
    assert not run(["/definitely/no/montara/executable"])["ok"]

def test_cpu_smoke_and_runtime_gate():
    r=examine(seconds=1)
    assert r["cpu_runtime_usable"]
    assert r["tests"]["libx264"]["decode_verified"]
    assert "gpu_runtime_usable" in r
