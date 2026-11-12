"""Operator-only entrypoint for native Chema in an EXISTING systemd Owner unit.

This program replaces the old pilot worker script *only after* a root broker
has reserved (owner_id, workspace_id, generation), launched a DynamicUser unit
with the pinned read-only JM/Engine binds, and verified a 0700 StateDirectory.
It never creates/opens a synthetic Editor project. Browser and Owner HTTP
callers must never choose this script or its arguments.

The existing private Socket/Stage transport modules are deliberately reused
from the reviewed integration branch: no second web server or privileged
broker is introduced.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import sys
from pathlib import Path

_UNIT = re.compile(r"montara-i24-job-[a-f0-9]{32}\Z")
_WORKSPACE = re.compile(
    r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z")
_STATE_DIR = re.compile(r"montara-owner-[a-f0-9]{40}\Z")
_REQUIRED_SITE = (
    "numpy", "scipy", "numba", "librosa", "soundfile",
    "pyloudnorm", "matchering",
)


class NativeSystemdOwnerError(ValueError):
    """Operator or persistent runtime is not a verified Owner worker."""


def trusted_native_worker_args(argv: list[str], *,
                               state_directory: str,
                               runtime_root: Path,
                               runtime_base: Path = Path("/run")):
    """Strict existing systemd argv; never accept paths, IDs from HTTP."""
    if (len(argv) not in (6, 8) or
            argv[4:6] != ["--jm-bundle", "/opt/montara-jm"] or
            not _UNIT.fullmatch(argv[1]) or
            not _WORKSPACE.fullmatch(argv[2]) or
            not re.fullmatch(r"[1-9][0-9]*", argv[3]) or
            argv[0] != "/opt/montara-engine"):
        raise NativeSystemdOwnerError("Untrusted pinned worker invocation")
    limit = 256
    if len(argv) == 8:
        if (argv[6] != "--private-proxy-limit-mib" or
                not re.fullmatch(r"(?:[0-9]{3,4})", argv[7])):
            raise NativeSystemdOwnerError("Untrusted proxy quota")
        limit = int(argv[7])
        if not 256 <= limit <= 4096:
            raise NativeSystemdOwnerError("Untrusted proxy quota")
    unit, workspace, generation = argv[1], argv[2], int(argv[3])
    if (not isinstance(state_directory, str) or ":" in state_directory
            or not state_directory or not isinstance(runtime_root, Path)):
        raise NativeSystemdOwnerError("One private StateDirectory is required")
    state = Path(state_directory)
    if (state.is_symlink() or not state.is_dir() or
            not _STATE_DIR.fullmatch(state.name) or
            state.stat().st_mode & 0o077 or
            not state.is_absolute()):
        raise NativeSystemdOwnerError("Unverified persistent Owner state")
    runtime = Path(runtime_root)
    if (runtime.is_symlink() or not runtime.is_dir() or
            runtime.stat().st_mode & 0o077 or
            runtime != runtime_base / unit):
        raise NativeSystemdOwnerError("Unverified systemd runtime")
    return state.resolve(strict=True), runtime.resolve(strict=True), workspace, generation, limit


def vendor_site_for_native_worker(engine_root: Path) -> str:
    """Exact immutable wheel site used by Chema's Python child processes."""
    site = (Path(engine_root) / "site").resolve(strict=True)
    if not site.is_dir() or not all(
        (site / name).is_dir() or (site / (name + ".py")).is_file()
        for name in _REQUIRED_SITE
    ):
        raise NativeSystemdOwnerError("Pinned JM mixer dependencies unavailable")
    return str(site)


def prepare_native_owner_runtime(*, engine_root: Path, jm_root: Path,
                                 proxy_limit_mib: int) -> None:
    """Preserve current production JM pins, mixer path and proxy quota rules."""
    engine = Path(engine_root).resolve(strict=True)
    jm = Path(jm_root).resolve(strict=True)
    if (jm.is_symlink() or not (jm / "app.py").is_file()
            or (jm / "engine").resolve(strict=True)
                != (engine / "engine").resolve(strict=True)
            or not 256 <= proxy_limit_mib <= 4096):
        raise NativeSystemdOwnerError("Untrusted JM/Engine bundle relationship")

    from urano.jm_private_proxy_overlay import private_proxy_limit_mib
    private_proxy_limit_mib(proxy_limit_mib)
    if proxy_limit_mib > 256:
        source = (jm / "resumable_upload.py").read_text(encoding="utf-8")
        if ("max_original_file_bytes=limit" not in source or
                "MONTARA_PRIVATE_PROXY_LIMIT_MIB" not in source):
            raise NativeSystemdOwnerError("Reviewed private proxy quota missing")
        os.environ["MONTARA_PRIVATE_PROXY_LIMIT_MIB"] = str(proxy_limit_mib)
    else:
        os.environ.pop("MONTARA_PRIVATE_PROXY_LIMIT_MIB", None)

    pinned_site = vendor_site_for_native_worker(engine)
    # Same import precedence as the existing production worker: original JM
    # modules first, then pinned vendor packages and the exact Engine bundle.
    sys.path[:0] = [
        str(jm), pinned_site, str(engine / "app"), str(engine / "engine"),
    ]
    os.environ["PYTHONPATH"] = pinned_site
    os.environ["MONTARA_SESSION_TOKEN"] = secrets.token_hex(32)


def main(argv: list[str] | None = None):
    # This entrypoint is a replacement script selected solely by the operator
    # in the existing root broker's fixed systemd launch, not a public flag.
    args = sys.argv[1:] if argv is None else argv
    if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
        raise NativeSystemdOwnerError("Expected trusted systemd argv")
    # Never create data directories until the required cgroup/StateDirectory
    # arguments have been validated; preserve current persistent originals.
    if len(args) < 2 or not _UNIT.fullmatch(args[1]):
        raise NativeSystemdOwnerError("Unverified Owner unit")
    state, runtime, workspace, generation, quota = trusted_native_worker_args(
        args, state_directory=os.environ.get("STATE_DIRECTORY", ""),
        runtime_root=Path("/run") / args[1])
    bundle = Path("/opt/montara-engine")
    jm = Path("/opt/montara-jm")
    prepare_native_owner_runtime(
        engine_root=bundle, jm_root=jm, proxy_limit_mib=quota)

    # The actual image already supplies the reviewed private Unix transport
    # modules and pins their code behind the root broker. Use those unchanged.
    from app import create_montara_app
    from urano.private_jm_wsgi_socket import create_private_jm_wsgi_server
    from urano.private_stage_unix_transport import serve_stage_socket
    from urano.native_owner_worker_service import serve_native_owner_workspace

    def ready():
        marker = runtime / "ready.json"
        if marker.is_symlink() or marker.exists():
            raise NativeSystemdOwnerError("Stale ready marker")
        tmp = runtime / "ready.tmp"
        if tmp.is_symlink() or tmp.exists():
            raise NativeSystemdOwnerError("Stale ready staging file")
        # The broker relies on the existing {ready,uid,folder} schema.
        tmp.write_text(json.dumps({
            "ready": True, "uid": os.getuid(), "folder": workspace}))
        tmp.replace(marker)

    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    serve_native_owner_workspace(
        app_factory=create_montara_app, data_root=state,
        runtime_root=runtime, workspace_id=workspace,
        generation=generation, on_ready=ready,
        make_private_server=create_private_jm_wsgi_server,
        serve_stage_socket=serve_stage_socket,
    )


if __name__ == "__main__":
    main()
