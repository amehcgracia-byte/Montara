"""Verify H4 beta session policy: default and maximum three days."""
import tempfile
import unittest
from pathlib import Path

from urano.session_auth import SessionStore


class H4OwnerSessionTTLTests(unittest.TestCase):
    def test_three_day_session_accepted_and_expires_at_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            sessions = SessionStore(Path(temp) / "sessions.sqlite3")
            now = 2_000_000_000
            issued = sessions.issue("test:h4-user", ttl_seconds=3 * 86400, now=now)
            self.assertEqual(issued.expires_at, now + 3 * 86400)
            self.assertIsNotNone(sessions.verify(issued.token, now=now + 3 * 86400 - 1))
            self.assertIsNone(sessions.verify(issued.token, now=now + 3 * 86400))

    def test_excessive_session_ttl_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            sessions = SessionStore(Path(temp) / "sessions.sqlite3")
            with self.assertRaises(ValueError):
                sessions.issue("test:h4-user", ttl_seconds=3 * 86400 + 1)

    def test_default_session_ttl_is_three_days(self):
        with tempfile.TemporaryDirectory() as temp:
            sessions = SessionStore(Path(temp) / "sessions.sqlite3")
            issued = sessions.issue("test:h4-user", now=2_000_000_000)
            self.assertEqual(issued.expires_at, 2_000_259_200)


if __name__ == "__main__":
    unittest.main()
