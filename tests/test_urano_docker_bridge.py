"""U13D2C Docker integration: actual container via stdio, owner state fence.

Only disposable synthetic project data. Does not load the Montara Engine yet.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from urano.container_worker_bridge import ContainerWorkerBridge, WorkerFailure
from urano.engine_bindings import EngineProjectRegistry
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.runtime_activation import RuntimeActivationGuard, RuntimeBusy


WORKER = r"""
import json, os, sys
from pathlib import Path
print(json.dumps({"type":"ready","worker_pid":os.getpid()}),flush=True)
for raw in sys.stdin:
    request=json.loads(raw)
    if request.get("op")=="open":
        name=request["folder"]
        local=Path("/workspace/Projects")/name/"project.json"
        if not local.is_file():
            print(json.dumps({"ok":False}),flush=True)
            continue
        print(json.dumps({"ok":True,"type":"opened","folder":name}),flush=True)
"""


@unittest.skipUnless(os.name == "posix" and os.environ.get("URANO_TEST_IMAGE_DIGEST"),
                     "Docker smoke only in CI opt-in")
class DockerContainerBridgeSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="urano-bridge-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.owner_root = self.root / "alice"
        self.owner_root.mkdir()
        (self.owner_root / "Projects").mkdir()
        self.catalog = ProjectCatalog(self.root / "catalog.sqlite3")
        self.bindings = EngineProjectRegistry(
            self.root / "bindings.sqlite3", self.owner_root, self.catalog)
        self.guard = RuntimeActivationGuard(
            self.root / "runtime.sqlite3", self.catalog, self.bindings)
        self.owner, self.other = "fake:alice", "fake:bob"
        self.runtime = self.guard.register_trusted(self.owner)
        self.projects = {}
        for name in ("Earlier", "Recent"):
            item = self.catalog.create(self.owner, name)
            folder = self.owner_root / "Projects" / name
            folder.mkdir()
            (folder / "project.json").write_text(json.dumps({"name": name}))
            self.bindings.bind_trusted(self.owner, item.id, name)
            self.projects[name] = item.id

    def bridge(self):
        return ContainerWorkerBridge(
            guard=self.guard, owner_id=self.owner, runtime_id=self.runtime,
            workspace=self.owner_root,
            image=os.environ["URANO_TEST_IMAGE_DIGEST"], name="urano-ci-bridge-alice",
            worker_command=["python", "-u", "-c", WORKER],
            startup_timeout=10, open_timeout=5, memory_mb=256, cpus=0.5)

    def test_real_container_opens_old_and_new_then_invalidates(self):
        bridge = self.bridge()
        bridge.start()
        try:
            self.assertTrue(bridge.cid)
            old = bridge.open_project(self.projects["Earlier"])
            recent = bridge.open_project(self.projects["Recent"])
            self.assertGreater(recent.generation, old.generation)
            self.assertEqual(self.guard.get_state(self.owner, self.runtime)[:2],
                             ("ready", self.projects["Recent"]))
        finally:
            bridge.stop()
        self.assertEqual(self.guard.get_state(self.owner, self.runtime)[:2], ("idle", None))
        self.assertIsNone(bridge.process)

    def test_foreign_owner_fails_before_worker_receives_project(self):
        foreign = self.catalog.create(self.other, "Other")
        bridge = self.bridge()
        bridge.start()
        try:
            with self.assertRaises(ProjectNotFound):
                bridge.open_project(foreign.id)
            self.assertEqual(self.guard.get_state(self.owner, self.runtime)[0], "idle")
        finally:
            bridge.stop()

    def test_busy_same_owner_does_not_switch(self):
        bridge = self.bridge()
        bridge.start()
        try:
            bridge.open_project(self.projects["Earlier"])
            gen = self.guard.begin_job(self.owner, self.runtime, self.projects["Earlier"])
            with self.assertRaises(RuntimeBusy):
                bridge.open_project(self.projects["Recent"])
            self.guard.finish_job(self.owner, self.runtime, self.projects["Earlier"], gen)
        finally:
            bridge.stop()


if __name__ == "__main__":
    unittest.main()
