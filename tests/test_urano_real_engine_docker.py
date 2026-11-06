"""U13D2D: actual pinned Montara Engine inside separately mounted Docker workers.

Run only in a disposable GitHub-hosted runner with the existing Montara image
built from this branch. All projects are synthetic and contain NO media.
This measures correct opening/isolation, NOT video throughput or Companion.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from urano.container_worker_bridge import ContainerWorkerBridge
from urano.engine_bindings import EngineProjectRegistry
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.runtime_activation import RuntimeActivationGuard

IMAGE_ENV = "URANO_TEST_IMAGE_ID"
ENGINE_COMMAND = [
    "python", "-u", "-m", "urano.engine_worker_process",
    "--engine-dir", "/app/engine", "--data-root", "/workspace"
]


def _run(argv, *, timeout=150):
    result = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise AssertionError("Disposable Docker setup failed: " +
                             result.stderr[-1500:] + result.stdout[-500:])
    return result.stdout


def _make_project(image: str, workspace: Path, name: str) -> None:
    # Generate project.json using the *actual pinned* Engine schema; no
    # replacement/stub JSON that could hide a compatibility regression.
    generator = (
        "import json; from pathlib import Path; "
        "from core.project import new_project_document; "
        "p=Path('/workspace/Projects')/ " + repr(name) + "; "
        "p.mkdir(exist_ok=True); "
        "(p/'project.json').write_text("
        "json.dumps(new_project_document(" + repr(name) + ")))"
    )
    _run(["docker", "run", "--rm", "--network", "none",
          "--user", "10001:10001",
          "--mount", f"type=bind,src={workspace},dst=/workspace",
          "--workdir", "/app/engine",
          "--env", "HOME=/workspace",
          image, "python", "-c", generator])


@unittest.skipUnless(os.name == "posix" and os.environ.get(IMAGE_ENV) and os.environ.get("GITHUB_ACTIONS") == "true",
                     "Opt-in Docker real Engine integration only")
class RealEngineDockerBridge(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="urano-u13d2d-")
        self.root = Path(self.temp.name)
        self.addCleanup(self._cleanup)
        self.image = os.environ[IMAGE_ENV]
        self.catalog = ProjectCatalog(self.root / "catalog.sqlite3")
        self.guard = None
        self.owners = {}
        # CI-only synthetic files: allow non-root container ID to write. This
        # mode is NOT acceptable for actual user media or production volumes.
        for owner, names in (("alice", ("Earlier", "Recent")),
                             ("bob", ("BobProject",))):
            workspace = self.root / owner
            workspace.mkdir(mode=0o777)
            workspace.chmod(0o777)
            (workspace / "Projects").mkdir(mode=0o777)
            (workspace / "Projects").chmod(0o777)
            self.owners[owner] = {"workspace": workspace, "ids": {}}
            for name in names:
                _make_project(self.image, workspace, name)
        self.bindings = {}
        for owner, info in self.owners.items():
            binding = EngineProjectRegistry(
                self.root / f"bindings-{owner}.sqlite3",
                info["workspace"], self.catalog
            )
            self.bindings[owner] = binding
            for name in ("Earlier", "Recent") if owner == "alice" else ("BobProject",):
                project = self.catalog.create(f"fixture:{owner}", name)
                binding.bind_trusted(f"fixture:{owner}", project.id, name)
                info["ids"][name] = project.id
        # One guard/catalog shared only by trusted orchestrator, but each
        # binding resolves exclusively into its owner's own workspace.
        # A multi-workspace adapter is not yet implemented: use one guard per
        # owner for this isolated Engine test and test auth separately.
        for owner, info in self.owners.items():
            guard = RuntimeActivationGuard(
                self.root / f"guard-{owner}.sqlite3",
                self.catalog, self.bindings[owner]
            )
            info["guard"] = guard
            info["runtime"] = guard.register_trusted(f"fixture:{owner}")

    def _cleanup(self):
        # On disposable GitHub runners only: project folders are written by
        # container UID 10001, not the runner user. Reclaim ownership before
        # TemporaryDirectory removes the synthetic data. Never do this on a
        # real host or user media workspace.
        reclaim = subprocess.run(
            ["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(self.root)],
            capture_output=True, text=True, timeout=20)
        if reclaim.returncode:
            raise AssertionError("Could not reclaim CI-only synthetic files")
        self.temp.cleanup()

    def bridge(self, owner):
        info = self.owners[owner]
        return ContainerWorkerBridge(
            guard=info["guard"], owner_id=f"fixture:{owner}",
            runtime_id=info["runtime"], workspace=info["workspace"],
            image=self.image, name=f"urano-real-{owner}-worker",
            worker_command=ENGINE_COMMAND, startup_timeout=110, open_timeout=100,
            cpus=1.0, memory_mb=1536
        )

    def test_real_engine_opens_historical_project_and_other_owner_concurrently(self):
        alice, bob = self.bridge("alice"), self.bridge("bob")
        try:
            # True concurrency: no global render queue. These operations open
            # projects only, not video renders or editor sessions.
            with ThreadPoolExecutor(max_workers=2) as pool:
                fa = pool.submit(alice.start)
                fb = pool.submit(bob.start)
                fa.result(timeout=120)
                fb.result(timeout=120)
                a_old = pool.submit(alice.open_project, self.owners["alice"]["ids"]["Earlier"])
                b_project = pool.submit(bob.open_project, self.owners["bob"]["ids"]["BobProject"])
                a_ticket = a_old.result(timeout=115)
                b_ticket = b_project.result(timeout=115)
            self.assertEqual(a_ticket.project_path.name, "Earlier")
            self.assertEqual(b_ticket.project_path.name, "BobProject")
            self.assertNotEqual(alice.cid, bob.cid)
            newer = alice.open_project(self.owners["alice"]["ids"]["Recent"])
            self.assertGreater(newer.generation, a_ticket.generation)
            self.assertEqual(
                self.owners["alice"]["guard"].get_state(
                    "fixture:alice", self.owners["alice"]["runtime"])[:2],
                ("ready", newer.project_id))
            self.assertEqual(
                self.owners["bob"]["guard"].get_state(
                    "fixture:bob", self.owners["bob"]["runtime"])[0], "ready")
            # Synthetic files for Bob cannot be seen in Alice's workspace.
            self.assertFalse(
                (self.owners["alice"]["workspace"] /
                 "Projects" / "BobProject").exists())
        finally:
            alice.stop()
            bob.stop()
        for owner, info in self.owners.items():
            self.assertEqual(
                info["guard"].get_state(f"fixture:{owner}", info["runtime"])[:2],
                ("idle", None))

    def test_unauthorized_foreign_id_rejected(self):
        alice = self.bridge("alice")
        alice.start()
        try:
            with self.assertRaises(ProjectNotFound):
                alice.open_project(self.owners["bob"]["ids"]["BobProject"])
        finally:
            alice.stop()


if __name__ == "__main__":
    unittest.main()
