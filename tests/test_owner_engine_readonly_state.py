"""Authoritative, read-only Engine state: identity, project names and no side effects."""
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from flask import Flask

from urano.job_recovery_ledger import JobLease
from urano.owner_broker_preview import owner_engine_preview_blueprint
from urano.private_broker_service import DemoBroker, dispatch_owner
from urano.private_owner_admission import verify_owner_and_project
from urano.project_catalog import ProjectCatalog
from urano.restricted_systemd_broker import expected_cgroup
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN="https://montara-owner.example.test"


class PrivateOwnerEngineStateTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="montara-owner-engine-readonly-")
        self.addCleanup(t.cleanup)
        root=Path(t.name)
        self.catalog=ProjectCatalog(root/"projects.sqlite3")
        self.sessions=SessionStore(root/"sessions.sqlite3")
        self.owner="owner-a"
        recipe={"montara_beta_workspace":{"version":1,"mode":"stage"}}
        self.a=self.catalog.create(self.owner,"Guitar Stage",recipe=recipe)
        self.b=self.catalog.create(self.owner,"Second Stage",recipe=recipe)
        self.foreign=self.catalog.create("owner-b","Foreign",recipe=recipe)
        self.auth=self.sessions.issue(self.owner)
        self.app=Flask(__name__)
        self.app.register_blueprint(owner_engine_preview_blueprint(
            self.catalog,self.sessions,https_origin=ORIGIN))
        self.client=self.app.test_client()
        self.client.set_cookie(SESSION_COOKIE,self.auth.token,
                               domain="montara-owner.example.test")
        self.url=f"/urano/v1/projects/{self.b.id}/engine-state"
        self.headers={"X-Urano-CSRF":self.auth.csrf}

    def read(self,path=None,headers=None):
        return self.client.get(path or self.url,headers=headers or self.headers,
                               base_url=ORIGIN)

    def test_other_owned_stage_is_identified_without_switching_worker(self):
        with patch("urano.owner_broker_preview.broker_request",return_value={
            "ok":True,"state":"on","active_project_id":self.a.id}) as broker:
            response=self.read()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,{"state":"on","active_project":{
            "id":self.a.id,"title":"Guitar Stage"}})
        self.assertEqual(response.headers["Cache-Control"],"private, no-store")
        broker.assert_called_once_with("status_owner",self.auth.token,
                                       self.auth.csrf,self.b.id)

    def test_off_and_unverified_are_not_mislabeled_green(self):
        for state,active in (("off",None),("unknown",None),
                             ("unknown",self.a.id)):
            with self.subTest(state=state,active=active),patch(
                "urano.owner_broker_preview.broker_request",return_value={
                "ok":True,"state":state,"active_project_id":active}):
                r=self.read()
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.json["state"],state)

    def test_unauthorized_foreign_active_project_not_disclosed(self):
        with patch("urano.owner_broker_preview.broker_request",return_value={
            "ok":True,"state":"on","active_project_id":self.foreign.id}):
            result=self.read()
        self.assertEqual(result.status_code,503)
        self.assertNotIn(self.foreign.title,result.get_data(as_text=True))

    def test_fails_closed_on_invalid_state(self):
        for value in ({"ok":True,"state":"on","active_project_id":None},
                      {"ok":True,"state":"off","active_project_id":self.a.id},
                      {"ok":False,"state":"off"},
                      {"ok":True,"state":"ready"}):
            with self.subTest(value=value),patch(
                    "urano.owner_broker_preview.broker_request",
                    return_value=value):
                self.assertEqual(self.read().status_code,503)

    def test_read_requires_csrf_cookie_and_owner(self):
        with patch("urano.owner_broker_preview.broker_request") as broker:
            self.assertEqual(self.read(headers={"X-Urano-CSRF":"a"*64}).status_code,403)
            self.assertEqual(self.read(
                f"/urano/v1/projects/{self.foreign.id}/engine-state").status_code,404)
            self.sessions.revoke(self.auth.token)
            self.assertEqual(self.read().status_code,401)
        broker.assert_not_called()

    def test_broker_status_operation_is_authenticated_and_readonly(self):
        frame=json.dumps({"op":"status_owner","project_id":self.b.id,
            "session":self.auth.token,"csrf":self.auth.csrf},
            separators=(",",":")).encode()
        root=self.catalog.db_path.parent
        self.assertEqual(verify_owner_and_project(frame,owner_db_root=root),
                         ("status_owner",self.owner,self.b.id))
        server,client=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(server.close);self.addCleanup(client.close)
        broker=Mock()
        broker.owner_engine_status.return_value={
            "ok":True,"state":"on","active_project_id":self.a.id}
        client.sendall(frame)
        result=dispatch_owner(server,os.getuid(),root,broker)
        self.assertEqual(result["active_project_id"],self.a.id)
        broker.owner_engine_status.assert_called_once_with(self.owner)
        broker.demo_start.assert_not_called()
        broker.stop_owner.assert_not_called()

    def test_status_does_not_start_stop_or_modify_ledger(self):
        b=object.__new__(DemoBroker)
        b.ledger=Mock()
        b.control=Mock()
        b.ledger.unverified_for_owner.return_value=()
        self.assertEqual(b.owner_engine_status(self.owner),{
            "ok":True,"state":"off","active_project_id":None})
        b.ledger.start_trusted.assert_not_called()
        b.control.stop_verified.assert_not_called()
        b.ledger.unverified_for_owner.return_value=(JobLease(
            self.owner,self.a.id,"job-"+"a"*32,3,"orphaned"),)
        self.assertEqual(b.owner_engine_status(self.owner)["state"],"unknown")
        b.ledger.start_trusted.assert_not_called()
        b.control.stop_verified.assert_not_called()

    def test_running_requires_systemd_and_ready_file(self):
        b=object.__new__(DemoBroker)
        b.ledger=Mock()
        b.control=Mock()
        lease=JobLease(self.owner,self.a.id,"job-"+"a"*32,3,"running")
        unit="montara-i24-job-"+"a"*32
        b.ledger.unverified_for_owner.return_value=(lease,)
        b.ledger.target_for_trusted.return_value=unit
        b.control.systemd.show.return_value={
            "ActiveState":"active",
            "MainPID":"3456",
            "ControlGroup":expected_cgroup(unit)
        }
        with patch.object(Path,"read_text",return_value=json.dumps({
            "ready":True,"folder":self.a.id,"uid":1001})):
            self.assertEqual(b.owner_engine_status(self.owner),{
                "ok":True,"state":"on","active_project_id":self.a.id})
        b.control.systemd.show.return_value["ActiveState"]="inactive"
        self.assertEqual(b.owner_engine_status(self.owner)["state"],"unknown")
        b.control.stop_verified.assert_not_called()


if __name__=="__main__":
    unittest.main()
