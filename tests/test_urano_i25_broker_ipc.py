"""I25: exact Unix peer credential and fail-closed stop dispatch."""
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urano.job_recovery_ledger import JobRecoveryLedger,StaleJob
from urano.restricted_broker_ipc import authenticate_peer,parse_stop,stop_authenticated,UntrustedPeer
from urano.restricted_systemd_broker import RestrictedTargetControl,expected_cgroup,UnverifiedTarget

class FakeOS:
    def __init__(self):self.calls=[];self.alive=True
    def show(self,unit):
        self.calls.append(("show",unit))
        return {"ActiveState":"active" if self.alive else "inactive",
                "ControlGroup":expected_cgroup(unit)}
    def stop_exact(self,unit):
        self.calls.append(("stop",unit));self.alive=False

class IPCContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db=JobRecoveryLedger(Path(temp.name)/"jobs.sqlite")
        self.job=self.db.start_trusted("owner-a","project-a")
        self.db.reserve_target_unit(self.job)
        self.os=FakeOS()
        self.ctrl=RestrictedTargetControl(self.db,self.os)
        self.a,self.b=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)
        self.valid=json.dumps({"op":"stop","job_id":self.job.job_id,
                               "generation":self.job.generation}).encode()
    def test_local_peer_credential_validated_by_kernel(self):
        authenticate_peer(self.a,trusted_uid=os.getuid(),web_uid=os.getuid()+10000)
        with self.assertRaises(UntrustedPeer):
            authenticate_peer(self.a,trusted_uid=os.getuid()+1,web_uid=os.getuid()+10000)
        with self.assertRaises(ValueError):
            authenticate_peer(self.a,trusted_uid=os.getuid(),web_uid=os.getuid())
    def test_payload_cannot_choose_owner_unit_path_uid_or_command(self):
        for message in (
            {"op":"stop","job_id":self.job.job_id,"generation":1,"unit":"montara-owner-beta"},
            {"op":"launch","job_id":self.job.job_id,"generation":1},
            {"op":"stop","job_id":self.job.job_id,"generation":True},
            {"op":"stop","job_id":"/system.slice/owner.service","generation":1},
            {"op":"stop","job_id":self.job.job_id,"generation":0},
        ):
            with self.subTest(message=message),self.assertRaises(ValueError):
                parse_stop(json.dumps(message).encode())
        with self.assertRaises(ValueError):parse_stop(b"x"*257)
    def test_unauthorized_peer_never_touches_ledger_or_os(self):
        with self.assertRaises(UntrustedPeer):
            stop_authenticated(self.a,self.valid,trusted_uid=os.getuid()+1,
                web_uid=os.getuid()+10000,ledger=self.db,controller=self.ctrl)
        self.assertEqual(self.db.get_trusted(self.job.job_id).state,"starting")
        self.assertEqual(self.os.calls,[])
    def test_authenticated_stop_attests_and_releases(self):
        with patch("pathlib.Path.read_text",side_effect=FileNotFoundError):
            self.assertTrue(stop_authenticated(self.a,self.valid,trusted_uid=os.getuid(),
                web_uid=os.getuid()+10000,ledger=self.db,controller=self.ctrl))
        self.assertEqual(self.db.get_trusted(self.job.job_id).state,"stopped")
        self.assertEqual([x[0] for x in self.os.calls].count("stop"),1)
        with self.assertRaises(StaleJob):
            stop_authenticated(self.a,self.valid,trusted_uid=os.getuid(),
                web_uid=os.getuid()+10000,ledger=self.db,controller=self.ctrl)
    def test_failed_cleanup_stays_fenced(self):
        with patch("pathlib.Path.read_text",return_value="123\n"):
            with self.assertRaises(UnverifiedTarget):
                stop_authenticated(self.a,self.valid,trusted_uid=os.getuid(),
                    web_uid=os.getuid()+10000,ledger=self.db,controller=self.ctrl)
        self.assertEqual(self.db.get_trusted(self.job.job_id).state,"stopping")

if __name__=="__main__":unittest.main()

