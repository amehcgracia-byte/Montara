"""U13: ownership and path invariants before any real Engine activation."""
import json
import tempfile
import unittest
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.project_catalog import ProjectCatalog, ProjectNotFound


class EngineBindingContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.engine_data = self.root / "engine-data"
        (self.engine_data / "Projects").mkdir(parents=True)
        self.catalog = ProjectCatalog(self.root / "catalog.sqlite3")
        self.registry = EngineProjectRegistry(self.root / "links.sqlite3", self.engine_data, self.catalog)
        self.alice = self.catalog.create("test:alice", "Stage")
        self.bob = self.catalog.create("test:bob", "Show")

    def folder(self, name):
        path = self.engine_data / "Projects" / name
        path.mkdir(parents=True)
        (path / "project.json").write_text(json.dumps({"name": name}))
        return path

    def test_trusted_binding_can_resolve_only_as_owner_after_reopen(self):
        path = self.folder("Stage-1.zuckervid")
        self.registry.bind_trusted("test:alice", self.alice.id, path.name)
        reopened = EngineProjectRegistry(self.root / "links.sqlite3", self.engine_data,
                                         ProjectCatalog(self.root / "catalog.sqlite3"))
        self.assertEqual(reopened.resolve_internal("test:alice", self.alice.id), path)
        with self.assertRaises(ProjectNotFound):
            reopened.resolve_internal("test:bob", self.alice.id)

    def test_foreign_project_and_duplicate_folder_never_link(self):
        self.folder("Saved.zuckervid")
        with self.assertRaises(ProjectNotFound):
            self.registry.bind_trusted("test:alice", self.bob.id, "Saved.zuckervid")
        self.registry.bind_trusted("test:alice", self.alice.id, "Saved.zuckervid")
        with self.assertRaises(ValueError):
            self.registry.bind_trusted("test:bob", self.bob.id, "Saved.zuckervid")
        with self.assertRaises(ValueError):
            self.registry.bind_trusted("test:alice", self.alice.id, "Saved.zuckervid")
        with self.assertRaises(ProjectNotFound):
            self.registry.resolve_internal("test:bob", self.bob.id)

    def test_no_arbitrary_folder_traversal_or_symlink(self):
        self.folder("Allowed")
        outside = self.root / "outsider"
        outside.mkdir()
        (outside / "project.json").write_text("{}")
        (self.engine_data / "Projects" / "shortcut").symlink_to(outside, target_is_directory=True)
        for name in ("../outsider", "/tmp", "..", ".", "shortcut", "missing", "a/b", " "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.registry.bind_trusted("test:alice", self.alice.id, name)
        with self.assertRaises(ProjectNotFound):
            self.registry.resolve_internal("test:alice", self.alice.id)

    def test_deleted_or_repointed_project_cannot_be_resolved(self):
        folder = self.folder("Ready")
        self.registry.bind_trusted("test:alice", self.alice.id, "Ready")
        (folder / "project.json").unlink()
        with self.assertRaises(ValueError):
            self.registry.resolve_internal("test:alice", self.alice.id)
        (folder / "project.json").symlink_to(self.root / "external.json")
        with self.assertRaises(ValueError):
            self.registry.resolve_internal("test:alice", self.alice.id)

    def test_does_not_activate_engine_or_write_project_contents(self):
        folder = self.folder("Work")
        before = (folder / "project.json").read_bytes()
        self.registry.bind_trusted("test:alice", self.alice.id, "Work")
        self.registry.resolve_internal("test:alice", self.alice.id)
        self.assertEqual((folder / "project.json").read_bytes(), before)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["project.json"])


if __name__ == "__main__":
    unittest.main()
