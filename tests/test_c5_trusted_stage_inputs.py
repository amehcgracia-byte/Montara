"""C5 private inbox -> trusted Engine project -> fixed worker registration.

Synthetic fixtures only. No Docker, public path or original media upload.
"""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from urano.project_catalog import ProjectCatalog
from urano.engine_bindings import EngineProjectRegistry
from urano.trusted_stage_inputs import prepare_trusted_stage_inputs
from urano.stage_source_provenance import UnverifiedSources
from urano.engine_worker_process import run
from test_urano_stage_worker_protocol import EngineClient, Response


class RegisteredEngine(EngineClient):
    def __init__(self, project_folder):
        super().__init__(project_folder)
        self.registered = []
    def post(self, endpoint, json=None):
        if endpoint == "/api/v1/inputs/videos":
            self.registered = json["paths"]
            return Response(200, {"videos":self.registered})
        return super().post(endpoint, json=json)


class TrustedPrivateStageInputs(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="montara-c5-private-promo-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.catalog=ProjectCatalog(self.root/"catalog.sqlite3")
        self.own=self.catalog.create("owner-a","A")
        self.other=self.catalog.create("owner-b","B")
        self.workspace=self.root/"engine"
        self.project=self.workspace/"Projects"/"OwnedAlice"
        self.project.mkdir(parents=True)
        (self.project/"project.json").write_text("{}")
        self.registry=EngineProjectRegistry(self.root/"bindings.sqlite3",
                                           self.workspace,self.catalog)
        self.registry.bind_trusted("owner-a",self.own.id,"OwnedAlice")
        self.inbox=self.root/"proxy-inbox"
        self.inbox.mkdir()
        self.owner_folder=self.inbox/hashlib.sha256(b"owner-a").hexdigest()/self.own.id
        self.owner_folder.mkdir(parents=True)
        self.proxy=b"proxy-bytes-for-stage-test"*600
        self.hash=hashlib.sha256(self.proxy).hexdigest()
        self.original={"name":"camera-original.mp4","size":99999,"fingerprint":"a"*64}
        self.stage_file=self.owner_folder/f"slot-0-{self.hash}.mp4"
        self.stage_file.write_bytes(self.proxy)
        self.receipt=self.owner_folder/f"slot-0-{self.hash}.json"
        self.receipt.write_text(json.dumps({
            "source_slot":0,"proxy_sha256":self.hash,
            "original_claim":self.original,"attested":False,"bytes":len(self.proxy)}))

    def prepare(self, owner="owner-a", project=None):
        return prepare_trusted_stage_inputs(self.registry,self.inbox,
                                            owner,project or self.own.id,source_slots={0})

    def test_staged_proxy_registers_in_exact_opened_private_engine(self):
        prepared=self.prepare()
        self.assertEqual(len(prepared),1)
        self.assertEqual(prepared[0].read_bytes(),self.proxy)
        self.assertTrue(prepared[0].is_relative_to(self.project))
        self.assertFalse(prepared[0].is_symlink())

        worker=RegisteredEngine(self.project)
        commands=[{"op":"open","folder":"OwnedAlice"},
                  {"op":"register_staged_proxies"},{"op":"stop"}]
        out=io.StringIO()
        run(io.StringIO("".join(json.dumps(cmd)+"\n" for cmd in commands)),
            out,engine_dir=self.root,data_root=self.workspace,
            make_client=lambda *_:worker)
        packets=[json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(packets[1]["type"],"opened")
        self.assertEqual(packets[2],{"ok":True,"type":"staged_inputs_registered",
                                     "source_count":1})
        self.assertEqual(worker.registered,[str(prepared[0])])

    def test_owner_wrong_digest_and_ambiguous_slot_rejected(self):
        with self.assertRaises(Exception):
            self.prepare(owner="owner-b",project=self.own.id)
        self.stage_file.write_bytes(b"changed")
        with self.assertRaises(UnverifiedSources):
            self.prepare()
        self.stage_file.write_bytes(self.proxy)
        second_hash="f"*64
        (self.owner_folder/f"slot-0-{second_hash}.json").write_text(
            self.receipt.read_text())
        with self.assertRaises(UnverifiedSources):
            self.prepare()

    def test_worker_rejects_unprepared_or_argument_injection(self):
        engine=RegisteredEngine(self.project)
        commands=[{"op":"open","folder":"OwnedAlice"},
                  {"op":"register_staged_proxies","path":"/tmp/foreign.mp4"},
                  {"op":"register_staged_proxies"},{"op":"stop"}]
        output=io.StringIO()
        run(io.StringIO("".join(json.dumps(cmd)+"\n" for cmd in commands)),
            output,engine_dir=self.root,data_root=self.workspace,
            make_client=lambda *_:engine)
        messages=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertFalse(messages[2]["ok"])
        self.assertFalse(messages[3]["ok"])
        self.assertEqual(engine.registered,[])

    def test_worker_detects_changed_copied_proxy(self):
        prepared=self.prepare()
        prepared[0].write_bytes(b"tampered-input")
        engine=RegisteredEngine(self.project)
        output=io.StringIO()
        commands=[{"op":"open","folder":"OwnedAlice"},
                  {"op":"register_staged_proxies"},{"op":"stop"}]
        run(io.StringIO("".join(json.dumps(cmd)+"\n" for cmd in commands)),
            output,engine_dir=self.root,data_root=self.workspace,
            make_client=lambda *_:engine)
        messages=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertFalse(messages[2]["ok"])
        self.assertEqual(engine.registered,[])


if __name__=="__main__":
    unittest.main()
