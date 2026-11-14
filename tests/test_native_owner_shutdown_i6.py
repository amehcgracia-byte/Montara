"""I6 stop contract; no host systemd or live workers touched."""
from __future__ import annotations
import inspect
import unittest
from pathlib import Path
from urano.restricted_systemd_broker import fixed_launch_properties, SYSTEMD_PROPS
UNIT = "montara-i24-job-" + "a" * 32
ENGINE = Path("/opt/montara/bundles/engine-" + "b" * 40)
JM = Path("/opt/montara/bundles/jm-" + "c" * 40)
class CooperativeStopPolicyTests(unittest.TestCase):
    def test_bounded_grace_and_full_cgroup(self):
        props = fixed_launch_properties(UNIT, ENGINE, jm_bundle=JM, owner_id="i6-owner")
        self.assertIn("TimeoutStopSec=90s", props)
        self.assertIn("KillMode=control-group", props)
        self.assertIn("SendSIGKILL=yes", props)
        self.assertNotIn("TimeoutStopSec=3s", SYSTEMD_PROPS)
    def test_signal_only_requests_shutdown(self):
        from urano import native_owner_systemd_entry
        source = inspect.getsource(native_owner_systemd_entry.main)
        self.assertIn("shutdown_event.set()", source)
        self.assertNotIn("sys.exit(0)", source)
    def test_http_requests_are_drained(self):
        from urano import native_owner_worker_service
        source = inspect.getsource(native_owner_worker_service.serve_native_owner_workspace)
        self.assertIn("server.daemon_threads = False", source)
        self.assertIn("server.block_on_close = True", source)
        self.assertIn("server.shutdown()", source)
if __name__ == "__main__":
    unittest.main()
