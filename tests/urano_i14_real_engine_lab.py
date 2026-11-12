"""Opt-in I14 local real Engine probe with synthetic data, NO production isolation.

No privileged operations, no network endpoints, no real owner DB, no video
or persistent runtime resources. The caller must provide an Engine checkout
that matches this repo's submodule pin. A real isolated executor is still
REQUIRED before exposing I13 to HTTP.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.private_worker_supervisor import PrivateWorkerSupervisor
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.runtime_activation import RuntimeActivationGuard


def _git_sha(*argv: str, directory: Path) -> str:
    return subprocess.check_output(["git", "-C", str(directory), *argv],
                                   stderr=subprocess.DEVNULL, text=True, timeout=8).strip()


def checked_engine(repo_root: Path, engine_dir: Path) -> str:
    expected = _git_sha("rev-parse", "HEAD:engine", directory=repo_root)
    actual = _git_sha("rev-parse", "HEAD", directory=engine_dir)
    if expected != actual:
        raise ValueError("Engine checkout differs from pinned Montara submodule")
    if not (engine_dir / "server" / "api.py").is_file():
        raise ValueError("Engine API is not available")
    return actual


def _current_rss_kib(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (FileNotFoundError, PermissionError):
        return 0
    return 0


def probe(engine_dir: Path, *, repo_root: Path, startup_timeout: int = 90,
          open_timeout: int = 90) -> dict:
    engine_sha = checked_engine(repo_root, engine_dir)
    begin = time.monotonic()
    # TemporaryDirectory cleans only this tool's own fixture; never point it
    # at the long-lived C8 private owner root or a user's Engine workspace.
    with tempfile.TemporaryDirectory(prefix="montara-i14-engine-real-") as tmp:
        base = Path(tmp)
        data = base / "workspace"
        (data / "Projects").mkdir(parents=True, mode=0o700)
        engine_sys_path = str(engine_dir)
        sys.path.insert(0, engine_sys_path)
        try:
            from core.project import new_project_document
            project_folder = data / "Projects" / "I14-Synthetic"
            project_folder.mkdir(mode=0o700)
            (project_folder / "project.json").write_text(
                json.dumps(new_project_document("I14-Synthetic")), encoding="utf-8")
        finally:
            sys.path.remove(engine_sys_path)
        catalog = ProjectCatalog(base / "catalog.sqlite3")
        bindings = EngineProjectRegistry(base / "bindings.sqlite3", data, catalog)
        guard = RuntimeActivationGuard(base / "runtime.sqlite3", catalog, bindings)
        owner = "i14:synthetic-" + str(uuid.uuid4())
        other = "i14:foreign-" + str(uuid.uuid4())
        first = catalog.create(owner, "I14 Synthetic Project")
        foreign = catalog.create(other, "Not yours")
        bindings.bind_trusted(owner, first.id, "I14-Synthetic")
        runtime = guard.register_trusted(owner)
        supervisor = PrivateWorkerSupervisor(
            guard, owner, runtime, engine_dir, data,
            startup_timeout=startup_timeout, open_timeout=open_timeout)
        started_at = None
        open_at = None
        rss = None
        result = {}
        try:
            supervisor.start()
            started_at = time.monotonic()
            assert supervisor.process is not None
            rss = _current_rss_kib(supervisor.process.pid)
            try:
                supervisor.open_project(foreign.id)
            except ProjectNotFound:
                pass
            else:
                raise AssertionError("Foreign project opened")
            ticket = supervisor.open_project(first.id)
            open_at = time.monotonic()
            assert ticket.project_id == first.id
            assert guard.get_state(owner, runtime)[:2] == ("ready", first.id)
            rss = max(rss, _current_rss_kib(supervisor.process.pid))
            result = {"real_engine_open": True,
                      "cross_owner_denied": True,
                      "runtime_state_during_open": "ready",
                      # This is the two point-in-time samples of the parent
                      # worker PID, not peak cgroup memory or descendants.
                      "worker_sampled_rss_mib": round(rss / 1024, 2),
                      "startup_seconds": round(started_at - begin, 3),
                      "open_seconds": round(open_at - started_at, 3),
                      "pinned_engine_sha": engine_sha,
                      "project_schema_real": True,
                      "isolation_verified": False,
                      "companion_tested": False,
                      "video_render_tested": False,
                      "private_demo_data_only": True}
        finally:
            supervisor.stop()
        result["worker_stopped_and_runtime_idle"] = (supervisor.process is None and
                       guard.get_state(owner, runtime)[:2] == ("idle", None))
        if not result["worker_stopped_and_runtime_idle"]:
            raise AssertionError("Worker failed to exit or runtime remained active")
        result["elapsed_seconds"] = round(time.monotonic() - begin, 3)
        return result


def main():
    parser = argparse.ArgumentParser(description="Local I14 synthetic Engine opening probe")
    parser.add_argument("--engine-dir", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    result=probe(args.engine_dir.resolve(strict=True),repo_root=args.repo_root.resolve(strict=True))
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__ == "__main__":
    main()
