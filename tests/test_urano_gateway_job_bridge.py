"""I21: existing I13 and I19 states coordinate without public Engine exposure."""
import tempfile
import unittest
from pathlib import Path

from urano.engine_bindings import EngineProjectRegistry
from urano.job_recovery_ledger import BusyOwner, JobRecoveryLedger
from urano.owner_engine_gateway import OwnerEngineGateway
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.runtime_activation import RuntimeActivationGuard
from urano.trusted_job_admission import TrustedJobAdmission
from urano.gateway_job_bridge import GatewayJobBridge


class FakeOS:
    def __init__(self):
        self.calls=[];self.open_ok=True;self.stop_ok=True
    def open_verified(self,owner,ticket):
        self.calls.append(('open',owner,ticket.project_id))
        return self.open_ok
    def stop_verified(self,owner,ticket):
        self.calls.append(('stop',owner,ticket.project_id))
        return self.stop_ok


class BridgeContract(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='montara-i21-')
        self.addCleanup(tmp.cleanup)
        base=Path(tmp.name)
        self.catalog=ProjectCatalog(base/'projects.sqlite3')
        engine=base/'Engine';(engine/'Projects').mkdir(parents=True)
        self.bindings=EngineProjectRegistry(base/'bindings.sqlite3',engine,self.catalog)
        self.guard=RuntimeActivationGuard(base/'slots.sqlite3',self.catalog,self.bindings)
        self.ledger=JobRecoveryLedger(base/'jobs.sqlite3')
        self.transport=FakeOS();self.slots={}
        self.bridge=GatewayJobBridge.prepare(self.guard,
            lambda broker:TrustedJobAdmission(self.catalog,self.ledger,broker),
            self.transport,lambda owner:self.slots.get(owner))
        self.gateway=OwnerEngineGateway(self.catalog,self.guard,self.bridge)
        self.a=self.project('alice','AliceFolder')
        self.b=self.project('bob','BobFolder')

    def project(self,owner,folder):
        project=self.catalog.create(owner,folder)
        dir=self.bindings.projects_dir/folder;dir.mkdir()
        (dir/'project.json').write_text('{"title":"synthetic"}')
        self.bindings.bind_trusted(owner,project.id,folder)
        self.slots[owner]=self.guard.register_trusted(owner)
        return project

    def test_open_binds_legacy_guard_and_durable_ledger_then_close(self):
        result=self.gateway.open_verified_owner_project('alice',self.a.id)
        self.assertEqual(result.state,'ready')
        self.assertEqual(self.guard.get_state('alice',self.slots['alice'])[:2],('ready',self.a.id))
        self.assertEqual(self.ledger.get_trusted(self.bridge._jobs['alice'].job_id).state,'running')
        job_id=self.bridge._jobs['alice'].job_id
        self.bridge.close_trusted('alice',self.slots['alice'])
        self.assertEqual(self.guard.get_state('alice',self.slots['alice'])[0],'idle')
        self.assertEqual(self.ledger.get_trusted(job_id).state,'stopped')
        self.assertEqual(self.transport.calls[0][0],'open')
        self.assertEqual(self.transport.calls[1][0],'stop')

    def test_second_open_cannot_destroy_existing_ready_engine(self):
        first=self.gateway.open_verified_owner_project('alice',self.a.id)
        from urano.owner_engine_gateway import ExecutorUnavailable
        with self.assertRaises(ExecutorUnavailable):
            self.gateway.open_verified_owner_project('alice',self.a.id)
        self.assertEqual(self.guard.get_state('alice',self.slots['alice'])[:2],('ready',self.a.id))
        self.assertEqual(self.ledger.get_trusted(self.bridge._jobs['alice'].job_id).state,'running')
        self.assertEqual([call[0] for call in self.transport.calls],['open'])
        self.bridge.close_trusted('alice',self.slots['alice'])

    def test_foreign_project_rejected_before_os_or_reservation(self):
        with self.assertRaises(ProjectNotFound):
            self.gateway.open_verified_owner_project('alice',self.b.id)
        self.assertEqual(self.transport.calls,[])

    def test_no_verified_cleanup_keeps_both_gates_closed(self):
        self.transport.open_ok=False;self.transport.stop_ok=False
        from urano.owner_engine_gateway import ExecutorUnavailable
        with self.assertRaises(ExecutorUnavailable):
            self.gateway.open_verified_owner_project('alice',self.a.id)
        self.assertEqual(self.guard.get_state('alice',self.slots['alice'])[0],'switching')
        with self.assertRaises(Exception):
            self.gateway.open_verified_owner_project('alice',self.a.id)
        with self.ledger._connect() as db:
            self.assertEqual(db.execute("SELECT state FROM urano_engine_jobs WHERE owner_id='alice'").fetchone()[0],'stopping')

    def test_two_owners_separate_jobs_and_no_stale_reuse(self):
        a=self.gateway.open_verified_owner_project('alice',self.a.id)
        b=self.gateway.open_verified_owner_project('bob',self.b.id)
        self.assertNotEqual(a.project_id,b.project_id)
        self.bridge.close_trusted('alice',self.slots['alice'])
        self.assertEqual(self.guard.get_state('bob',self.slots['bob'])[0],'ready')
        self.bridge.close_trusted('bob',self.slots['bob'])

    def test_recovered_orphan_blocks_new_start(self):
        lease=self.ledger.start_trusted('alice',self.a.id)
        orphan=self.ledger.recover_after_restart()[0]
        self.assertEqual(orphan.job_id,lease.job_id)
        from urano.owner_engine_gateway import ExecutorUnavailable
        with self.assertRaises(ExecutorUnavailable):
            self.gateway.open_verified_owner_project('alice',self.a.id)
        self.assertEqual(self.guard.get_state('alice',self.slots['alice'])[0],'switching')

if __name__=='__main__':unittest.main()
