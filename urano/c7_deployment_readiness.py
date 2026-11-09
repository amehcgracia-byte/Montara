"""C7 isolated beta readiness gate. Read-only; never provisions infrastructure.

This script deliberately has no deploy, login, Docker-run, systemctl, GCP,
Cloudflare, or SSH code. It inspects a target's supplied host facts and refuses
to mark a beta 'ready' until the operator has confirmed all isolation gates.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Gate:
    name: str
    ok: bool
    explanation: str


@dataclass(frozen=True)
class Readiness:
    ready_for_private_beta: bool
    gates: tuple[Gate, ...]

    def public_report(self) -> dict:
        # No env, credentials, host paths, private tokens or data returned.
        return {"ready_for_private_beta": self.ready_for_private_beta,
                "gates": [asdict(g) for g in self.gates]}


def check_c7_deployment(
    *,
    docker_cli: bool,
    docker_daemon_access: bool,
    isolated_owner_volumes: bool,
    host_loopback_only: bool,
    trusted_https_proxy: bool,
    pinned_https_origin: bool,
    real_google_oauth_configured: bool,
    private_key_material: bool,
    per_owner_workers: bool,
    separate_existing_services: bool,
    operator_approval: bool,
    collaborator_approval: bool,
    engine_image_pinned: bool,
) -> Readiness:
    """Explicit all-of gate. A pass is a review result, never a deployment."""
    results = (
        Gate("docker_runtime", docker_cli and docker_daemon_access,
             "Pinned Docker image and a working Docker daemon are required"),
        Gate("owner_volume_isolation", isolated_owner_volumes,
             "Each owner must have private storage and independent worker"),
        Gate("loopback_listener", host_loopback_only,
             "Owner API must not listen directly on public network interfaces"),
        Gate("trusted_https_reverse_proxy", trusted_https_proxy,
             "TLS termination must validate exact Host and scheme"),
        Gate("canonical_https_origin", pinned_https_origin,
             "A fixed HTTPS origin must match Google and Companion settings"),
        Gate("google_oauth_live", real_google_oauth_configured,
             "Real Google web OAuth setup and private allowlist must be verified"),
        Gate("private_companion_pairing", private_key_material,
             "Companion HMAC keys must be operator-paired outside the browser"),
        Gate("per_owner_worker", per_owner_workers,
             "Runtime must never share a mutable Engine process across owners"),
        Gate("shared_services_untouched", separate_existing_services,
             "Do not modify JM/Chema processes, services or ports"),
        Gate("operator_authorization", operator_approval,
             "User permission is required before staging or installing software"),
        Gate("collaborator_authorization", collaborator_approval,
             "Chema approval is required before modifying shared infrastructure"),
        Gate("immutable_engine_image", engine_image_pinned,
             "Owner worker must use a reviewed immutable Engine image pin"),
    )
    return Readiness(
        ready_for_private_beta=all(g.ok for g in results),
        gates=results,
    )


def inspect_host_readonly() -> dict:
    """Safe inventory to inform the gate, NOT automatic evidence of readiness.

    A Docker CLI alone does not prove sandboxing, stable TLS, Google OAuth,
    approved change scope or permission to deploy.
    """
    docker = shutil.which("docker")
    runtime = {name: bool(shutil.which(name))
               for name in ("docker", "podman", "lxc", "lxd")}
    daemon = False
    if docker:
        try:
            result = subprocess.run(
                [docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=4, check=False,
            )
            daemon = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            daemon = False
    return {
        "docker_cli": docker is not None,
        "docker_daemon_access": daemon,
        "available_runtimes": runtime,
        "loopback_only_not_confirmed": True,
        "operator_approval_not_inferred": True,
        "ready_for_private_beta": False,
    }


if __name__ == "__main__":
    print(json.dumps(inspect_host_readonly(), sort_keys=True))
