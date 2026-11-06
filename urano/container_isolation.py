"""U13D2B: secure-default container launch contract for untrusted worker tests.

Intentionally separate from the Engine supervisor: no automatic production
integration, no docker socket mounted, no network, no shared home/data roots.
A privileged trusted orchestrator must supply a unique private workspace.
"""
from __future__ import annotations

import re
from pathlib import Path

_IMAGE_DIGEST = re.compile(r"^(?:[a-zA-Z0-9][a-zA-Z0-9._/-]*@)?sha256:[0-9a-f]{64}$")
_CONTAINER_NAME = re.compile(r"^urano-[a-z0-9-]{5,60}$")


def isolated_container_command(*, image: str, name: str, workspace: Path,
                               command: list[str], memory_mb: int = 512,
                               cpus: float = 1.0, uid: int = 10001) -> list[str]:
    """Create docker argv for one worker; no shell or untrusted runtime flags.

    The owner controls neither the mount nor the command. The caller provisions
    a separate private workspace and verifies its ownership before invocation.
    Requiring an image SHA256 digest prevents silent image tag drift.
    """
    if not isinstance(image, str) or not _IMAGE_DIGEST.fullmatch(image):
        raise ValueError("Container image must have immutable sha256 digest or local image ID")
    if not isinstance(name, str) or not _CONTAINER_NAME.fullmatch(name):
        raise ValueError("Invalid container name")
    root = Path(workspace)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("A real absolute per-user workspace is required")
    if not (root / "Projects").is_dir() or (root / "Projects").is_symlink():
        raise ValueError("Missing private projects directory")
    if type(memory_mb) is not int or not 128 <= memory_mb <= 16384:
        raise ValueError("Out-of-range memory budget")
    if type(cpus) not in (int, float) or not .25 <= cpus <= 8:
        raise ValueError("Out-of-range CPU budget")
    if type(uid) is not int or not 10000 <= uid <= 60000:
        raise ValueError("Dedicated unprivileged UID required")
    if (not isinstance(command, list) or not command or
        not all(isinstance(arg, str) and arg and "\x00" not in arg
                for arg in command)):
        raise ValueError("Explicit argument-vector command required")
    path = root.resolve(strict=True)
    return [
        "docker", "run", "--rm", "--name", name,
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--pids-limit", "64",
        "--memory", f"{memory_mb}m",
        "--cpus", str(cpus),
        "--user", f"{uid}:{uid}",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=32m,mode=1777",
        "--mount", f"type=bind,src={path},dst=/workspace",
        "--workdir", "/workspace",
        "--env", "HOME=/workspace",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "PYTHONPATH=/app",
        image, *command,
    ]
