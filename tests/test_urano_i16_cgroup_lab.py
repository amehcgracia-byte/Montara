"""I16 safety guards, independent of any systemd daemon or installed Engine."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from urano_i16_cgroup_real_engine_lab import (MEMORY_BYTES, TASKS_LIMIT,
    checked_engine, properties, stop_unit, verify_limits)


class I16GuardTests(unittest.TestCase):
    def test_exact_positive_cgroup_contract(self):
        name='montara-i16-lab-a1b2c3d4e5f6'
        good={'MemoryMax':str(MEMORY_BYTES),'TasksMax':str(TASKS_LIMIT),
              'CPUQuotaPerSecUSec':'1s',
              'ControlGroup':'/user.slice/app.slice/'+name+'.service',
              'ActiveState':'active'}
        verify_limits(good,name)
        for key,value in [('MemoryMax','infinity'),('TasksMax','500'),
                          ('CPUQuotaPerSecUSec','infinity'),('ActiveState','failed'),
                          ('ControlGroup','/not-this-unit.service')]:
            bad={**good,key:value}
            with self.assertRaises(AssertionError):verify_limits(bad,name)

    def test_never_manage_non_lab_unit(self):
        for name in ('montara-owner-beta','montara-owner-tunnel','montara-i16-lab-../../owner',
                     'montara-i16-lab-nope',''):
            with self.assertRaises(ValueError):stop_unit(name)
            with self.assertRaises(ValueError):properties(name)

    def test_submodule_sha_mismatch_blocks_engine(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            with mock.patch('urano_i16_cgroup_real_engine_lab.subprocess.check_output',side_effect=['a'*40,'b'*40]):
                with self.assertRaisesRegex(ValueError,'submodule version mismatch'):
                    checked_engine(d,d)

    def test_opt_in_no_http_or_prod_sandbox_claim(self):
        script=(Path(__file__).parent/'urano_i16_cgroup_real_engine_lab.py').read_text()
        self.assertIn('if __name__==\'__main__\':main()',script)
        self.assertIn('"production_isolation_certified":False',script)
        self.assertIn('"companion_tested":False',script)
        self.assertIn('"video_render_tested":False',script)
        self.assertIn('"--property=MemoryMax=512M"',script)
        self.assertIn('"--property=TasksMax=24"',script)
        self.assertIn('"--pid","--fork"',script)
        self.assertNotIn('sudo ',script)
        self.assertNotIn('docker run',script)
        self.assertNotIn('app.route(',script)
        self.assertNotIn('google-client-secret',script)

if __name__=='__main__':unittest.main()
