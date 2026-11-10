"""C8 public beta landing links only to reviewed Google owner entry, not classic editor."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import unittest

LANDING = Path(__file__).resolve().parents[1] / 'deployment/cloudflare-beta/public/index.html'
OWNER = 'https://montara-owner.memoriainvalida001.workers.dev'
ALLOWED = {OWNER + '/login', OWNER + '/register'}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []
        self.buttons = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'a': self.anchors.append(d)
        if tag == 'button': self.buttons.append(d)


class PublicOwnerEntryContract(unittest.TestCase):
    def test_login_and_register_ctas_use_exact_trusted_owner_https_origin(self):
        text = LANDING.read_text(encoding='utf8')
        links = Links(); links.feed(text)
        url = urlsplit(OWNER)
        self.assertEqual((url.scheme, url.path, url.query, url.fragment), ('https', '', '', ''))
        google = [a.get('href') for a in links.anchors if a.get('href') in ALLOWED]
        self.assertEqual(set(google), ALLOWED)
        for a in links.anchors:
            href = a.get('href', '')
            self.assertFalse('8101' in href or '8102' in href or '8103' in href or '8114' in href)
            if not href.startswith('#'): self.assertIn(href, ALLOWED)
        self.assertNotIn('Acceso con Google próximamente', text)
        self.assertNotIn('montara-tau.vercel.app', text)

    def test_not_promise_password_signup_or_engine_or_original_upload(self):
        text = LANDING.read_text(encoding='utf8')
        self.assertIn('registro con email y contraseña', text)
        self.assertIn('aún no están disponibles', text)
        self.assertIn('testers autorizados', text)
        self.assertIn('editor', text.lower())
        self.assertNotIn('<form', text)
        self.assertNotIn('<input', text)

    def test_security_headers_preserved(self):
        headers = (LANDING.parent / '_headers').read_text()
        self.assertIn("Content-Security-Policy: default-src 'none'", headers)
        self.assertIn('X-Frame-Options: DENY', headers)


if __name__ == '__main__': unittest.main()
