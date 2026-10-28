"""Candidate cgroup v2 overlap guard, independent of the production engine."""
from pathlib import Path

def overlap_allowed(host_total, host_available, *, cgroup=Path('/sys/fs/cgroup')):
    """Retain host policy; veto when cgroup v2 memory is too limited.

    Missing/unlimited cgroups preserve legacy behavior. A finite limit whose
    current usage cannot be read fails closed for overlap (serial verification).
    """
    if host_total < 16 * 1024**3 or host_available < 2 * 1024**3:
        return False
    try:
        raw = (cgroup / 'memory.max').read_text().strip()
        if raw == 'max':
            return True
        limit = int(raw)
        if limit < 16 * 1024**3:
            return False
        current = int((cgroup / 'memory.current').read_text().strip())
        return current >= 0 and limit - current >= 2 * 1024**3
    except (OSError, ValueError):
        try:
            return not (cgroup / 'memory.max').exists()
        except OSError:
            return True
