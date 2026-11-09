"""Companion C5 local evidence: proxy bytes + original edge fingerprint.

No real user media or external network, and no server-trusted receipt implied.
"""
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

COMPANION=Path(__file__).resolve().parents[1]/"companion"


class C5CompanionProxyReceipt(unittest.TestCase):
    def test_original_proxy_receipt_and_mutation_denial(self):
        script=textwrap.dedent(r'''
            import hashlib
            import json
            import os
            import sys
            from pathlib import Path
            root=Path(sys.argv[2])
            os.environ["MONTARA_COMPANION_HOME"]=str(root/"home")
            sys.path.insert(0,sys.argv[1])
            import companion
            original=root/"camera-original.mp4"
            original.write_bytes(b"original-data"*4500)
            companion.CACHE.mkdir(parents=True,exist_ok=True)
            identity={"name":original.name,"size":original.stat().st_size,
                      "fingerprint":companion.fingerprint(original)}
            key=hashlib.sha256(
                f"{identity['name']}|{identity['size']}|{identity['fingerprint']}".encode()
            ).hexdigest()[:24]
            companion.sources[key]=original
            companion.jobs[key]={"status":"ready"}
            proxy=companion.output_path(key)
            proxy.write_bytes(b"proxy-bytes"*3000)
            proxy.with_suffix(".quality.json").write_text(
                json.dumps({"recipe":companion.VIDEO_PROXY_RECIPE}))
            receipt=companion.video_proxy_receipt(key)
            assert receipt["original"]==identity
            assert receipt["proxy_sha256"]==hashlib.sha256(proxy.read_bytes()).hexdigest()
            assert "path" not in receipt and "source_files" not in receipt
            proxy.write_bytes(b"changed-proxy"*3000)
            assert companion.video_proxy_receipt(key)["proxy_sha256"] != receipt["proxy_sha256"]
            proxy.write_bytes(b"proxy-bytes"*3000)
            original.write_bytes(b"changed-original"*4500)
            try:
                companion.video_proxy_receipt(key)
                raise AssertionError("Changed original incorrectly accepted")
            except ValueError:
                pass
            original.write_bytes(b"original-data"*4500)
            companion.jobs[key]["status"]="working"
            try:
                companion.video_proxy_receipt(key)
                raise AssertionError("Incomplete proxy incorrectly accepted")
            except ValueError:
                pass
            # Same bytes: actual Companion receipt can be checked against a
            # completed Stage snapshot by a trusted ingest-side caller.
            from urano.project_catalog import ProjectCatalog
            from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources
            from urano.stage_ingest_attestation import attest_stage_ingest
            catalog=ProjectCatalog(root/"catalog.sqlite3")
            project=catalog.create("owner-stage","Receipt integration")
            provenance=StageSourceProvenance(root/"provenance.sqlite3",catalog)
            companion.sources[key]=original
            companion.jobs[key]["status"]="ready"
            actual_receipt=companion.video_proxy_receipt(key)
            staged=root/"staged.mp4"
            staged.write_bytes(proxy.read_bytes())
            project_file=root/"project.json"
            project_file.write_text(json.dumps({
              "stages":{"ingest":{"status":"done"}},
              "inputs":{"videos":[{"normalized":{"path":str(staged),"kind":"proxy"}}]}
            }))
            envelope=[{"source_slot":0,**actual_receipt}]
            revision=attest_stage_ingest(provenance,"owner-stage",project.id,
                                         engine_project_file=project_file,receipts=envelope)
            assert provenance.verified("owner-stage",project.id,source_slots={0})["stage_revision"]==revision
            staged.write_bytes(b"modified-stage-proxy")
            try:
                attest_stage_ingest(provenance,"owner-stage",project.id,
                                    engine_project_file=project_file,receipts=envelope)
                raise AssertionError("Mismatched Stage bytes accepted")
            except UnverifiedSources:
                pass
            print("LOCAL_PROXY_RECEIPT_PASS")
        ''')
        with tempfile.TemporaryDirectory(prefix="montara-c5-receipt-") as folder:
            process=subprocess.run(
                [sys.executable,"-c",script,str(COMPANION),folder],
                capture_output=True,text=True,timeout=25)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        self.assertIn("LOCAL_PROXY_RECEIPT_PASS",process.stdout)


if __name__=="__main__":
    unittest.main()
