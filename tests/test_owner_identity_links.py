"""Verify both login orders preserve project UUIDs without email-only takeover."""
import tempfile
import unittest
import uuid
from pathlib import Path

from urano.owner_identity_links import LinkDenied, OwnerIdentityLinks
from urano.project_catalog import ProjectCatalog, ProjectNotFound


class OwnerLinkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / 'projects.sqlite3'
        self.catalog = ProjectCatalog(db)
        self.links = OwnerIdentityLinks(db)
        self.email = 'human@example.org'
        self.a = str(uuid.uuid4()); self.b = str(uuid.uuid4())

    def setup_owners(self, *, first):
        primary, secondary = (self.a, self.b) if first == 'password' else (self.b, self.a)
        self.links.bind_verified_identity(self.a,'password',self.email,verified_email=self.email)
        self.links.bind_verified_identity(self.b,'google','google-sub-abc',verified_email=self.email)
        p1 = self.catalog.create(primary,'Primera edición')
        edited = self.catalog.save_recipe(primary,p1.id,{'cuts':[{'camera':0,'start':1.4}]},expected_revision=0)
        p2 = self.catalog.create(secondary,'Segundo clip')
        return primary,secondary,edited,p2

    def test_password_first_then_google_no_duplicates_or_lost_edits(self):
        self.assert_same_after_link('password')

    def test_google_first_then_password_no_duplicates_or_lost_edits(self):
        self.assert_same_after_link('google')

    def assert_same_after_link(self, order):
        primary,secondary,p1,p2 = self.setup_owners(first=order)
        # Verified emails MATCH, but both owner IDs and project lists remain distinct.
        self.assertNotEqual(self.links.resolve('password',self.email),self.links.resolve('google','google-sub-abc'))
        self.assertEqual(len(self.catalog.list_for(primary)),1)
        self.assertEqual(len(self.catalog.list_for(secondary)),1)
        grants=(self.links.issue_link_grant(primary,now=1000),self.links.issue_link_grant(secondary,now=1000))
        self.assertEqual(self.links.link_proven_owners(primary,secondary,*grants,now=1001),primary)
        self.assertEqual({x.id for x in self.catalog.list_for(primary)},{p1.id,p2.id})
        self.assertEqual(self.catalog.get(primary,p1.id).recipe,p1.recipe)
        self.assertEqual(self.catalog.get(primary,p1.id).revision,1)
        self.assertEqual(self.links.resolve('password',self.email),primary)
        self.assertEqual(self.links.resolve('google','google-sub-abc'),primary)
        self.assertEqual(self.catalog.list_for(secondary),[])
        with self.assertRaises(ProjectNotFound): self.catalog.get(secondary,p1.id)
        # Re-opening SQLite maintains canonical owner and all projects.
        again=OwnerIdentityLinks(self.catalog.db_path)
        self.assertEqual(again.resolve('google','google-sub-abc'),primary)
        with self.assertRaises(LinkDenied): again.link_proven_owners(primary,secondary,*grants,now=1002)

    def test_one_proof_wrong_or_expired_never_moves_projects(self):
        primary,secondary,p1,p2=self.setup_owners(first='google')
        good=self.links.issue_link_grant(primary,now=1000)
        bad=self.links.issue_link_grant(secondary,now=1000)
        with self.assertRaises(LinkDenied): self.links.link_proven_owners(primary,secondary,good,good,now=1001)
        with self.assertRaises(LinkDenied): self.links.link_proven_owners(primary,secondary,good,bad,now=1300)
        self.assertEqual({x.id for x in self.catalog.list_for(primary)},{p1.id})
        self.assertEqual({x.id for x in self.catalog.list_for(secondary)},{p2.id})

    def test_existing_google_sub_cannot_be_hijacked(self):
        self.links.bind_verified_identity(self.a,'google','sub1',verified_email=self.email)
        with self.assertRaises(LinkDenied):
            self.links.bind_verified_identity(self.b,'google','sub1',verified_email=self.email)
        self.assertEqual(self.links.resolve('google','sub1'),self.a)

    def test_unverified_email_is_not_a_unification_proof(self):
        self.links.bind_verified_identity(self.a,'google','sub1',verified_email=self.email)
        self.links.bind_verified_identity(self.b,'password',self.email)
        self.assertNotEqual(self.links.resolve('google','sub1'),self.links.resolve('password',self.email))

if __name__ == '__main__': unittest.main()
