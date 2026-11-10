"""I25 strict control-plane policy for an operator-provisioned systemd helper.

This is NOT a public API and does not install sudo policies. A production
helper must run under a separately authorized account/service socket and
authenticate the local caller before invoking these trusted-only operations.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from urano.job_recovery_ledger import JobLease, JobRecoveryLedger, StaleJob

_JOB = re.compile(r"job-[0-9a-f]{32}\Z")
_UNIT = re.compile(r"montara-i24-job-[0-9a-f]{32}\Z")
# No dynamic systemd properties, shell commands, filenames, paths or UIDs.
SYSTEMD_PROPS = (
    "DynamicUser=yes", "NoNewPrivileges=yes",
    "ProtectHome=yes", "ProtectSystem=strict",
    "PrivateTmp=yes", "PrivateDevices=yes", "PrivateNetwork=yes",
    "RestrictSUIDSGID=yes", "MemoryMax=768M", "TasksMax=64",
    "CPUQuota=100%", "KillMode=control-group", "TimeoutStopSec=3s",
    "SendSIGKILL=yes", "RuntimeDirectoryMode=0700",
)
CGROUP_ROOT = Path("/sys/fs/cgroup")


class UnverifiedTarget(RuntimeError):
    """Never release a reserved job without exact unit/cgroup proof."""


@dataclass(frozen=True)
class ControlledTarget:
    job_id: str
    owner_id: str
    project_id: str
    generation: int
    unit_name: str


def target_name_for(lease: JobLease) -> str:
    if not _JOB.fullmatch(lease.job_id):
        raise ValueError("Invalid trusted job format")
    return "montara-i24-job-" + lease.job_id[4:]


def expected_cgroup(unit: str) -> str:
    if not _UNIT.fullmatch(unit):
        raise ValueError("Foreign or malformed service unit")
    return "/system.slice/" + unit + ".service"


class SystemdControl(Protocol):
    """Private, trusted implementation; not an HTTP client."""
    def show(self, unit: str) -> dict[str, str]: ...
    def stop_exact(self, unit: str) -> None: ...


class RestrictedTargetControl:
    """Allow only an exact trusted ledger entry to identify a stoppable job."""

    def __init__(self, ledger: JobRecoveryLedger, systemd: SystemdControl):
        self.ledger = ledger
        self.systemd = systemd

    def resolve(self, lease: JobLease) -> ControlledTarget:
        # A non-canonical lease from a browser must never reach this point.
        name = target_name_for(lease)
        stored = self.ledger.get_trusted(lease.job_id)
        if (stored is None or stored.owner_id != lease.owner_id or
                stored.project_id != lease.project_id or
                stored.generation != lease.generation or
                stored.state not in ("starting","running","stopping","orphaned")):
            raise StaleJob("Lease is stale or belongs to another owner")
        actual = self.ledger.target_for_trusted(lease)
        if actual is None:
            raise UnverifiedTarget("No persisted service identity")
        # The I24 ledger uses its fixed service namespace: never change
        # a previously committed service identity or broaden matching.
        if actual != name:
            raise UnverifiedTarget("Service is not in ledger service namespace")
        return ControlledTarget(lease.job_id,lease.owner_id,lease.project_id,
                                lease.generation,name)

    def stop_verified(self, lease: JobLease) -> bool:
        target = self.resolve(lease)
        group = expected_cgroup(target.unit_name)
        before = self.systemd.show(target.unit_name)
        if before.get("ControlGroup") not in ("", group):
            raise UnverifiedTarget("Target belongs to another cgroup")
        # If a unit is already absent after a restart, allow only a
        # verified *exact* namespace lookup, not a caller assertion.
        self.systemd.stop_exact(target.unit_name)
        path = CGROUP_ROOT / group.lstrip("/")
        # One bounded verification after signaling; never infer an empty
        # subtree solely from the top-level cgroup.procs.
        for _ in range(40):
            after = self.systemd.show(target.unit_name)
            if after.get("ControlGroup") not in ("", group):
                raise UnverifiedTarget("Cgroup identity changed during stop")
            active = after.get("ActiveState") in ("active","activating","deactivating")
            try:
                events = (path / "cgroup.events").read_text().splitlines()
                populations = [line.split()[1] for line in events if line.startswith("populated ")]
                populated = not populations or populations[0] != "0"
                pids = bool((path / "cgroup.procs").read_text().split())
            except FileNotFoundError:
                populated = False
                pids = False
            if not active and not populated and not pids:
                return True
            time.sleep(.15)
        return False


def fixed_launch_properties(unit: str, bundle_path: Path) -> tuple[str, ...]:
    """Build safe properties only from trusted operator bundle config."""
    expected_cgroup(unit)
    path = Path(bundle_path)
    # No arbitrary bundle location or symlinks. Deployment must additionally
    # require root-owned readonly files under this fixed installation root.
    base = Path("/opt/montara/bundles")
    if (not path.is_absolute() or path.parent != base or
            not re.fullmatch(r"engine-[0-9a-f]{40}",path.name)):
        raise ValueError("Bundle must be version-pinned under /opt/montara/bundles")
    return (*SYSTEMD_PROPS, "RuntimeDirectory="+unit,
            "BindReadOnlyPaths="+str(path)+":/opt/montara-engine")

