"""I38 authentic JM Engine -> existing U13A private Owner project registry."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from urano.engine_bindings import EngineProjectRegistry
from urano.owner_jm_editor_handoff import (
    EditorHandoffDenied, bind_open_jm_editor_project,
)
from urano.project_catalog import ProjectCatalog, ProjectNotFound


class FakeEngine:
    def __init__(self, folder):
        self.folder = folder
        self.ok = True
        self.application = SimpleNamespace(config={
            "ZUCKER_STATE": SimpleNamespace(project=SimpleNamespace(folder=folder))
        })

    def get(self, path):
        assert path == "/api/v1/project"
        return SimpleNamespace(
            status_code=200 if self.ok else 500,
            get_json=lambda: {"stages": {}} if self.ok else None,
        )


class OwnerJMEditorHandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.catalog = ProjectCatalog(root / "owner.sqlite3")
        self.data = root / "engine"
        (self.data / "Projects").mkdir(parents=True)
        self.registry = EngineProjectRegistry(
            root / "bindings.sqlite3", self.data, self.catalog)
        self.project = self.catalog.create(
            "owner-a", "A Stage",
            recipe={"montara_beta_workspace": {"mode": "stage", "version": 1}},
        )
        self.push = self.catalog.create(
            "owner-a", "Push",
            recipe={"montara_beta_workspace": {"mode": "push", "version": 1}},
        )
        self.other = self.catalog.create(
            "owner-b", "Other Stage",
            recipe={"montara_beta_workspace": {"mode": "stage", "version": 1}},
        )
        self.folder = self.data / "Projects" / self.project.id
        self.folder.mkdir()
        (self.folder / "project.json").write_text("{}", encoding="utf-8")
        self.engine = FakeEngine(self.folder)

    def bind(self, *, owner="owner-a", project=None, mode="stage"):
        return bind_open_jm_editor_project(
            owner_id=owner, project_id=project or self.project.id,
            mode=mode, catalog=self.catalog, registry=self.registry,
            engine_client=self.engine,
        )

    def test_authentic_engine_folder_binds_to_existing_owner_uuid(self):
        result = self.bind()
        self.assertEqual(result.catalog_project_id, self.project.id)
        self.assertEqual(result.folder_name, self.project.id)
        self.assertEqual(
            self.registry.resolve_internal("owner-a", self.project.id),
            self.folder,
        )
        with self.assertRaises(ProjectNotFound):
            self.registry.resolve_internal("owner-b", self.project.id)

    def test_same_owner_can_reopen_same_real_jm_project(self):
        first = self.bind()
        second = self.bind()
        self.assertEqual(first, second)
        self.assertEqual(self.registry.resolve_internal(
            "owner-a", self.project.id), self.folder)

    def test_foreign_owner_wrong_mode_and_push_are_denied(self):
        for kwargs in (
            {"owner": "owner-b"},
            {"project": self.other.id},
            {"project": self.push.id},
            {"mode": "push"},
            {"mode": "show"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(EditorHandoffDenied):
                self.bind(**kwargs)
        with self.assertRaises(ProjectNotFound):
            self.registry.resolve_internal("owner-a", self.project.id)

    def test_wrong_global_project_and_empty_engine_denied(self):
        foreign_folder = self.data / "Projects" / self.other.id
        foreign_folder.mkdir()
        (foreign_folder / "project.json").write_text("{}")
        self.engine.application.config["ZUCKER_STATE"].project.folder = foreign_folder
        with self.assertRaises(EditorHandoffDenied):
            self.bind()
        self.engine.application.config["ZUCKER_STATE"].project.folder = None
        with self.assertRaises(EditorHandoffDenied):
            self.bind()

    def test_deny_unavailable_engine_or_symlink(self):
        self.engine.ok = False
        with self.assertRaises(EditorHandoffDenied):
            self.bind()
        self.engine.ok = True
        self.engine.application.config["ZUCKER_STATE"].project.folder = (
            self.folder.parent / "fake-link"
        )
        (self.folder.parent / "fake-link").symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(EditorHandoffDenied):
            self.bind()


if __name__ == "__main__":
    unittest.main()
