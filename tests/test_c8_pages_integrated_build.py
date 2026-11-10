"""The published Pages build must contain only the reviewed standalone landing."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PagesBuildContract(unittest.TestCase):
    def test_pinned_build_only_copies_landing_and_security_headers(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            sandbox = Path(folder)
            target = sandbox / 'dist'
            from importlib.util import spec_from_file_location, module_from_spec
            spec = spec_from_file_location('safe_pages_build', root / 'tools/cloudflare-beta/build.py')
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            module.TARGET = target
            module.build()
            self.assertEqual({p.name for p in target.iterdir()}, {'index.html','_headers'})
            self.assertIn(module.OWNER_BASE + '/login', (target / 'index.html').read_text())
            self.assertIn(module.OWNER_BASE + '/register', (target / 'index.html').read_text())
            self.assertIn("default-src 'none'", (target / '_headers').read_text())
            with self.assertRaises(RuntimeError):
                module.build()  # never overwrite an existing output directory

    def test_builder_is_only_static_and_safe_when_public_portal_unavailable(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / 'tools/cloudflare-beta/build.py').read_text()
        self.assertNotIn('requests.get(', script)
        self.assertNotIn('subprocess.run(', script)
        self.assertNotIn('google-client-secret', script)
        self.assertNotIn('cloudflare-tunnel.token', script)

if __name__ == '__main__': unittest.main()
