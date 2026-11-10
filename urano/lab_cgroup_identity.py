"""Small stdlib-only I20 lab cgroup verification; no Engine/OIDC imports.

Not a production broker authorization boundary. Never interpret empty
ControlGroup as permission to read /sys/fs/cgroup/cgroup.procs.
"""
from __future__ import annotations
import os
import re
from pathlib import Path

def attested_cgroup_empty(unit: str, group: str) -> bool:
    """Inspect ONLY an already-attested I20 user service; never cgroup root."""
    if not re.fullmatch(r'montara-i20-lab-[0-9a-f]{12}', unit):
        raise ValueError('Unrecognized I20 lab unit')
    uid = os.getuid()
    expected = (f'/user.slice/user-{uid}.slice/user@{uid}.service/'
                f'app.slice/{unit}.service')
    if group != expected:
        raise ValueError('Unrecognized target cgroup identity')
    procs = Path('/sys/fs/cgroup') / group.lstrip('/') / 'cgroup.procs'
    try:
        return not procs.read_text().split()
    except FileNotFoundError:
        # systemd has unloaded the attested unit and removed its cgroup.
        return True


