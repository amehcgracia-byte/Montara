"""Closed operator-only worker-script selection for the existing root broker.

A browser request never contains, selects or changes this path. It is a
fixed server startup flag in the privileged systemd unit. The new Chema
workspace script is opt-in, not the default and requires a pinned JM bundle.

Keep the two previously permitted worker paths unchanged for rollback.
"""
from __future__ import annotations

import stat
from pathlib import Path

LEGACY_WORKER = "/opt/montara/broker/private_broker_worker.py"
SMART_PILOT_WORKER = "/opt/montara/broker-smart-candidate/private_broker_worker.py"
NATIVE_CHEMA_WORKER = "/opt/montara/broker-smart-candidate/native_owner_systemd_worker.py"
_ALLOWED = frozenset((LEGACY_WORKER, SMART_PILOT_WORKER, NATIVE_CHEMA_WORKER))


def trusted_operator_worker_script(worker_script: str | None,
                                   *, jm_bundle: Path | None) -> str:
    """Reject arbitrary runners, symlinks and scripts writable by non-root."""
    selected = LEGACY_WORKER if worker_script is None else worker_script
    if not isinstance(selected, str) or selected not in _ALLOWED:
        raise ValueError("Unapproved root-owned worker runner")
    if selected == NATIVE_CHEMA_WORKER and jm_bundle is None:
        raise ValueError("Native Chema requires a pinned JM bundle")
    path = Path(selected)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Untrusted private worker runner")
    details = path.stat()
    if details.st_uid != 0 or details.st_mode & 0o022 or not stat.S_ISREG(details.st_mode):
        raise ValueError("Untrusted private worker runner")
    return selected
