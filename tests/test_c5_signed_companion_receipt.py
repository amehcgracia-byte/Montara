"""C5 signed Companion receipts: scoped, operator-paired and fail-closed."""
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path

from test_c5_private_proxy_inbox import TestC5PrivateProxyInbox
from test_google_flow_contract import CLIENT, CALLBACK, HOST
from urano.companion_receipt_auth import CompanionReceiptVerifier
from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api
from urano.stage_source_provenance import UnverifiedSources


class TestC5SignedCompanionReceipt(unittest.TestCase):
    def setUp(self):
        self.fixture=TestC5PrivateProxyInbox("test_disabled_by_default_and_no_original_upload")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        fx=self.fixture
        self.secret=fx.root/"owner-companion-key"
        self.secret.write_bytes(os.urandom(32))
        self.secret.chmod(0o600)
        self.verifier=CompanionReceiptVerifier({"owner-placeholder":self.secret})
        self.app=create_owner_api(fx.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                frozenset({"alpha@example.test","beta@example.test"})),
            provider=fx.google,enable_dashboard=True,
            proxy_staging_root=fx.staging,
            receipt_verifier=self.verifier)
        fx.app=self.app
        fx.a,fx.b=self.app.test_client(),self.app.test_client()

    def envelope(self,project,slot,original,digest,secret=None):
        payload={"schema":"montara-companion-proxy-receipt-v1",
                 "project_id":project,"source_slot":slot,"original":original,
                 "proxy_sha256":digest}
        signature=hmac.new(secret or self.secret.read_bytes(),
                json.dumps(payload,sort_keys=True,separators=(",",":"),
                           ensure_ascii=True).encode(),hashlib.sha256).hexdigest()
        return {"receipt":payload,"signature":signature}

    def send(self,client,project,slot,payload,csrf,original,envelope=None):
        digest=hashlib.sha256(payload).hexdigest()
        headers={"Origin":HOST,"X-Urano-CSRF":csrf,
                 "X-Urano-Proxy-SHA256":digest,
                 "X-Urano-Original-Claim":json.dumps(original)}
        if envelope is not None:
            headers["X-Urano-Signed-Receipt"]=json.dumps(envelope)
        return client.put(
            f"/urano/v1/proxy-inbox/projects/{project}/slots/{slot}",
            base_url=HOST,headers=headers,
            data=payload,content_type="video/mp4")

    def test_signature_required_and_scoped_to_exact_owner_project_slot_and_proxy(self):
        fx=self.fixture
        owner_a,csrf_a=fx.login(fx.a,sub="signed-a",email="alpha@example.test")
        owner_b,csrf_b=fx.login(fx.b,sub="signed-b",email="beta@example.test")
        self.verifier._keys={owner_a:self.secret}
        project_a=fx.setup_project(fx.a)
        project_b=fx.setup_project(fx.b)
        original={"name":"my-camera.mov","size":78998,"fingerprint":"a"*64}
        blob=b"this-is-a-proxy"*150
        digest=hashlib.sha256(blob).hexdigest()
        good=self.envelope(project_a,0,original,digest)
        self.assertEqual(self.send(fx.a,project_a,0,blob,csrf_a,original).status_code,403)
        self.assertEqual(self.send(fx.b,project_b,0,blob,csrf_b,original,good).status_code,403)
        self.assertEqual(self.send(fx.a,project_a,1,blob,csrf_a,original,good).status_code,403)
        changed=self.envelope(project_b,0,original,digest)
        self.assertEqual(self.send(fx.a,project_a,0,blob,csrf_a,original,changed).status_code,403)
        fake={**good,"signature":"0"*64}
        self.assertEqual(self.send(fx.a,project_a,0,blob,csrf_a,original,fake).status_code,403)
        corrupted=good.copy()
        corrupted["receipt"]={**good["receipt"],"original":{
            **original,"fingerprint":"b"*64}}
        self.assertEqual(self.send(fx.a,project_a,0,blob,csrf_a,original,corrupted).status_code,403)
        self.assertEqual(list(fx.staging.rglob("*.mp4")),[])
        accepted=self.send(fx.a,project_a,0,blob,csrf_a,original,good)
        self.assertEqual(accepted.status_code,201,accepted.get_data(as_text=True))
        self.assertIs(accepted.json["attested"],False)
        self.assertIs(accepted.json["receipt_authenticated"],True)
        record=json.loads(next(fx.staging.rglob("*.json")).read_text())
        self.assertIs(record["receipt_authenticated"],True)
        self.assertIs(record["attested"],False)

    def test_untrusted_key_and_modified_payload_rejected(self):
        original={"name":"camera.mp4","size":12,"fingerprint":"a"*64}
        project="01234567-89ab-cdef-0123-456789abcdef"
        digest="b"*64
        envelope=self.envelope(project,0,original,digest)
        with self.assertRaises(UnverifiedSources):
            self.verifier.verify("unpaired-owner",project,0,digest,original,envelope)
        self.verifier._keys={"owned":self.secret}
        with self.assertRaises(UnverifiedSources):
            self.verifier.verify("owned",project,0,"c"*64,original,envelope)
        self.secret.chmod(0o644)
        with self.assertRaises(UnverifiedSources):
            self.verifier.verify("owned",project,0,digest,original,envelope)
