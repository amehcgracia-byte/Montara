"""I48 real HTTP traffic over broker-issued Unix socket descriptor."""
import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from flask import Flask, jsonify, request
from urano.owner_private_http_client import authenticated_private_jm_connection
from urano.private_editor_fd_handoff import EditorFdLease, send_editor_fd
from urano.private_jm_wsgi_socket import create_private_jm_wsgi_server

PROJECT="7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"


class OwnerPrivateHTTPStreamingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.root.chmod(0o700)
        app=Flask("JM-worker-stream")
        @app.get("/")
        def index():
            return "<html>Original JM</html>"
        @app.post("/api/v1/wizard/upload")
        def upload():
            return jsonify(bytes=len(request.get_data()))
        self.worker,self.path=create_private_jm_wsgi_server(app,self.root)
        self.worker_thread=threading.Thread(target=self.worker.serve_forever,daemon=True)
        self.worker_thread.start()
        self.addCleanup(self.stop_worker)

    def stop_worker(self):
        self.worker.shutdown()
        self.worker.server_close()
        self.worker_thread.join(timeout=3)
        self.path.unlink(missing_ok=True)

    def start_broker(self,*,response_generation=3):
        broker_path=self.root/"broker-control.sock"
        broker_path.unlink(missing_ok=True)
        ready=threading.Event()
        packets=[]
        def serve():
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
                listener.bind(str(broker_path))
                listener.listen(1)
                ready.set()
                control,_=listener.accept()
                with control:
                    packet=json.loads(control.recv(384))
                    packets.append(packet)
                    connection=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                    connection.connect(str(self.path))
                    send_editor_fd(control,EditorFdLease(
                        PROJECT,response_generation,connection))
        thread=threading.Thread(target=serve,daemon=True)
        thread.start()
        self.assertTrue(ready.wait(5))
        return broker_path,packets,thread

    def test_real_http_media_stream_bypasses_control_socket(self):
        control,packets,thread=self.start_broker()
        http=authenticated_private_jm_connection(
            "s"*64,"c"*64,PROJECT,3,control_socket=control,
            broker_uid=os.getuid())
        self.addCleanup(http.close)
        http.request("GET","/")
        response=http.getresponse()
        self.assertEqual(response.status,200)
        self.assertIn(b"Original JM",response.read())
        http.close()
        thread.join(timeout=2)
        control,packets,thread=self.start_broker()
        stream=authenticated_private_jm_connection(
            "s"*64,"c"*64,PROJECT,3,control_socket=control,
            broker_uid=os.getuid())
        self.addCleanup(stream.close)
        media=b"proxy"*300000
        stream.request("POST","/api/v1/wizard/upload",
                       body=media,headers={"Content-Type":"application/octet-stream",
                                           "X-Zucker-Filename":"proxy.small.mp4"})
        reply=stream.getresponse()
        self.assertEqual(reply.status,200)
        self.assertEqual(json.loads(reply.read())["bytes"],len(media))
        self.assertEqual(len(packets),1)
        self.assertEqual(set(packets[0]),{
            "op","session","csrf","project_id","generation"})
        self.assertLess(len(json.dumps(packets[0])),384)
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def test_generation_mismatch_denied(self):
        control,_,thread=self.start_broker(response_generation=4)
        from urano.private_engine_route_contract import PrivateEngineRouteDenied
        with self.assertRaises(PrivateEngineRouteDenied):
            authenticated_private_jm_connection(
                "s"*64,"c"*64,PROJECT,3,control_socket=control,
                broker_uid=os.getuid())
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())


if __name__=="__main__":
    unittest.main()
