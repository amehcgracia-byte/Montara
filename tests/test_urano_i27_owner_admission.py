"""I27 exact Google-owner session, CSRF, catalog and Unix peer proof."""
from __future__ import annotations
import json
import os
import socket
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock

from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore
from urano.private_owner_admission import (
    OwnerAdmissionDenied,parse_owner_request,verify_owner_and_project
)
from urano.private_broker_service import dispatch_owner


class OwnerAdmissionContract(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="montara-i27-")
        self.addCleanup(temp.cleanup)
        self.dir=Path(temp.name)
        self.sessions=SessionStore(self.dir/"sessions.sqlite3")
        self.projects=ProjectCatalog(self.dir/"projects.sqlite3")
        self.owner="google-owner-a"
        self.another="google-owner-b"
        self.project=self.projects.create(self.owner,"Project for A")
        self.foreign=self.projects.create(self.another,"Project for B")
        self.session=self.sessions.issue(self.owner,ttl_seconds=900)
        self.a,self.b=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def packet(self,op="open_owner",project_id=None,session=None,csrf=None,**extra):
        return json.dumps({"op":op,"project_id":project_id or self.project.id,
            "session":session or self.session.token,"csrf":csrf or self.session.csrf,
            **extra},separators=(",",":")).encode()

    def test_real_session_and_catalog_positive(self):
        self.assertEqual(
            verify_owner_and_project(self.packet(),owner_db_root=self.dir),
            ("open_owner",self.owner,self.project.id))

    def test_foreign_project_denied(self):
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(self.packet(project_id=self.foreign.id),
                                     owner_db_root=self.dir)

    def test_revoked_session_denied(self):
        self.sessions.revoke(self.session.token)
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(self.packet(),owner_db_root=self.dir)

    def test_wrong_csrf_denied(self):
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(self.packet(csrf="a"*64),owner_db_root=self.dir)

    def test_unknown_or_arbitrary_parameters_rejected(self):
        for field in (
            {"owner_id":self.another},{"unit":"montara-owner-beta.service"},
            {"runtime_id":"root"},{"folder":"/etc/shadow"},{"command":"bash"},
        ):
            with self.subTest(field=field),self.assertRaises(ValueError):
                parse_owner_request(self.packet(**field))
        with self.assertRaises(ValueError):parse_owner_request(b"x"*385)

    def test_authenticated_kernel_peer_owns_exact_project(self):
        broker=Mock()
        broker.demo_start.return_value={"ok":True,"generation":5}
        self.b.sendall(self.packet())
        result=dispatch_owner(self.a,os.getuid(),self.dir,broker)
        self.assertEqual(result,{"ok":True,"project_id":self.project.id,
                                 "state":"ready","generation":5})
        broker.demo_start.assert_called_once_with(self.owner,self.project.id)

    def test_untrusted_peer_denied_before_parsing(self):
        self.b.sendall(self.packet())
        broker=Mock()
        with self.assertRaises(PermissionError):
            dispatch_owner(self.a,os.getuid()+1,self.dir,broker)
        broker.demo_start.assert_not_called()

    def test_close_rechecks_project(self):
        broker=Mock()
        broker.stop_owner.return_value={"ok":True,"state":"stopped"}
        self.b.sendall(self.packet(op="close_owner"))
        self.assertEqual(dispatch_owner(self.a,os.getuid(),self.dir,broker),
                         {"ok":True,"state":"stopped"})
        broker.stop_owner.assert_called_once_with(self.owner,self.project.id)


if __name__=="__main__":
    unittest.main()

