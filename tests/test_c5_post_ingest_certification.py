"""C5 operator-only post-Ingest certification is serialized by owner."""
import tempfile
import unittest
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock, patch

from urano.owner_runtime_controller import OwnerRuntimeController
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources


class TestC5PostIngestCertification(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="montara-c5-auto-attest-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        catalog=ProjectCatalog(self.root/"catalog.sqlite3")
        project=catalog.create("owner-a","Private camera")
        self.project_id=project.id
        self.owner="owner-a"
        self.provenance=StageSourceProvenance(self.root/"provenance.sqlite3",catalog)
        self.inbox=self.root/"private-inbox"
        self.inbox.mkdir()
        self.project_dir=self.root/"Engine"/"Projects"/"OwnerA"
        self.project_dir.mkdir(parents=True)
        (self.project_dir/"project.json").write_text("{}")
        self.bindings=Mock()
        self.bindings.resolve_internal.return_value=self.project_dir
        self.bridge=SimpleNamespace(
            guard=SimpleNamespace(
                bindings=self.bindings,
                get_state=Mock(return_value=("busy",self.project_id,1))),
            runtime_id="test-only-owner-runtime",
            ingest_status=Mock(return_value="done"))
        self.controller=OwnerRuntimeController()
        self.controller._worker=lambda owner:(self.bridge,RLock())

    def test_configuration_is_explicit_and_fails_closed(self):
        with self.assertRaises(ValueError):
            self.controller.configure_trusted_attestation(
                self.provenance,self.root/"missing")
        self.controller.configure_trusted_attestation(
            self.provenance,self.inbox,container_workspace=Path("/workspace"))
        with self.assertRaises(ValueError):
            self.controller.configure_trusted_attestation(
                self.provenance,self.inbox,container_workspace=Path("/workspace"))

    def test_only_real_done_triggers_owner_scoped_attestation(self):
        self.controller.configure_trusted_attestation(
            self.provenance,self.inbox,container_workspace=Path("/workspace"))
        with patch("urano.owner_runtime_controller.attest_authenticated_inbox",
                   return_value="a"*64) as attest:
            self.bridge.ingest_status.return_value="running"
            self.assertEqual(
                self.controller.ingest_status(self.owner,self.project_id),"running")
            attest.assert_not_called()
            self.bridge.ingest_status.return_value="done"
            self.assertEqual(
                self.controller.ingest_status(self.owner,self.project_id),"done")
            attest.assert_called_once_with(
                self.provenance,self.bindings,self.inbox,self.owner,self.project_id,
                engine_project_file=self.project_dir/"project.json",
                container_workspace=Path("/workspace"))

    def test_invalid_receipt_leaves_stage_done_but_certificate_unavailable(self):
        sources=[{"source_slot":0,"original":{
            "name":"camera.mp4","size":9999,"fingerprint":"a"*64}}]
        self.provenance.register_trusted(
            self.owner,self.project_id,sources,stage_revision="b"*64)
        self.controller.configure_trusted_attestation(self.provenance,self.inbox)
        with patch("urano.owner_runtime_controller.attest_authenticated_inbox",
                   side_effect=UnverifiedSources("invalid receipt")):
            self.assertEqual(
                self.controller.ingest_status(self.owner,self.project_id),"done")
        with self.assertRaises(UnverifiedSources):
            self.provenance.verified(self.owner,self.project_id,source_slots={0})

    def test_unprovisioned_mode_keeps_legacy_stage_status(self):
        with patch("urano.owner_runtime_controller.attest_authenticated_inbox") as attest:
            self.assertEqual(
                self.controller.ingest_status(self.owner,self.project_id),"done")
            attest.assert_not_called()

    def test_foreign_owner_never_certifies(self):
        self.controller.configure_trusted_attestation(self.provenance,self.inbox)
        self.bindings.resolve_internal.side_effect=ProjectNotFound("foreign")
        with patch("urano.owner_runtime_controller.attest_authenticated_inbox") as attest:
            with self.assertRaises(ProjectNotFound):
                self.controller.ingest_status("owner-b",self.project_id)
            attest.assert_not_called()


if __name__=="__main__":
    unittest.main()
