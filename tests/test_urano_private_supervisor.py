"""U13D: real subprocess supervision with synthetic Engine worker protocol.

No host services, real user data, network listeners, or deployment.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.private_worker_supervisor import PrivateWorkerSupervisor, WorkerFailure
from urano.runtime_activation import RuntimeActivationGuard, StaleActivation, RuntimeBusy

# A worker fixture with no Engine imports and a genuine child process.
WORKER = r"""
import json,os,sys,time
print(json.dumps({"type":"ready","worker_pid":os.getpid()}),flush=True)
for line in sys.stdin:
    request=json.loads(line)
    if request["op"]=="open":
        folder=request["folder"]
        if folder=="Hangs":time.sleep(10)
        elif folder=="Crashes":os._exit(5)
        elif folder=="Rejects":print(json.dumps({"ok":False}),flush=True)
        else:print(json.dumps({"ok":True,"type":"opened","folder":folder}),flush=True)
    elif request["op"]=="stop":
        print(json.dumps({"ok":True,"type":"stopped"}),flush=True)
        break
"""


class SupervisorContract(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "Projects").mkdir()
        self.root = root
        self.catalog = ProjectCatalog(root / "catalog.sqlite3")
        self.bindings = EngineProjectRegistry(root / "bindings.sqlite3", root, self.catalog)
        self.guard = RuntimeActivationGuard(root / "runtime.sqlite3", self.catalog, self.bindings)
        self.owner = "test:alice"
        self.other = "test:bob"
        self.runtime = self.guard.register_trusted(self.owner)
        self.other_runtime = self.guard.register_trusted(self.other)
        self.ids = {}
        for name in ("Old", "New", "Hangs", "Crashes", "Rejects"):
            folder = root / "Projects" / name
            folder.mkdir()
            (folder / "project.json").write_text(json.dumps({"name": name}))
            project = self.catalog.create(self.owner, name)
            self.bindings.bind_trusted(self.owner, project.id, name)
            self.ids[name] = project.id
        bob = self.catalog.create(self.other, "Bob")
        (root / "Projects" / "Bob").mkdir()
        (root / "Projects" / "Bob" / "project.json").write_text("{}")
        self.bindings.bind_trusted(self.other, bob.id, "Bob")
        self.bob_project = bob.id

    def supervisor(self, owner=None, runtime=None, *, timeout=1.0):
        return PrivateWorkerSupervisor(
            self.guard, owner or self.owner, runtime or self.runtime,
            self.root, self.root, startup_timeout=2, open_timeout=timeout,
            command=[sys.executable, "-u", "-c", WORKER]
        )

    def test_open_two_historical_projects_and_invalidate_on_exit(self):
        sup = self.supervisor()
        sup.start()
        try:
            old = sup.open_project(self.ids["Old"])
            self.assertEqual(old.project_path.name, "Old")
            self.assertEqual(self.guard.get_state(self.owner, self.runtime)[0], "ready")
            new = sup.open_project(self.ids["New"])
            self.assertGreater(new.generation, old.generation)
            self.assertEqual(self.guard.get_state(self.owner, self.runtime)[1], self.ids["New"])
        finally:
            sup.stop()
        self.assertEqual(self.guard.get_state(self.owner, self.runtime)[:2], ("idle", None))
        with self.assertRaises(RuntimeBusy):
            self.guard.begin_job(self.owner, self.runtime, self.ids["New"])

    def test_timeout_kills_worker_and_clears_pending_switch(self):
        sup = self.supervisor(timeout=0.15)
        sup.start()
        with self.assertRaises(WorkerFailure):
            sup.open_project(self.ids["Hangs"])
        self.assertIsNone(sup.process)
        self.assertEqual(self.guard.get_state(self.owner, self.runtime)[0], "idle")
        newer = self.supervisor()
        newer.start()
        newer.open_project(self.ids["Old"])
        newer.stop()

    def test_worker_crash_fails_closed_and_can_restart(self):
        sup = self.supervisor()
        sup.start()
        with self.assertRaises(WorkerFailure):
            sup.open_project(self.ids["Crashes"])
        self.assertEqual(self.guard.get_state(self.owner, self.runtime)[0], "idle")

    def test_negative_engine_ack_fails_closed(self):
        sup = self.supervisor()
        sup.start()
        with self.assertRaises(WorkerFailure):
            sup.open_project(self.ids["Rejects"])
        self.assertEqual(self.guard.get_state(self.owner, self.runtime)[0], "idle")

    def test_cross_owner_rejected_before_worker_command(self):
        sup = self.supervisor()
        sup.start()
        try:
            with self.assertRaises(ProjectNotFound):
                sup.open_project(self.bob_project)
            self.assertEqual(self.guard.get_state(self.owner, self.runtime)[0], "idle")
            with self.assertRaises(ProjectNotFound):
                self.supervisor(self.other, self.runtime).start()
        finally:
            sup.stop()

    def test_does_not_open_when_a_job_is_busy(self):
        sup = self.supervisor()
        sup.start()
        sup.open_project(self.ids["Old"])
        generation = self.guard.begin_job(self.owner, self.runtime, self.ids["Old"])
        with self.assertRaises(RuntimeBusy):
            sup.open_project(self.ids["New"])
        self.guard.finish_job(self.owner, self.runtime, self.ids["Old"], generation)
        sup.stop()
        self.assertEqual(self.guard.get_state(self.owner, self.runtime)[0], "idle")

    def test_runtime_generation_changes_after_shutdown(self):
        sup = self.supervisor()
        sup.start()
        ticket = sup.open_project(self.ids["Old"])
        sup.stop()
        with self.assertRaises(StaleActivation):
            self.guard.acknowledge_open(self.owner, ticket, success=True)
        fresh = self.supervisor()
        fresh.start()
        fresh.open_project(self.ids["New"])
        fresh.stop()


if __name__ == "__main__":
    unittest.main()
