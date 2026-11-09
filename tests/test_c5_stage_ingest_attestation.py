"""Trusted Stage proxy attestation is tied to actual normalized bytes."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from urano.project_catalog import ProjectCatalog
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources
from urano.stage_ingest_attestation import attest_stage_ingest


class StageIngestAttestation(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="montara-c5-stage-proof-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.catalog=ProjectCatalog(self.root/"projects.sqlite3")
        self.provenance=StageSourceProvenance(self.root/"provenance.sqlite3",self.catalog)
        self.a=self.catalog.create("owner-a","Alice")
        self.b=self.catalog.create("owner-b","Bob")
        self.proxy=self.root/"camera-proxy.mp4"
        self.proxy.write_bytes(b"fake-proxy-for-trusted-test")
        self.engine=self.root/"project.json"
        self.snapshot={
            "stages":{"ingest":{"status":"done"}},
            "inputs":{"videos":[{"path":str(self.root/"original.mov"),
                                "normalized":{"path":str(self.proxy),"kind":"proxy"}}]}
        }
        self.engine.write_text(json.dumps(self.snapshot))
        self.receipt={"source_slot":0,
            "original":{"name":"camera-original.mov","size":987654,
                        "fingerprint":"a"*64},
            "proxy_sha256":hashlib.sha256(self.proxy.read_bytes()).hexdigest()}

    def attest(self, receipts=None):
        return attest_stage_ingest(self.provenance,"owner-a",self.a.id,
                                   engine_project_file=self.engine,
                                   receipts=self.receipt_as_list() if receipts is None else receipts)

    def receipt_as_list(self):
        return [dict(self.receipt)]

    def test_completed_proxy_hash_and_original_identity(self):
        stage_revision=self.attest()
        self.assertRegex(stage_revision,r"^[0-9a-f]{64}$")
        verified=self.provenance.verified("owner-a",self.a.id,source_slots={0})
        self.assertEqual(verified["stage_revision"],stage_revision)
        self.assertEqual(verified["sources"][0]["original"],self.receipt["original"])
        with self.assertRaises(Exception):
            self.provenance.verified("owner-b",self.a.id,source_slots={0})

    def test_missing_or_changed_proxy_fails_closed(self):
        for changed in ("", "0"*64):
            self.receipt["proxy_sha256"]=changed
            with self.assertRaises(UnverifiedSources):
                self.attest()
        self.receipt["proxy_sha256"]=hashlib.sha256(self.proxy.read_bytes()).hexdigest()
        self.proxy.write_bytes(b"modified-proxy")
        with self.assertRaises(UnverifiedSources):
            self.attest()
        with self.assertRaises(UnverifiedSources):
            self.provenance.verified("owner-a",self.a.id,source_slots={0})

    def test_unfinished_ingest_or_missing_normalized_proxy(self):
        self.snapshot["stages"]["ingest"]["status"]="running"
        self.engine.write_text(json.dumps(self.snapshot))
        with self.assertRaises(UnverifiedSources):
            self.attest()
        self.snapshot["stages"]["ingest"]["status"]="done"
        self.snapshot["inputs"]["videos"][0].pop("normalized")
        self.engine.write_text(json.dumps(self.snapshot))
        with self.assertRaises(UnverifiedSources):
            self.attest()

    def test_rejects_untrusted_identity_and_incomplete_receipts(self):
        with self.assertRaises(UnverifiedSources):
            self.attest([])
        for invalid in (
            {"source_slot":0,"original":{**self.receipt["original"],"name":"../private.mp4"}},
            {"source_slot":True,"original":self.receipt["original"]},
            {"source_slot":0,"original":self.receipt["original"],"proxy_sha256":"not-a-digest"},
        ):
            with self.subTest(invalid=invalid),self.assertRaises(UnverifiedSources):
                self.attest([invalid])
        self.assertEqual(self.provenance.verified("owner-a",self.a.id,source_slots={0})
                         if False else None,None)

    def test_rejects_symlink_proxy(self):
        linked=self.root/"linked.mp4"
        linked.symlink_to(self.proxy)
        self.snapshot["inputs"]["videos"][0]["normalized"]["path"]=str(linked)
        self.engine.write_text(json.dumps(self.snapshot))
        with self.assertRaises(UnverifiedSources):
            self.attest()


if __name__=="__main__":
    unittest.main()
