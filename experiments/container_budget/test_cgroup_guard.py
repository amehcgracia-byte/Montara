from cgroup_guard import overlap_allowed
G=1024**3

def test_small_container_on_big_host(tmp_path):
    (tmp_path/'memory.max').write_text(str(8*G))
    (tmp_path/'memory.current').write_text(str(2*G))
    assert not overlap_allowed(64*G,60*G,cgroup=tmp_path)

def test_big_container_with_headroom(tmp_path):
    (tmp_path/'memory.max').write_text(str(24*G))
    (tmp_path/'memory.current').write_text(str(8*G))
    assert overlap_allowed(64*G,60*G,cgroup=tmp_path)

def test_big_container_without_headroom(tmp_path):
    (tmp_path/'memory.max').write_text(str(24*G))
    (tmp_path/'memory.current').write_text(str(23*G))
    assert not overlap_allowed(64*G,60*G,cgroup=tmp_path)

def test_unlimited(tmp_path):
    (tmp_path/'memory.max').write_text('max')
    assert overlap_allowed(64*G,60*G,cgroup=tmp_path)

def test_no_cgroup(tmp_path):
    assert overlap_allowed(64*G,60*G,cgroup=tmp_path)

def test_missing_usage_with_finite_limit(tmp_path):
    (tmp_path/'memory.max').write_text(str(24*G))
    assert not overlap_allowed(64*G,60*G,cgroup=tmp_path)

def test_host_not_enough(tmp_path):
    (tmp_path/'memory.max').write_text(str(32*G))
    (tmp_path/'memory.current').write_text('0')
    assert not overlap_allowed(8*G,7*G,cgroup=tmp_path)
