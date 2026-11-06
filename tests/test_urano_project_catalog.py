"""P0 catalog contract: two mock principals; no live authentication or VM."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from urano.project_catalog import ProjectCatalog, ProjectConflict, ProjectNotFound


class ProjectCatalogContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "catalog.sqlite3"
        self.catalog = ProjectCatalog(self.path)

    def test_two_users_are_isolated_in_list_get_and_save(self):
        alice = self.catalog.create("test:alice", "Stage — ensayo")
        bob = self.catalog.create("test:bob", "Show")
        self.assertEqual([p.id for p in self.catalog.list_for("test:alice")], [alice.id])
        self.assertEqual([p.id for p in self.catalog.list_for("test:bob")], [bob.id])
        for user, foreign in (("test:alice", bob.id), ("test:bob", alice.id)):
            with self.assertRaises(ProjectNotFound):
                self.catalog.get(user, foreign)
            with self.assertRaises(ProjectNotFound):
                self.catalog.save_recipe(user, foreign, {"cuts": []}, expected_revision=0)
        self.assertEqual(self.catalog.get("test:alice", alice.id).revision, 0)
        self.assertEqual(self.catalog.get("test:bob", bob.id).revision, 0)

    def test_recipe_survives_catalog_reopen_and_keeps_owner(self):
        project = self.catalog.create("test:alice", "Mi vídeo")
        saved = self.catalog.save_recipe("test:alice", project.id,
                    {"mode": "stage", "edits": [{"start": 3.4}]}, expected_revision=0)
        self.assertEqual(saved.revision, 1)
        reopened = ProjectCatalog(self.path)
        self.assertEqual(reopened.get("test:alice", project.id).recipe,
                         {"mode": "stage", "edits": [{"start": 3.4}]})
        with self.assertRaises(ProjectNotFound):
            reopened.get("test:bob", project.id)

    def test_stale_writer_does_not_overwrite_saved_recipe(self):
        p = self.catalog.create("test:alice", "A")
        self.catalog.save_recipe("test:alice", p.id, {"x": 1}, expected_revision=0)
        with self.assertRaises(ProjectConflict):
            self.catalog.save_recipe("test:alice", p.id, {"x": 2}, expected_revision=0)
        self.assertEqual(self.catalog.get("test:alice", p.id).recipe, {"x": 1})

    def test_invalid_identifiers_titles_and_recipe_fail_closed(self):
        with self.assertRaises(ValueError):
            self.catalog.create("../../someone", "bad")
        with self.assertRaises(ValueError):
            self.catalog.create("test:alice", "   ")
        p = self.catalog.create("test:alice", "OK")
        with self.assertRaises(ValueError):
            self.catalog.get("test:alice", "../data")
        for bad in ({"bad": float("nan")}, {"bad": b"binary"}, {"large": "z" * 260_000}):
            with self.assertRaises(ValueError):
                self.catalog.save_recipe("test:alice", p.id, bad, expected_revision=0)
        self.assertEqual(self.catalog.get("test:alice", p.id).revision, 0)

    def test_failed_foreign_update_never_creates_a_project(self):
        self.catalog.create("test:alice", "A")
        foreign = self.catalog.create("test:bob", "B")
        with self.assertRaises(ProjectNotFound):
            self.catalog.save_recipe("test:alice", foreign.id, {}, expected_revision=0)
        self.assertEqual(len(self.catalog.list_for("test:alice")), 1)
        self.assertEqual(len(self.catalog.list_for("test:bob")), 1)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM urano_projects").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
