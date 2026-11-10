"""Pure I17 controller safety contracts; NEVER start Linux units in CI."""
from pathlib import Path
from unittest import TestCase, mock
import tempfile

from urano_i17_broker_cancel_lab import (NAME, target_stop, unit_status,
    cgroup_pids, check_sha, PREFIX)


class BrokerLabContracts(TestCase):
    def test_only_random_lab_service_can_be_stopped(self):
        correct=PREFIX+'abcdef123456'
        self.assertTrue(NAME.fullmatch(correct))
        for value in ('montara-owner-beta','montara-owner-tunnel',
                      'montara-i16-lab-abcdef123456',
                      'montara-i17-target-../other','montara-i17-target-ff',
                      'montara-i17-target-abcdef123456.service',''):
            self.assertFalse(NAME.fullmatch(value))
            with self.assertRaises(ValueError):target_stop(value)
            with self.assertRaises(ValueError):unit_status(value)

    def test_stop_uses_noblock_and_exact_user_unit(self):
        value=PREFIX+'abcdef123456'
        with mock.patch('urano_i17_broker_cancel_lab.command') as cmd:
            target_stop(value)
            cmd.assert_called_once_with('systemctl','--user','stop','--no-block',
                value+'.service',timeout=6,check=False)

    def test_cgroup_inspection_cannot_leave_i17_service(self):
        for raw in ('/user.slice/other.service',
                    '/user.slice/user-1006.slice/user@1006.service/app.slice/montara-owner-beta.service',
                    '/user.slice/user-1006.slice/user@1006.service/app.slice/montara-i17-target-abcdef123456.service/..',
                    '/other/montara-i17-target-abcdef123456.service'):
            with self.assertRaises(ValueError):cgroup_pids(raw)

    def test_wrong_pinned_engine_ref_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch('urano_i17_broker_cancel_lab.command') as cmd:
                from unittest.mock import Mock
                cmd.side_effect=[Mock(stdout='a'*40+'\n'),Mock(stdout='b'*40+'\n')]
                with self.assertRaisesRegex(RuntimeError,'mismatch'):
                    check_sha(Path(root),Path(root))

    def test_opt_in_no_public_http_and_bounded_os_kill(self):
        lab=(Path(__file__).parent/'urano_i17_broker_cancel_lab.py').read_text()
        launcher=(Path(__file__).parent/'urano_i17_target_entry.sh').read_text()
        self.assertIn("if __name__=='__main__':main()",lab)
        self.assertNotIn('Blueprint(',lab)
        self.assertNotIn('app.route(',lab)
        self.assertNotIn('sudo ',lab)
        self.assertNotIn('docker run',lab)
        self.assertIn("'--property=TimeoutStopSec=3s'",lab)
        self.assertIn("'--property=KillMode=control-group'",lab)
        self.assertIn('ffmpeg_descendant_reaped',lab)
        self.assertIn('not cgroup_pids(group)',lab)
        self.assertIn('/usr/bin/ffmpeg',launcher)
        self.assertIn('anullsrc=',launcher)
        self.assertNotIn('https://',launcher)
        self.assertNotIn('curl ',launcher)

if __name__=='__main__':
    import unittest
    unittest.main()
