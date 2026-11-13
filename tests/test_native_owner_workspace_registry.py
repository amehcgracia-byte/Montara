"""No implicit project replacement: stable Owner workspace lifecycle tests."""
from __future__ import annotations

import concurrent.futures
import sqlite3
import tempfile
import unittest
from pathlib import Path

from urano.native_owner_workspace_registry import (
    ExistingOwnerProjects, NativeOwnerWorkspaceRegistry,
    WorkspaceAlreadyBound,
)
from urano.project_catalog import ProjectCatalog, ProjectNotFound


class NativeOwnerWorkspaceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="montara-native-registry-")
        self.addCleanup(self.temp.cleanup)
        self.catalog = ProjectCatalog(Path(self.temp.name) / "owner.sqlite3")
        self.registry = NativeOwnerWorkspaceRegistry(self.catalog)

    def test_one_stable_workspace_per_owner_and_no_picker(self):
        a = self.registry.reserve_new("user-a")
        b = self.registry.reserve_new("user-b")
        self.assertNotEqual(a.workspace_id,b.workspace_id)
        self.assertEqual(a,self.registry.reserve_new("user-a"))
        self.assertEqual(a,self.registry.get("user-a"))
        self.assertIsNone(self.registry.get("user-c"))
        self.assertEqual(self.catalog.get("user-a",a.workspace_id).id,a.workspace_id)
        with self.assertRaises(ProjectNotFound):
            self.catalog.get("user-b",a.workspace_id)

    def test_existing_legacy_owner_not_auto_switched_or_hidden(self):
        old1 = self.catalog.create("user-a","Video Stage")
        old2 = self.catalog.create("user-a","Musical session")
        original = [p.id for p in self.catalog.list_for("user-a")]
        with self.assertRaises(ExistingOwnerProjects):
            self.registry.reserve_new("user-a")
        self.assertIsNone(self.registry.get("user-a"))
        self.assertEqual([p.id for p in self.catalog.list_for("user-a")],
                         original)
        # Following the independent broker/data-root check, orchestration
        # may explicitly choose the original Owner workspace UUID.
        chosen = self.registry.bind_existing("user-a",old1.id)
        self.assertEqual(chosen.workspace_id,old1.id)
        self.assertEqual(self.registry.reserve_new("user-a"),chosen)
        self.assertEqual(len(self.catalog.list_for("user-a")),2)
        with self.assertRaises(WorkspaceAlreadyBound):
            self.registry.bind_existing("user-a",old2.id)

    def test_cross_owner_legacy_binding_denied(self):
        owned = self.catalog.create("user-a","Owner A")
        with self.assertRaises(ProjectNotFound):
            self.registry.bind_existing("user-b",owned.id)
        self.assertIsNone(self.registry.get("user-b"))
        self.assertEqual(self.catalog.get("user-a",owned.id).title,"Owner A")

    def test_corrupt_and_noncanonical_project_ids_fail_closed(self):
        self.catalog.create("user-a","Existing")
        for value in ("../escape","invalid","A"*36):
            with self.subTest(id=value):
                with self.assertRaises(ValueError):
                    self.registry.bind_existing("user-a",value)

    def test_legacy_binding_is_idempotent_not_destructive(self):
        first=self.catalog.create("user-a","First")
        fixed=self.registry.bind_existing("user-a",first.id)
        self.assertEqual(fixed,self.registry.bind_existing("user-a",first.id))
        self.assertEqual(first.id,self.registry.get("user-a").workspace_id)

    def test_two_simultaneous_logins_do_not_create_two_workspaces(self):
        def enroll(_):
            return self.registry.reserve_new("concurrent-user").workspace_id
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(enroll,range(24)))
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(len(self.catalog.list_for("concurrent-user")),1)
        with sqlite3.connect(self.catalog.db_path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM urano_native_owner_workspace "
                "WHERE owner_id=?",("concurrent-user",)).fetchone()[0],1)

    def test_legacy_and_new_users_keep_separate_workspaces(self):
        old=self.catalog.create("legacy-user","Existing Chema draft")
        with self.assertRaises(ExistingOwnerProjects):
            self.registry.reserve_new("legacy-user")
        new=self.registry.reserve_new("new-user")
        self.assertEqual(self.registry.bind_existing(
            "legacy-user",old.id).workspace_id,old.id)
        self.assertNotEqual(old.id,new.workspace_id)


if __name__=="__main__":
    unittest.main()
