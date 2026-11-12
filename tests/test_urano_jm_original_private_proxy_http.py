"""I55 direct ORIGINAL Chema resumable HTTP test, opt-in 2 GiB previews.

Requires MONTARA_ORIGINAL_JM_UPLOAD_SOURCE pointing to the reviewed JM
resumable_upload.py. A source-overlay is compiled IN MEMORY and registered on
a test-only Flask app with a minimal session.save stub. No Engine or user media
is involved; actual video classification remains covered by earlier I54.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from urano.jm_private_proxy_overlay import patched_original_resumable_upload


class OriginalJMPrivateProxyLimitsTest(unittest.TestCase):
    def test_reviewed_original_upload_limit_and_real_http(self):
        original=os.environ.get("MONTARA_ORIGINAL_JM_UPLOAD_SOURCE")
        if not original:
            self.skipTest("Full reviewed JM source not provided")
        source=Path(original).read_text(encoding="utf-8")
        patched=patched_original_resumable_upload(source)
        library=types.ModuleType("mixer_adapter")
        session=types.ModuleType("mixer_adapter.session")
        def save(path, data):
            Path(path).write_text(json.dumps(data),encoding="utf-8")
        session.save=save
        library.session=session
        with patch.dict(sys.modules,{
            "mixer_adapter":library, "mixer_adapter.session":session
        }), patch.dict(os.environ,{
            "MONTARA_SESSION_TOKEN":"private-test-token",
            "MONTARA_PRIVATE_PROXY_LIMIT_MIB":"2048",
        }):
            namespace={"__name__":"reviewed_chema_resumable"}
            exec(compile(patched,str(original),"exec"),namespace)
            with tempfile.TemporaryDirectory(prefix="montara-i55-direct-http-") as temp:
                app=Flask("private-jm-original-resumable")
                namespace["register_resumable_upload"](
                    app,Path(temp),lambda files:{
                        "videos":[{"path":str(files[0])}], "ignored":[]})
                client=app.test_client()
                limits=client.get("/montara/uploads")
                self.assertEqual(limits.status_code,200)
                self.assertEqual(limits.json["max_file_bytes"],2048*1024**2)
                self.assertEqual(limits.json["max_original_file_bytes"],256*1024**2)
                large=client.post("/montara/uploads",json={
                    "name":"camera.small.mp4","size":650*1024**2,
                    "fingerprint":"f"*64,"video_preview":True,
                    "original":{"name":"camera.mp4","size":3*1024**3,
                                "fingerprint":"e"*64}})
                self.assertEqual(large.status_code,201,large.json)
                self.assertEqual(large.json["chunk_size"],16*1024**2)
                repeated=client.post("/montara/uploads",json={
                    "name":"camera.small.mp4","size":650*1024**2,
                    "fingerprint":"f"*64,"video_preview":True,
                    "original":{"name":"camera.mp4","size":3*1024**3,
                                "fingerprint":"e"*64}})
                self.assertEqual(repeated.status_code,200)
                self.assertEqual(repeated.json["id"],large.json["id"])
                denied=client.post("/montara/uploads",json={
                    "name":"camera.mp4","size":650*1024**2,
                    "fingerprint":"f"*64,"original_video_consent":True})
                self.assertEqual(denied.status_code,413,denied.json)
                # The real JM cancellation route releases only unfinished
                # upload state, without storing the promised 650 MiB.
                cancelled=client.delete("/montara/uploads/"+large.json["id"])
                self.assertEqual(cancelled.status_code,200)
                self.assertTrue(cancelled.json["deleted"])
                self.assertFalse((Path(temp)/"Uploads"/large.json["id"]).exists())

    def test_invalid_operator_proxy_cap_fails_before_registering_routes(self):
        original=os.environ.get("MONTARA_ORIGINAL_JM_UPLOAD_SOURCE")
        if not original:
            self.skipTest("Full reviewed JM source not provided")
        patched=patched_original_resumable_upload(Path(original).read_text())
        lib=types.ModuleType("mixer_adapter")
        session=types.ModuleType("mixer_adapter.session")
        session.save=lambda path,data:None
        with patch.dict(sys.modules,{
            "mixer_adapter":lib,"mixer_adapter.session":session
        }),patch.dict(os.environ,{
            "MONTARA_SESSION_TOKEN":"private-test-token",
            "MONTARA_PRIVATE_PROXY_LIMIT_MIB":"99999",
        }):
            namespace={"__name__":"reviewed_chema_upload"}
            exec(compile(patched,str(original),"exec"),namespace)
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
                    namespace["register_resumable_upload"](
                        Flask("fail-closed"),Path(root),lambda files: {})
                

if __name__=="__main__":
    unittest.main()
