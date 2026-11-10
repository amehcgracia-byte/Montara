"""Offline I20 safety checks; CI never starts services or connects to Google."""
import os
import unittest
from pathlib import Path
from unittest import mock

from urano_i20_oidc_to_real_engine_lab import attested_cgroup_empty


class I20LabSafety(unittest.TestCase):
    def setUp(self):
        self.unit='montara-i20-lab-a1b2c3d4e5f6'
        uid=os.getuid()
        self.group=(f'/user.slice/user-{uid}.slice/user@{uid}.service/'
                    f'app.slice/{self.unit}.service')

    def test_root_or_cross_service_group_rejected(self):
        for group in ('','/','/user.slice','/user.slice/user-1006.slice/session-1.scope',
                      self.group.replace('i20','owner'),self.group+'/..'):
            with self.subTest(group=group),self.assertRaises(ValueError):
                attested_cgroup_empty(self.unit,group)

    def test_other_unit_names_rejected_even_with_fake_group(self):
        for unit in ('montara-owner-beta','montara-i17-target-abcdef123456',
                     'montara-i20-lab-aaa','montara-i20-lab-a1b2c3d4e5f6.service'):
            with self.subTest(unit=unit),self.assertRaises(ValueError):
                attested_cgroup_empty(unit,self.group)

    def test_attested_removed_cgroup_is_empty(self):
        with mock.patch('pathlib.Path.read_text',side_effect=FileNotFoundError):
            self.assertTrue(attested_cgroup_empty(self.unit,self.group))

    def test_attested_live_cgroup_cannot_claim_empty(self):
        with mock.patch('pathlib.Path.read_text',return_value='20491\\n20495\\n'):
            self.assertFalse(attested_cgroup_empty(self.unit,self.group))

    def test_lab_only_no_web_activation(self):
        source=(Path(__file__).parent/'urano_i20_oidc_to_real_engine_lab.py').read_text()
        self.assertIn('fake verified Google OIDC',source)
        self.assertIn('public_beta_modified\':False',source)
        self.assertIn('host_uid_per_tenant_isolated\':False',source)
        self.assertNotIn('app.run(',source)
        self.assertNotIn('cloudflared',source)
        self.assertNotIn('sudo ',source)

if __name__=='__main__':unittest.main()
