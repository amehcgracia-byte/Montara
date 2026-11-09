"""The Stage certificate can only follow an authenticated Companion receipt.

Synthetic fixture: actual SHA-256 source/normalized bytes and owner binding.
No user original, public key registration or Docker privileges needed.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from urano.project_catalog import ProjectCatalog
from urano.engine_bindings import EngineProjectRegistry
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources
from urano.stage_ingest_attestation import attest_authenticated_inbox, attest_authenticated_worker_proof


class AuthenticatedIngestAttestation(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="montara-c5-trusted-receipt-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.catalog=ProjectCatalog(self.root/"catalog.sqlite3")
        self.project=self.catalog.create("owner-a","A")
        self.workspace=self.root/"workspace"
        self.folder=self.workspace/"Projects"/"OwnerA"
        self.folder.mkdir(parents=True)
        self.inputdir=self.folder/"inputs"/"urano-staged-proxies"
        self.inputdir.mkdir(parents=True)
        self.engine=self.folder/"project.json"
        self.engine.write_text("{}")
        self.binding=EngineProjectRegistry(
            self.root/"bindings.sqlite3",self.workspace,self.catalog)
        self.binding.bind_trusted("owner-a",self.project.id,"OwnerA")
        self.provenance=StageSourceProvenance(
            self.root/"provenance.sqlite3",self.catalog)
        self.inbox=self.root/"inbox"
        self.inbox.mkdir()
        self.owner_inbox=self.inbox/hashlib.sha256(b"owner-a").hexdigest()/self.project.id
        self.owner_inbox.mkdir(parents=True)
        self.blob=b"transferred-private-proxy"*420
        self.hash=hashlib.sha256(self.blob).hexdigest()
        name=f"camera-0-{self.hash}.mp4"
        self.stage_input=self.inputdir/name
        self.stage_input.write_bytes(self.blob)
        self.normalized=self.root/"normalized.mp4"
        self.normalized.write_bytes(b"FFmpeg-produced-stage-output")
        self.project_data={
            "stages":{"ingest":{"status":"done"}},
            "inputs":{"videos":[{"path":str(self.stage_input),
                "normalized":{"path":str(self.normalized)}}]}}
        self.engine.write_text(json.dumps(self.project_data))
        self.upload=self.owner_inbox/f"slot-0-{self.hash}.mp4"
        self.upload.write_bytes(self.blob)
        self.meta=self.owner_inbox/f"slot-0-{self.hash}.json"
        self.entry={"source_slot":0,"proxy_sha256":self.hash,
            "original_claim":{"name":"user-original.mov","size":123456,
                              "fingerprint":"a"*64},
            "attested":False,"bytes":len(self.blob),"receipt_authenticated":True}
        self.meta.write_text(json.dumps(self.entry))

    def attest(self, owner="owner-a"):
        return attest_authenticated_inbox(
            self.provenance,self.binding,self.inbox,owner,self.project.id,
            engine_project_file=self.engine)

    def test_isolated_worker_hashes_certify_without_reading_engine_files(self):
        # Simulate an Engine project with UID-only permissions. The backend
        # must verify owner-specific inbox hashes, not open project.json.
        proof=[{"slot":0,"proxy_sha256":self.hash,
                "normalized_sha256":hashlib.sha256(
                    self.normalized.read_bytes()).hexdigest()}]
        self.engine.chmod(0o000)
        revision=attest_authenticated_worker_proof(
            self.provenance,self.inbox,"owner-a",self.project.id,proof=proof)
        self.assertRegex(revision,r"^[a-f0-9]{64}$")
        certified=self.provenance.verified(
            "owner-a",self.project.id,source_slots={0})
        self.assertEqual(certified["sources"][0]["original"],
                         self.entry["original_claim"])
        self.provenance.invalidate_trusted("owner-a",self.project.id)
        self.entry["receipt_authenticated"]=False
        self.meta.write_text(json.dumps(self.entry))
        with self.assertRaises(UnverifiedSources):
            attest_authenticated_worker_proof(
                self.provenance,self.inbox,"owner-a",self.project.id,proof=proof)

    def test_previous_signed_receipt_cannot_recertify_after_slot_replacement(self):
        proof=[{"slot":0,"proxy_sha256":self.hash,
                "normalized_sha256":"b"*64}]
        replacement_hash="f"*64
        other=self.owner_inbox/f"slot-0-{replacement_hash}.json"
        other.write_text(json.dumps({
            "source_slot":0,"proxy_sha256":replacement_hash,
            "original_claim":{"name":"new-camera.mp4","size":789,
                              "fingerprint":"c"*64},
            "attested":False,"bytes":789,"receipt_authenticated":True}))
        with self.assertRaises(UnverifiedSources):
            attest_authenticated_worker_proof(
                self.provenance,self.inbox,"owner-a",self.project.id,proof=proof)
        with self.assertRaises(UnverifiedSources):
            self.provenance.verified("owner-a",self.project.id,source_slots={0})

    def test_worker_proof_detects_swapped_camera_hash_and_modified_inbox(self):
        proof=[{"slot":0,"proxy_sha256":self.hash,
                "normalized_sha256":"f"*64}]
        invalid=[dict(proof[0],proxy_sha256="a"*64)]
        with self.assertRaises(UnverifiedSources):
            attest_authenticated_worker_proof(
                self.provenance,self.inbox,"owner-a",self.project.id,proof=invalid)
        self.upload.write_bytes(b"not-the-receipted-proxy")
        with self.assertRaises(UnverifiedSources):
            attest_authenticated_worker_proof(
                self.provenance,self.inbox,"owner-a",self.project.id,proof=proof)
        with self.assertRaises(UnverifiedSources):
            self.provenance.verified("owner-a",self.project.id,source_slots={0})

    def test_authenticated_signed_receipt_can_be_attested_after_stage_done(self):
        revision=self.attest()
        self.assertRegex(revision,r"^[a-f0-9]{64}$")
        result=self.provenance.verified("owner-a",self.project.id,source_slots={0})
        self.assertEqual(result["sources"][0]["original"],self.entry["original_claim"])
        self.assertEqual(result["stage_revision"],revision)

    def test_old_untrusted_browser_claim_never_produces_certificate(self):
        self.entry["receipt_authenticated"]=False
        self.meta.write_text(json.dumps(self.entry))
        with self.assertRaises(UnverifiedSources):
            self.attest()
        with self.assertRaises(UnverifiedSources):
            self.provenance.verified("owner-a",self.project.id,source_slots={0})

    def test_tampered_stage_bytes_wrong_owner_and_false_ingest_done(self):
        with self.assertRaises(Exception):
            self.attest(owner="owner-b")
        self.stage_input.write_bytes(b"replaced-input")
        with self.assertRaises(UnverifiedSources):
            self.attest()
        self.stage_input.write_bytes(self.blob)
        self.project_data["stages"]["ingest"]["status"]="running"
        self.engine.write_text(json.dumps(self.project_data))
        with self.assertRaises(UnverifiedSources):
            self.attest()

    def test_docker_workspace_paths_map_only_inside_trusted_owner_mount(self):
        cache=self.workspace/"Cache"
        cache.mkdir()
        normalized=cache/"normalized.mp4"
        normalized.write_bytes(self.normalized.read_bytes())
        inner=Path("/workspace")
        source_relative=self.stage_input.relative_to(self.workspace)
        self.project_data["inputs"]["videos"][0]["path"]=str(inner/source_relative)
        self.project_data["inputs"]["videos"][0]["normalized"]["path"]=str(
            inner/normalized.relative_to(self.workspace))
        self.engine.write_text(json.dumps(self.project_data))
        revision=attest_authenticated_inbox(
            self.provenance,self.binding,self.inbox,"owner-a",self.project.id,
            engine_project_file=self.engine,container_workspace=inner)
        self.assertRegex(revision,r"^[a-f0-9]{64}$")
        self.provenance.invalidate_trusted("owner-a",self.project.id)
        self.project_data["inputs"]["videos"][0]["path"]=str(
            Path("/workspace-other")/source_relative)
        self.engine.write_text(json.dumps(self.project_data))
        with self.assertRaises(UnverifiedSources):
            attest_authenticated_inbox(
                self.provenance,self.binding,self.inbox,"owner-a",self.project.id,
                engine_project_file=self.engine,container_workspace=inner)

    def test_change_or_replay_of_receipt_or_staged_bytes_fails(self):
        self.entry["proxy_sha256"]="f"*64
        self.meta.write_text(json.dumps(self.entry))
        with self.assertRaises(UnverifiedSources):
            self.attest()
        self.entry["proxy_sha256"]=self.hash
        self.meta.write_text(json.dumps(self.entry))
        self.upload.write_bytes(b"altered-after-receipt")
        with self.assertRaises(UnverifiedSources):
            self.attest()
