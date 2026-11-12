"""I15 safe-by-default contract: offline test never provisions workers in CI.

For real execution, the operator invokes the opt-in local program directly.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'tests' / 'urano_i15_namespace_entry.sh'
PROBE = ROOT / 'tests' / 'urano_i15_namespace_real_open_lab.py'


class RootlessNamespaceLabContract(unittest.TestCase):
    def test_lab_is_not_a_public_endpoint_or_auto_started_runtime(self):
        shell = LAUNCHER.read_text()
        python = PROBE.read_text()
        self.assertIn('if __name__==\'__main__\': main()', python)
        self.assertNotIn('app.route(',python)
        self.assertNotIn('Blueprint(',python)
        self.assertNotIn('docker run',shell)
        self.assertNotIn('sudo ',shell)
        self.assertNotIn('systemctl ',shell)
        self.assertNotIn('lxc launch',shell)
        self.assertIn('production_sandbox_certified\':False',python)
        self.assertIn('companion_tested\':False',python)

    def test_explicit_code_mounts_and_protection_present(self):
        text = LAUNCHER.read_text()
        for clause in ('mount --make-rprivate /',
                       'mount -t tmpfs',
                       'mount --bind "$item" "$dest"',
                       'mount -o remount,bind,ro "$dest"',
                       'mount --bind "$workspace" "$root/workspace"',
                       '--no-new-privs',
                       '--bounding-set=-all',
                       'ulimit -v 4194304',
                       'ulimit -t 60'):
            self.assertIn(clause,text)
        self.assertNotIn('mount --bind /home',text)
        self.assertNotIn('mount --bind /var',text)
        self.assertNotIn('mount --bind /proc',text)
        self.assertNotIn('mount --bind /run',text)
        self.assertNotIn('owner-beta.env',text)
        self.assertNotIn('google-client-secret',text)
        self.assertNotIn('cloudflare-tunnel.token',text)
        python = PROBE.read_text()
        self.assertIn("'--mount','--net'",python)
        self.assertIn('foreign_owner_hidden',python)
        self.assertIn('dedicated_user_mount_network_namespaces',python)
        self.assertIn('pid_namespace_isolated\']=False',python)
        self.assertIn('worker_rss_one_sample_mib',python)

if __name__=='__main__': unittest.main()
