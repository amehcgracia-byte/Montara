"""Real WSGI requests: Engine activation only at a valid JM upload boundary."""
import unittest
from flask import Flask, jsonify, request

from urano.first_valid_upload_gate import FirstValidUploadEngineGate


class JMFirstValidUploadGateTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.ready = True
        app = Flask("test-real-jm-upload-gate")

        @app.route("/api/v1/wizard/upload", methods=["GET", "POST"])
        def upload():
            return jsonify(bytes=len(request.get_data()))

        @app.route("/montara/uploads", methods=["GET", "POST"])
        def resumable():
            return jsonify(ok=True)

        @app.get("/")
        def index():
            return "Original editor"

        def ensure():
            self.calls.append("ensure")
            if not self.ready:
                raise RuntimeError("No verified private worker")
            return {"ok": True, "state": "ready", "generation": 4}

        app.wsgi_app = FirstValidUploadEngineGate(
            app.wsgi_app, ensure_private_worker=ensure)
        self.client = app.test_client()

    def test_original_editor_and_upload_listing_do_not_start_engine(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/montara/uploads").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/wizard/upload").status_code, 200)
        self.assertEqual(self.calls, [])

    def test_actual_proxy_post_ensures_before_upload(self):
        result = self.client.post(
            "/api/v1/wizard/upload", data=b"small-proxy",
            content_type="application/octet-stream",
            headers={"X-Zucker-Filename": "camera.small.mp4"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["bytes"], len(b"small-proxy"))
        self.assertEqual(self.calls, ["ensure"])

    def test_real_resumable_create_ensures_and_never_consumes_body(self):
        response = self.client.post("/montara/uploads", json={
            "name": "cam.small.mp4", "size": 100,
            "fingerprint": "f" * 64, "video_preview": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, ["ensure"])

    def test_invalid_empty_and_wrong_routes_cannot_start_worker(self):
        for url, content, headers in (
            ("/api/v1/wizard/upload", b"", {"X-Zucker-Filename": "x.mp4"}),
            ("/api/v1/wizard/upload", b"x",
             {"X-Zucker-Filename": "../../owner-b/movie.mp4"}),
            ("/api/v1/wizard/upload", b"x", {}),
        ):
            with self.subTest(url=url, headers=headers):
                self.client.post(url, data=content,
                                 content_type="application/octet-stream",
                                 headers=headers)
        self.assertEqual(self.calls, [])

    def test_invalid_resumable_metadata_never_starts_or_forwards_upload(self):
        for body in (
            {"name": "../../private/camera.mp4", "size": 120,
             "fingerprint": "f" * 64},
            {"name": "camera.exe", "size": 120,
             "fingerprint": "f" * 64},
            {"name": "cam.small.mp4", "size": True,
             "fingerprint": "f" * 64},
            {"name": "cam.small.mp4", "size": 120,
             "fingerprint": "wrong"},
        ):
            with self.subTest(body=body):
                reply = self.client.post("/montara/uploads", json=body)
                self.assertEqual(reply.status_code, 400)
        self.assertEqual(self.calls, [])

    def test_no_upload_forwarded_when_private_engine_cannot_be_attested(self):
        self.ready = False
        response = self.client.post(
            "/api/v1/wizard/upload", data=b"private-proxy",
            content_type="application/octet-stream",
            headers={"X-Zucker-Filename": "camera.small.mp4"})
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"not ready", response.data)
        self.assertEqual(self.calls, ["ensure"])


if __name__ == "__main__":
    unittest.main()
