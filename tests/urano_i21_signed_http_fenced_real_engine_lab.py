"""Opt-in I21: fake signed Google HTTP → I13 → I19/I18 → real Engine.

Uses the I20 rootless/cgroup process launcher ONLY on this operator-controlled
synthetic test. The host UID is not isolated between tenants: not production.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.gateway_job_bridge import GatewayJobBridge
from urano.google_flow import OIDCSettings
from urano.google_owner import GoogleOwnerStore
from urano.job_recovery_ledger import JobRecoveryLedger
from urano.minimal_owner_api import create_owner_api
from urano.owner_engine_gateway import OwnerEngineGateway
from urano.project_catalog import ProjectCatalog
from urano.runtime_activation import RuntimeActivationGuard
from urano.trusted_job_admission import TrustedJobAdmission
from test_google_flow_contract import CLIENT, HOST, CALLBACK, SignedFakeGoogle
from urano_i20_oidc_to_real_engine_lab import CgroupLabExecutor,verified_fake_login


class RealLabTransport:
    def __init__(self, executor):self.executor=executor
    def open_verified(self,owner,ticket):
        return self.executor.open_verified(owner,ticket)
    def stop_verified(self,owner,ticket):
        self.executor.abort(owner,ticket.runtime_id)
        return True


def main(repo,engine,venv):
    pinned=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD:engine'],text=True).strip()
    sha=subprocess.check_output(['git','-C',str(engine),'rev-parse','HEAD'],text=True).strip()
    if sha!=pinned:raise RuntimeError('Real Engine pin mismatch')
    start=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='montara-i21-owner.',dir='/tmp') as data, \
         tempfile.TemporaryDirectory(prefix='montara-i15-workspace.',dir='/tmp') as work:
        root=Path(data);workspace=Path(work)
        catalog=ProjectCatalog(root/'projects.sqlite3')
        (workspace/'Projects').mkdir()
        bindings=EngineProjectRegistry(root/'bindings.sqlite3',workspace,catalog)
        guard=RuntimeActivationGuard(root/'runtime.sqlite3',catalog,bindings)
        ledger=JobRecoveryLedger(root/'jobs.sqlite3')
        physical=CgroupLabExecutor(guard,repo,engine,venv,workspace)
        bridge=GatewayJobBridge.prepare(guard,lambda broker:TrustedJobAdmission(catalog,ledger,broker),
            RealLabTransport(physical),lambda owner:physical.slots.get(owner))
        if bridge.startup_orphans:raise RuntimeError('Fresh test must not have orphans')
        google=SignedFakeGoogle()
        api=create_owner_api(root,settings=OIDCSettings(CLIENT,'synthetic-signing-only',CALLBACK,
                frozenset({'alpha@example.test','beta@example.test'})),provider=google,
                engine_gateway=OwnerEngineGateway(catalog,guard,bridge))
        a=api.test_client();b=api.test_client();owners=GoogleOwnerStore(root/'owners.sqlite3')
        owner=verified_fake_login(a,google,owners,sub='i21-alpha',email='alpha@example.test')
        foreign=verified_fake_login(b,google,owners,sub='i21-beta',email='beta@example.test')
        assert owner!=foreign
        runtime=guard.register_trusted(owner);physical.slots[owner]=runtime
        sys.path.insert(0,str(engine))
        try:
            from core.project import new_project_document
            folder=workspace/'Projects'/'I21-Real'
            folder.mkdir()
            (folder/'project.json').write_text(json.dumps(new_project_document('I21-Real')))
        finally:sys.path.remove(str(engine))
        project=catalog.create(owner,'I21 real engine fenced HTTP')
        bindings.bind_trusted(owner,project.id,'I21-Real')
        path='/urano/v1/projects/'+project.id+'/open'
        a_csrf=a.post('/urano/v1/session/refresh',base_url=HOST,headers={'Origin':HOST}).json['csrf']
        b_csrf=b.post('/urano/v1/session/refresh',base_url=HOST,headers={'Origin':HOST}).json['csrf']
        rejected=b.post(path,base_url=HOST,headers={'Origin':HOST,'X-Urano-CSRF':b_csrf})
        assert rejected.status_code==404
        result={'two_signed_fake_google_identities':True,'foreign_owner_http_404':True,
                'real_engine_open':False,'job_fenced_persistently':False,
                'clean_stop':False,'per_tenant_host_uid_verified':False,
                'public_beta_modified':False,'companion_tested':False,
                'mp4_export_tested':False,'pinned_engine':pinned}
        try:
            opened=a.post(path,base_url=HOST,headers={'Origin':HOST,'X-Urano-CSRF':a_csrf,
                                                        'X-Owner-ID':foreign})
            if opened.status_code!=200:
                raise RuntimeError('Fenced real Engine open failed: '+str(opened.status_code))
            result['real_engine_open']=(opened.json.get('state')=='ready')
            job=bridge._jobs[owner]
            result['job_fenced_persistently']=(ledger.get_trusted(job.job_id).state=='running')
            result['engine_ready_after_http']=guard.get_state(owner,runtime)[0]=='ready'
            result['open_seconds']=round(time.monotonic()-start,3)
        finally:
            if owner in bridge._jobs:
                bridge.close_trusted(owner,runtime)
        result['clean_stop']=(not physical.active and
            ledger.get_trusted(job.job_id).state=='stopped' and
            guard.get_state(owner,runtime)[0]=='idle')
        result['duration_seconds']=round(time.monotonic()-start,3)
        if not all(result[key] for key in ('real_engine_open','job_fenced_persistently',
                    'engine_ready_after_http','clean_stop')):
            raise RuntimeError('Fenced Engine contract failed')
        print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: ENGINE_DIR VENV_DIR')
    main(Path(__file__).resolve().parents[1],Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
