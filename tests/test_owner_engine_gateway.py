"""A real authenticated session may request only its own bound Engine project.

Fake executor tests the control-plane contract, NOT OS sandboxing or video
rendering. The C8 public beta must continue to reject this operation (404).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from urano.engine_bindings import EngineProjectRegistry
from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api
from urano.owner_engine_gateway import OwnerEngineGateway
from urano.project_catalog import ProjectCatalog
from urano.runtime_activation import RuntimeActivationGuard
from test_google_flow_contract import CLIENT, HOST, CALLBACK, SignedFakeGoogle


class TestExecutor:
    __test__ = False

    def __init__(self, slots):
        self.slots = slots
        self.calls = []
        self.fail = False
        self.abort_fails = False

    def runtime_for_owner(self, owner):
        self.calls.append(("lookup", owner))
        return self.slots.get(owner)

    def open_verified(self, owner, ticket):
        self.calls.append(("open", owner, ticket.project_id, ticket.project_path.name))
        return not self.fail

    def abort(self, owner, runtime_id):
        self.calls.append(("abort", owner, runtime_id))
        if self.abort_fails:
            raise RuntimeError("Isolated process reaping failed")


class OwnerEngineAdmission(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="montara-owner-to-engine-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        private = self.root / 'private';private.mkdir(mode=0o700)
        self.catalog = ProjectCatalog(private / 'projects.sqlite3')
        engine_root = self.root / 'engine';(engine_root / 'Projects').mkdir(parents=True)
        self.bindings = EngineProjectRegistry(private / 'bindings.sqlite3', engine_root, self.catalog)
        self.guard = RuntimeActivationGuard(private / 'runtime.sqlite3', self.catalog, self.bindings)
        self.executor = TestExecutor({})
        self.provider=SignedFakeGoogle()
        settings=OIDCSettings(CLIENT,'synthetic-secret',CALLBACK,
                              frozenset({'alpha@example.test','beta@example.test'}))
        self.app = create_owner_api(private,settings=settings,provider=self.provider,
                                    engine_gateway=OwnerEngineGateway(self.catalog,self.guard,self.executor))
        self.a=self.app.test_client();self.b=self.app.test_client()
        # Owner ids from GoogleOwnerStore are stable UUIDs, not synthetic aliases.
        # Provisioner will be attached to those ids after verified logins.

    def login(self, client, sub, email):
        self.provider.sub,self.provider.email=sub,email
        start=client.get('/urano/v1/google/start',base_url=HOST)
        data={k:v[0] for k,v in parse_qs(urlsplit(start.headers['Location']).query).items()}
        self.provider.nonce=data['nonce']
        self.provider.expected_challenge=data['code_challenge']
        self.provider.code='synthetic-provider-code'
        done=client.get('/urano/v1/google/callback',base_url=HOST,
                        query_string={'code':self.provider.code,'state':data['state']})
        self.assertEqual(done.status_code,303)
        from urano.google_owner import GoogleOwnerStore
        with GoogleOwnerStore(self.root/'private'/'owners.sqlite3')._connect() as db:
            owner=db.execute('SELECT owner_id FROM urano_google_owners WHERE google_sub=?',(sub,)).fetchone()['owner_id']
        return owner

    def csrf(self,client):
        r=client.post('/urano/v1/session/refresh',base_url=HOST,headers={'Origin':HOST})
        self.assertEqual(r.status_code,200)
        return r.json['csrf']

    def project(self, owner, folder):
        result=self.catalog.create(owner,'Owner project')
        place=self.bindings.projects_dir/folder
        place.mkdir();(place/'project.json').write_text(json.dumps({'title':'Stage'}))
        self.bindings.bind_trusted(owner,result.id,folder)
        return result

    def test_google_alpha_opens_own_project_without_paths_from_browser(self):
        owner=self.login(self.a,'sub-a','alpha@example.test')
        runtime=self.guard.register_trusted(owner)
        self.executor.slots[owner]=runtime
        project=self.project(owner,'Alpha-Stage')
        response=self.a.post(f'/urano/v1/projects/{project.id}/open',base_url=HOST,
                             headers={'Origin':HOST,'X-Urano-CSRF':self.csrf(self.a),
                                      'X-Owner-ID':'forged-owner'},
                             content_type='application/octet-stream')
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        self.assertEqual(response.json['state'],'ready')
        self.assertEqual(set(response.json),{'project_id','state','generation'})
        self.assertEqual(self.guard.get_state(owner,runtime)[:2],('ready',project.id))
        self.assertEqual(self.executor.calls[-1],('open',owner,project.id,'Alpha-Stage'))

    def test_second_owner_and_anonymous_cannot_open_first_owners_project(self):
        a_owner=self.login(self.a,'sub-a','alpha@example.test')
        project=self.project(a_owner,'Owner-One')
        b_owner=self.login(self.b,'sub-b','beta@example.test')
        self.executor.slots[a_owner]=self.guard.register_trusted(a_owner)
        self.executor.slots[b_owner]=self.guard.register_trusted(b_owner)
        path=f'/urano/v1/projects/{project.id}/open'
        calls_before=len(self.executor.calls)
        anon=self.app.test_client()
        self.assertEqual(anon.post(path,base_url=HOST,headers={'Origin':HOST}).status_code,401)
        self.assertEqual(self.b.post(path,base_url=HOST,headers={'Origin':HOST,
                            'X-Urano-CSRF':self.csrf(self.b),'X-Owner-ID':a_owner}).status_code,404)
        self.assertEqual(len(self.executor.calls),calls_before)

    def test_requires_csrf_exact_https_origin_and_empty_body(self):
        owner=self.login(self.a,'sub-a','alpha@example.test')
        self.executor.slots[owner]=self.guard.register_trusted(owner)
        project=self.project(owner,'Only-One')
        path=f'/urano/v1/projects/{project.id}/open'
        self.assertEqual(self.a.post(path,base_url=HOST,headers={'Origin':HOST}).status_code,403)
        self.assertEqual(self.a.post(path,base_url=HOST,headers={'Origin':'https://attacker.test',
            'X-Urano-CSRF':self.csrf(self.a)}).status_code,403)
        self.assertEqual(self.a.post(path,base_url='http://bad.test',headers={'Origin':HOST,
            'X-Urano-CSRF':self.csrf(self.a)}).status_code,403)
        self.assertEqual(self.a.post(path,base_url=HOST,headers={'Origin':HOST,
            'X-Urano-CSRF':self.csrf(self.a)},data=b'{"path":"/etc"}').status_code,400)
        self.assertFalse(any(call[0]=='open' for call in self.executor.calls))

    def test_executor_missing_and_failing_open_never_returns_ready(self):
        owner=self.login(self.a,'sub-a','alpha@example.test')
        project=self.project(owner,'Recovery')
        path=f'/urano/v1/projects/{project.id}/open'
        csrf=self.csrf(self.a)
        def open_request():
            return self.a.post(path,base_url=HOST,headers={'Origin':HOST,'X-Urano-CSRF':csrf})
        self.assertEqual(open_request().status_code,503)
        runtime=self.guard.register_trusted(owner)
        self.executor.slots[owner]=runtime
        self.executor.fail=True
        self.assertEqual(open_request().status_code,503)
        self.assertEqual(self.guard.get_state(owner,runtime)[:2],('idle',None))
        self.assertTrue(any(call[0]=='abort' for call in self.executor.calls))
        self.executor.abort_fails=True
        self.assertEqual(open_request().status_code,503)
        self.assertEqual(self.guard.get_state(owner,runtime)[0],'switching')
        self.assertEqual(open_request().status_code,409)

    def test_no_implicit_worker_in_c8_no_engine_http(self):
        from urano.owner_beta_wsgi import create_private_owner_beta
        private=self.root/'real-c8';private.mkdir(mode=0o700)
        secret=self.root/'fake-key';secret.write_text('fake-key');secret.chmod(0o600)
        cfg={'MONTARA_BETA_ORIGIN':HOST,'MONTARA_COMPANION_BETA_ORIGIN':HOST,
             'MONTARA_GOOGLE_CLIENT_ID':'123456-synthetic.apps.googleusercontent.com',
             'MONTARA_BETA_ALLOWED_EMAILS':'alpha@example.test',
             'MONTARA_GOOGLE_SECRET_FILE':str(secret),
             'MONTARA_OWNER_PRIVATE_DIR':str(private)}
        real=create_private_owner_beta(cfg,provider=self.provider)
        code=real.test_client().post('/urano/v1/projects/'+self.catalog.create('someowner','X').id+'/open',base_url=HOST).status_code
        self.assertEqual(code,404)

if __name__=='__main__':unittest.main()
