"""The public login choice must not enable unverified email/password or Engine."""
import tempfile
import unittest
from pathlib import Path
from urano.owner_beta_wsgi import create_private_owner_beta

class LoginChoice(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        root=Path(tmp.name);private=root/'owner';private.mkdir(mode=0o700)
        key=root/'secret';key.write_text('synthetic-not-real');key.chmod(0o600)
        env={"MONTARA_BETA_ORIGIN":"https://beta.example.test", "MONTARA_COMPANION_BETA_ORIGIN":"https://beta.example.test", "MONTARA_GOOGLE_CLIENT_ID":"123456-synthetic.apps.googleusercontent.com", "MONTARA_BETA_ALLOWED_EMAILS":"user@example.test", "MONTARA_GOOGLE_SECRET_FILE":str(key), "MONTARA_OWNER_PRIVATE_DIR":str(private)}
        self.client=create_private_owner_beta(env).test_client()
    def test_login_register_are_real_html_and_google_is_only_available_provider(self):
        for path in ('/login','/register'):
            response=self.client.get(path,base_url='https://beta.example.test')
            self.assertEqual(response.status_code,200)
            page=response.get_data(as_text=True)
            self.assertIn('Continuar con Google',page)
            self.assertIn('href="/urano/v1/google/start"',page)
            self.assertIn('Correo y contraseña',page)
            self.assertIn('No crees una contraseña todavía',page)
            self.assertNotIn('<form',page)
            self.assertIn("default-src 'none'",response.headers['Content-Security-Policy'])
            self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_trusted_host_and_antiforwarding_still_applies(self):
        for path in ('/login','/register'):
            self.assertEqual(self.client.get(path,base_url='http://localhost').status_code,403)
            self.assertEqual(self.client.get(path,base_url='https://beta.example.test',headers={'X-Forwarded-Host':'evil.test'}).status_code,403)
    def test_root_legacy_google_bookmark_still_works(self):
        r=self.client.get('/',base_url='https://beta.example.test')
        self.assertEqual(r.status_code,303)
        self.assertEqual(r.headers['Location'],'/urano/v1/google/start')

if __name__=='__main__':unittest.main()
