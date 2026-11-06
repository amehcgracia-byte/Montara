"""U13B: two owners and competing switches/jobs in isolated fake workspaces."""
import json
import tempfile
import unittest
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.runtime_activation import RuntimeActivationGuard, RuntimeBusy, StaleActivation


class GuardContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "engine" / "Projects").mkdir(parents=True)
        self.catalog = ProjectCatalog(root / "catalog.sqlite3")
        self.bindings = EngineProjectRegistry(root / "bindings.sqlite3", root / "engine", self.catalog)
        self.guard = RuntimeActivationGuard(root / "runtime.sqlite3", self.catalog, self.bindings)
        self.alice = "fake:alice"
        self.bob = "fake:bob"
        self.ar = self.guard.register_trusted(self.alice)
        self.br = self.guard.register_trusted(self.bob)
        self.a1 = self.add_project(self.alice, "Alice-1")
        self.a2 = self.add_project(self.alice, "Alice-2")
        self.b1 = self.add_project(self.bob, "Bob-1")

    def add_project(self, owner, name):
        project = self.catalog.create(owner, name)
        folder = self.bindings.projects_dir / name
        folder.mkdir()
        (folder / "project.json").write_text(json.dumps({"name": name}))
        self.bindings.bind_trusted(owner, project.id, name)
        return project.id

    def test_correct_project_may_open_and_switch_after_acknowledgement(self):
        t1 = self.guard.request_open(self.alice, self.ar, self.a1)
        self.assertEqual(t1.project_path.name, "Alice-1")
        self.assertEqual(self.guard.get_state(self.alice, self.ar)[0], "switching")
        with self.assertRaises(RuntimeBusy):
            self.guard.request_open(self.alice, self.ar, self.a2)
        self.guard.acknowledge_open(self.alice, t1, success=True)
        self.assertEqual(self.guard.get_state(self.alice, self.ar)[:2], ("ready", self.a1))
        t2 = self.guard.request_open(self.alice, self.ar, self.a2)
        self.assertGreater(t2.generation, t1.generation)
        self.guard.acknowledge_open(self.alice, t2, success=True)
        self.assertEqual(self.guard.get_state(self.alice, self.ar)[:2], ("ready", self.a2))
        with self.assertRaises(StaleActivation):
            self.guard.acknowledge_open(self.alice, t1, success=True)

    def test_running_job_blocks_other_project_switch(self):
        ticket = self.guard.request_open(self.alice, self.ar, self.a1)
        self.guard.acknowledge_open(self.alice, ticket, success=True)
        generation = self.guard.begin_job(self.alice, self.ar, self.a1)
        with self.assertRaises(RuntimeBusy):
            self.guard.request_open(self.alice, self.ar, self.a2)
        with self.assertRaises(RuntimeBusy):
            self.guard.begin_job(self.alice, self.ar, self.a2)
        with self.assertRaises(StaleActivation):
            self.guard.finish_job(self.alice, self.ar, self.a1, generation + 1)
        self.guard.finish_job(self.alice, self.ar, self.a1, generation)
        self.guard.acknowledge_open(self.alice, self.guard.request_open(self.alice, self.ar, self.a2),
                                    success=True)

    def test_two_owners_cannot_share_slot_or_cross_open(self):
        self.assertNotEqual(self.ar, self.br)
        with self.assertRaises(ProjectNotFound):
            self.guard.request_open(self.bob, self.ar, self.b1)
        with self.assertRaises(ProjectNotFound):
            self.guard.request_open(self.alice, self.ar, self.b1)
        with self.assertRaises(ValueError):
            self.guard.register_trusted(self.bob, runtime_id=self.ar)
        with self.assertRaises(ValueError):
            self.guard.register_trusted(self.alice)
        alice_ticket = self.guard.request_open(self.alice, self.ar, self.a1)
        bob_ticket = self.guard.request_open(self.bob, self.br, self.b1)
        self.guard.acknowledge_open(self.alice, alice_ticket, success=True)
        self.guard.acknowledge_open(self.bob, bob_ticket, success=True)
        self.assertEqual(self.guard.get_state(self.bob, self.br)[1], self.b1)

    def test_failed_open_fails_closed_and_can_retry(self):
        ticket = self.guard.request_open(self.alice, self.ar, self.a1)
        self.guard.acknowledge_open(self.alice, ticket, success=False)
        self.assertEqual(self.guard.get_state(self.alice, self.ar)[:2], ("idle", None))
        with self.assertRaises(RuntimeBusy):
            self.guard.begin_job(self.alice, self.ar, self.a1)
        self.guard.acknowledge_open(self.alice, self.guard.request_open(self.alice, self.ar, self.a1),
                                    success=True)

    def test_persistent_state_and_concurrent_guard_instances(self):
        first = self.guard.request_open(self.alice, self.ar, self.a1)
        second_guard = RuntimeActivationGuard(self.guard.db_path, self.catalog, self.bindings)
        with self.assertRaises(RuntimeBusy):
            second_guard.request_open(self.alice, self.ar, self.a2)
        second_guard.acknowledge_open(self.alice, first, success=True)
        generation = second_guard.begin_job(self.alice, self.ar, self.a1)
        with self.assertRaises(RuntimeBusy):
            self.guard.request_open(self.alice, self.ar, self.a2)
        self.guard.finish_job(self.alice, self.ar, self.a1, generation)

    def test_cannot_claim_absent_project_or_missing_source(self):
        with self.assertRaises(ProjectNotFound):
            self.guard.request_open(self.alice, self.ar, self.b1)
        missing = self.bindings.projects_dir / "Alice-1" / "project.json"
        missing.unlink()
        with self.assertRaises(ValueError):
            self.guard.request_open(self.alice, self.ar, self.a1)
        self.assertEqual(self.guard.get_state(self.alice, self.ar)[0], "idle")


if __name__ == "__main__":
    unittest.main()
