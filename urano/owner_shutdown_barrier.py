"""I6c broker-side admission barrier and guarded shutdown transaction.

Disabled until the operator provisions the same 0700 root-owned runtime
directory for broker and watchdog. This module cannot power off a VM itself.
"""
from __future__ import annotations

import fcntl
import os
import stat
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Callable

from urano.owner_poweroff_guard import may_poweroff

ROOT = Path("/run/montara-owner-shutdown")
LOCK = "admission.lock"
DRAINING = "draining"


class OwnerShutdownBlocked(RuntimeError):
    """No verified, mutually exclusive shutdown/admission decision."""


class OwnerShutdownBarrier:
    def __init__(self, root: Path = ROOT):
        if not isinstance(root, Path) or not root.is_absolute() or root.is_symlink():
            raise OwnerShutdownBlocked("Untrusted admission barrier root")
        try:
            mode = root.stat()
        except OSError as exc:
            raise OwnerShutdownBlocked("Admission barrier must be provisioned") from exc
        if (not stat.S_ISDIR(mode.st_mode) or mode.st_mode & 0o077
                or mode.st_uid != os.geteuid()):
            raise OwnerShutdownBlocked("Admission barrier is not private to controller")
        self.root = root

    @contextmanager
    def _lock(self, exclusive: bool):
        path = self.root / LOCK
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o600)
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                    or info.st_uid != os.geteuid()):
                raise OwnerShutdownBlocked("Untrusted admission lock")
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        except OSError as exc:
            raise OwnerShutdownBlocked("Could not lock admission barrier") from exc
        finally:
            if "fd" in locals():
                os.close(fd)

    def _draining(self) -> bool:
        marker = self.root / DRAINING
        return marker.exists() or marker.is_symlink()

    @contextmanager
    def admit(self):
        """Hold shared lock for the entire privileged Engine start."""
        with self._lock(exclusive=False):
            if self._draining():
                raise OwnerShutdownBlocked("VM draining: new Engine denied")
            yield

    def shutdown_if_idle(self, ledgers: tuple[Path, ...], request_poweroff: Callable[[], None]) -> bool:
        """Trusted final gate, run only after SSH/FFmpeg/benchmark checks.

        Holds exclusive lock while checking ledgers and arming draining. A
        successful request keeps the marker until reboot; if OS poweroff
        request fails, marker is removed so the operator can retry.
        """
        if not callable(request_poweroff):
            raise OwnerShutdownBlocked("Trusted poweroff callback required")
        with self._lock(exclusive=True):
            if self._draining():
                raise OwnerShutdownBlocked("Shutdown already in progress")
            if not may_poweroff(ledger_paths=ledgers):
                return False
            marker = self.root / DRAINING
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
            os.close(fd)
            try:
                request_poweroff()
            except BaseException:
                marker.unlink(missing_ok=True)
                raise
            return True


def guarded_owner_start(fn):
    """Opt-in decorator on the existing trusted broker's sole start path."""
    @wraps(fn)
    def invoke(*args, **kwargs):
        if os.environ.get("MONTARA_OWNER_SHUTDOWN_GATE") != "1":
            return fn(*args, **kwargs)
        with OwnerShutdownBarrier().admit():
            return fn(*args, **kwargs)
    return invoke
