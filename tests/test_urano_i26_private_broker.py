"""I26 contracts: the private socket only accepts exact authenticated operations.

Runs without root, sudo, systemd, Google or network.
"""
import json
import os
import socket
import unittest
from unittest.mock import Mock

from urano.private_broker_service import dispatch
from urano.restricted_broker_ipc import UntrustedPeer


class I26PrivateBrokerContracts(unittest.TestCase):
    def setUp(self):
        self.server,self.client=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(self.server.close)
        self.addCleanup(self.client.close)
        self.fake=Mock()
        self.fake.demo_start.return_value={"ok":True,"engine_opened":True}
        self.fake.stop.return_value={"ok":True,"state":"stopped"}

    def call(self, value, *, uid=None):
        payload=json.dumps(value,separators=(",",":")).encode()
        self.client.sendall(payload)
        return dispatch(self.server,os.getuid() if uid is None else uid,
                        os.getuid()+999,self.fake)

    def test_ping_is_only_local_and_authenticated(self):
        self.assertEqual(self.call({"op":"ping"})["mode"],"lab")
        self.fake.assert_not_called()

    def test_real_unix_credential_mismatch_denies_before_dispatch(self):
        self.client.sendall(b'{"op":"demo_start"}')
        with self.assertRaises(UntrustedPeer):
            dispatch(self.server,os.getuid()+1000,os.getuid()+1001,self.fake)
        self.fake.demo_start.assert_not_called()

    def test_synthetic_start_requires_exact_schema(self):
        self.assertTrue(self.call({"op":"demo_start"})["engine_opened"])
        self.fake.demo_start.assert_called_once()
        for obj in ({"op":"demo_start","owner":"other"},
                    {"op":"launch","unit":"montara-owner-beta"},
                    {"op":"ping","path":"/etc/shadow"},
                    {"op":"stop","unit":"montara-owner-beta.service"}):
            with self.subTest(obj=obj):
                self.client.sendall(json.dumps(obj).encode())
                with self.assertRaises(ValueError):
                    dispatch(self.server,os.getuid(),os.getuid()+999,self.fake)

    def test_stop_can_only_delegate_strict_lease_to_i25(self):
        payload={"op":"stop","job_id":"job-"+("a"*32),"generation":7}
        self.assertEqual(self.call(payload)["state"],"stopped")
        self.fake.stop.assert_called_once()
        forwarded=self.fake.stop.call_args.args[0]
        self.assertEqual(json.loads(forwarded),payload)

    def test_invalid_frames_rejected(self):
        self.client.sendall(b"x"*513)
        with self.assertRaises(ValueError):
            dispatch(self.server,os.getuid(),os.getuid()+999,self.fake)

if __name__=="__main__":
    unittest.main()

