"""One original Chema worker lifecycle, without broker or browser substitutes.

These tests exercise the real filesystem-backed Unix socket permissions and
readiness order. They do not run a second GCP worker or touch live Owner data.
"""
from __future__ import annotations

import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from urano.native_owner_worker_service import (
    NativeOwnerSocketUnavailable, serve_native_owner_workspace,
)

WORKSPACE="8044210a-c74e-4f0c-8d49-90d1d2eaf7c2"


class NativeOwnerWorkerServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="montara-native-sockets-")
        self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name)
        self.data=base/"private"
        self.runtime=base/"run"
        self.data.mkdir(mode=0o700)
        self.runtime.mkdir(mode=0o700)
        self.stop=threading.Event()
        self.addCleanup(self.stop.set)
        self.calls=[]
        self.reads=[]

    def factory(self, data_root: Path, *, samples: bool):
        self.calls.append(("factory", data_root, samples))
        app=Flask(__name__)
        app.config["ZUCKER_STATE"]=SimpleNamespace(project=None)
        return app

    def socket_server(self, app, directory: Path, *, mode=0o600):
        self.calls.append(("server", directory))
        location=directory/"jm-editor-http.sock"
        sock=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(location))
        os.chmod(location,mode)
        sock.listen(2)

        class Server:
            def serve_forever(s):
                self.calls.append(("serve",))
                self.stop.set()
            def server_close(s):
                self.calls.append(("close",))
                sock.close()

        return Server(),location

    def status_server(self, directory: Path, *, project_id: str,
                      generation: int, read_snapshot, trusted_broker_uid: int,
                      on_listening):
        self.calls.append(("status", project_id, generation, trusted_broker_uid))
        self.reads.append(read_snapshot())
        path=directory/"stage-read.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.bind(str(path))
            os.chmod(path,0o600)
            sock.listen(2)
            on_listening()
            self.stop.wait(timeout=5)
        path.unlink(missing_ok=True)

    def run_worker(self, **overrides):
        kwargs=dict(app_factory=self.factory,data_root=self.data,
                    runtime_root=self.runtime,workspace_id=WORKSPACE,
                    generation=1,make_private_server=self.socket_server,
                    serve_stage_socket=self.status_server,
                    on_ready=lambda:self.calls.append(("ready",)),
                    ready_timeout=2)
        kwargs.update(overrides)
        return serve_native_owner_workspace(**kwargs)

    def test_real_private_socket_and_stage_listener_ready_before_announcing(self):
        self.run_worker()
        events=[c[0] for c in self.calls]
        self.assertEqual(events,["factory","server","status","ready","serve","close"])
        self.assertEqual(self.calls[2],("status",WORKSPACE,1,0))
        self.assertEqual(self.reads[0]["project"],WORKSPACE)
        self.assertEqual(self.reads[0]["camera_count"],0)
        self.assertFalse((self.runtime/"jm-editor-http.sock").exists())
        self.assertEqual(list(self.data.iterdir()),[])

    def test_cooperative_stop_drains_before_socket_close(self):
        shutdown = threading.Event()
        serving = threading.Event()
        closed = threading.Event()
        gate = threading.Event()

        def graceful_server(app, directory):
            original, path = self.socket_server(app, directory)
            class Server:
                def serve_forever(self):
                    serving.set()
                    gate.wait(timeout=2)
                def shutdown(self):
                    gate.set()
                def server_close(self):
                    self_test.assertTrue(gate.is_set())
                    closed.set()
                    original.server_close()
            self_test = self
            return Server(), path

        def send_shutdown():
            self.assertTrue(serving.wait(timeout=2))
            shutdown.set()
        trigger = threading.Thread(target=send_shutdown)
        trigger.start()
        try:
            self.run_worker(make_private_server=graceful_server,
                            shutdown_event=shutdown)
        finally:
            gate.set()
            self.stop.set()
            trigger.join(timeout=2)
        self.assertTrue(closed.is_set())
        self.assertFalse((self.runtime/"jm-editor-http.sock").exists())

    def test_rejects_runtime_permission_before_app_factory(self):
        self.runtime.chmod(0o755)
        with self.assertRaises(NativeOwnerSocketUnavailable):
            self.run_worker()
        self.assertEqual(self.calls,[])

    def test_rejects_invalid_worker_generation_before_app_factory(self):
        for bad in (0,-1,True,"2"):
            with self.subTest(generation=bad):
                with self.assertRaises(NativeOwnerSocketUnavailable):
                    self.run_worker(generation=bad)
        self.assertEqual(self.calls,[])

    def test_missing_status_socket_prevents_ready(self):
        def missing(directory, *, project_id, generation, read_snapshot,
                    trusted_broker_uid, on_listening):
            on_listening()
            self.stop.wait(timeout=3)
        with self.assertRaises(NativeOwnerSocketUnavailable):
            self.run_worker(serve_stage_socket=missing)
        self.assertNotIn(("ready",),self.calls)
        self.stop.set()

    def test_status_exception_prevents_ready(self):
        def failure(*args, **kwargs):
            raise RuntimeError("status listener unavailable")
        with self.assertRaises(NativeOwnerSocketUnavailable):
            self.run_worker(serve_stage_socket=failure)
        self.assertNotIn(("ready",),self.calls)

    def test_world_readable_jm_socket_prevents_ready(self):
        def open_socket(app, directory):
            return self.socket_server(app,directory,mode=0o666)
        with self.assertRaises(NativeOwnerSocketUnavailable):
            self.run_worker(make_private_server=open_socket)
        self.assertNotIn(("ready",),self.calls)


if __name__=="__main__":
    unittest.main()
