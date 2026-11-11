"""I40 Unix WSGI transport tests, real socket, strict peer and method gate."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from flask import Flask, jsonify

from urano.private_jm_wsgi_socket import (
    SOCKET_FILE, VerifiedJMUnixConnection, create_private_jm_wsgi_server,
)


class OriginalJMUnixTransportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.directory.chmod(0o700)
        app = Flask("jm-wsgi-private-test")

        @app.get("/")
        def index():
            return "<html>Real Montara</html>"

        @app.get("/api/v1/wizard/status")
        def status():
            return jsonify(status="pending")

        @app.post("/api/v1/wizard/start")
        def write():
            raise AssertionError("Lab client must never send edits")

        self.server, self.path = create_private_jm_wsgi_server(
            app, self.directory)
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.path.unlink(missing_ok=True)

    def connection(self, **override):
        return VerifiedJMUnixConnection(
            self.path, expected_pid=override.get("pid", os.getpid()),
            expected_uid=override.get("uid", os.getuid()), timeout=2)

    def test_original_wsgi_response_over_real_unix_socket(self):
        with self.connection() as conn:
            code, kind, body = conn.get_safe_read("/")
        self.assertEqual(code, 200)
        self.assertIn("text/html", kind)
        self.assertIn(b"Real Montara", body)

    def test_original_engine_wizard_status_over_socket(self):
        with self.connection() as conn:
            code, kind, body = conn.get_safe_read("/api/v1/wizard/status")
        self.assertEqual(code, 200)
        self.assertIn(b"pending", body)

    def test_deny_arbitrary_paths_and_mutating_operations(self):
        with self.connection() as conn:
            for path in (
                "/api/v1/wizard/start", "/montara/uploads",
                "http://localhost:8101/api/v1/project",
                "/api/v1/project?project=foreign", "/api/v1/../etc/passwd",
                "//api/v1/project",
            ):
                with self.subTest(path=path), self.assertRaises(PermissionError):
                    conn.get_safe_read(path)

    def test_deny_wrong_socket_peer_and_path_symlink(self):
        with self.connection(pid=os.getpid() + 42) as conn:
            with self.assertRaises(PermissionError):
                conn.get_safe_read("/")
        with self.connection(uid=os.getuid() + 42) as conn:
            with self.assertRaises(PermissionError):
                conn.get_safe_read("/")
        symlink = self.directory / "different.sock"
        symlink.symlink_to(self.path)
        with VerifiedJMUnixConnection(
            symlink, expected_pid=os.getpid(), expected_uid=os.getuid()) as conn:
            with self.assertRaises(PermissionError):
                conn.get_safe_read("/")


if __name__ == "__main__":
    unittest.main()
