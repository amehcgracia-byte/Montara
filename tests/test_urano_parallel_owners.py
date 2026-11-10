"""U13D2A: verify parallel owners do NOT accidentally share a global render queue.

Tests use two real child processes and synthetic projects. These tests do NOT
prove OS/user isolation or real video render throughput.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.private_worker_supervisor import PrivateWorkerSupervisor
from urano.project_catalog import ProjectCatalog
from urano.runtime_activation import RuntimeActivationGuard, RuntimeBusy


SYNC_WORKER = r"""
import json,os,sys,time
from pathlib import Path
name=sys.argv[1]
marker_dir=Path(sys.argv[2])
print(json.dumps({"type":"ready","worker_pid":os.getpid()}),flush=True)
for line in sys.stdin:
    command=json.loads(line)
    if command.get("op")=="open":
        (marker_dir / (name + ".entered")).write_text("entered")
        other="bob" if name=="alice" else "alice"
        deadline=time.monotonic()+5
        while not (marker_dir / (other + ".entered")).exists():
            if time.monotonic()>deadline:
                print(json.dumps({"ok":False,"error":"parallel-overlap-not-observed"}),flush=True)
                break
            time.sleep(0.01)
        else:
            print(json.dumps({"ok":True,"type":"opened","folder":command["folder"]}),flush=True)
    elif command.get("op")=="stop":
        break
"""


class ConcurrentRuntimeContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        (self.base / "Projects").mkdir()
        self.catalog = ProjectCatalog(self.base / "catalog.sqlite3")
        self.bindings = EngineProjectRegistry(self.base / "bindings.sqlite3", self.base, self.catalog)
        self.guard = RuntimeActivationGuard(self.base / "runtime.sqlite3", self.catalog, self.bindings)
        self.users = {}
        for name in ("alice", "bob"):
            owner = f"fake:{name}"
            project = self.catalog.create(owner, f"Project-{name}")
            folder = self.base / "Projects" / f"Project-{name}"
            folder.mkdir()
            (folder / "project.json").write_text(json.dumps({"name": name}))
            self.bindings.bind_trusted(owner, project.id, folder.name)
            self.users[name] = (owner, self.guard.register_trusted(owner), project.id)

    def supervisor(self, name):
        owner, runtime, _ = self.users[name]
        return PrivateWorkerSupervisor(
            self.guard, owner, runtime, self.base, self.base,
            startup_timeout=5, open_timeout=8,
            command=[sys.executable, "-u", "-c", SYNC_WORKER, name, str(self.base)]
        )

    def test_two_different_owners_open_concurrently_without_global_queue(self):
        supervisors = {name: self.supervisor(name) for name in ("alice", "bob")}
        for supervisor in supervisors.values():
            supervisor.start()
        try:
            def open_one(name):
                owner, runtime, project_id = self.users[name]
                ticket = supervisors[name].open_project(project_id)
                return (ticket.runtime_id, self.guard.get_state(owner, runtime))
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(open_one, "alice")
                b = pool.submit(open_one, "bob")
                a_result, b_result = a.result(timeout=12), b.result(timeout=12)
            self.assertNotEqual(a_result[0], b_result[0])
            self.assertEqual(a_result[1][0], "ready")
            self.assertEqual(b_result[1][0], "ready")
            self.assertTrue((self.base / "alice.entered").exists())
            self.assertTrue((self.base / "bob.entered").exists())
        finally:
            for supervisor in supervisors.values():
                supervisor.stop()

    def test_own_busy_job_does_not_prevent_other_user_from_opening(self):
        # U13B's busy guard is PER OWNER; no global mutex.
        a_owner, a_runtime, a_project = self.users["alice"]
        b_owner, b_runtime, b_project = self.users["bob"]
        a_ticket = self.guard.request_open(a_owner, a_runtime, a_project)
        self.guard.acknowledge_open(a_owner, a_ticket, success=True)
        gen = self.guard.begin_job(a_owner, a_runtime, a_project)
        with self.assertRaises(RuntimeBusy):
            self.guard.request_open(a_owner, a_runtime, a_project)
        b_ticket = self.guard.request_open(b_owner, b_runtime, b_project)
        self.guard.acknowledge_open(b_owner, b_ticket, success=True)
        self.assertEqual(self.guard.get_state(a_owner, a_runtime)[0], "busy")
        self.assertEqual(self.guard.get_state(b_owner, b_runtime)[0], "ready")
        self.guard.finish_job(a_owner, a_runtime, a_project, gen)


if __name__ == "__main__":
    unittest.main()
