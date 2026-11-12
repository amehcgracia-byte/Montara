"""Owner-bound Chema full-session route and SQLite isolation contract."""
import tempfile
import unittest
from pathlib import Path

from werkzeug.datastructures import MultiDict

from urano.owner_session_contract import session_operation, session_query, session_media
from urano.owner_session_bindings import OwnerSessionBindings, SessionOwnershipError
from urano.project_catalog import ProjectCatalog


class OwnerSessionContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cat=ProjectCatalog(Path(self.tmp.name)/"projects.sqlite3")
        self.a=self.cat.create("owner-a","Stage A")
        self.b=self.cat.create("owner-a","Stage B")
        self.foreign=self.cat.create("owner-b","Other Owner")
        self.claims=OwnerSessionBindings(self.cat)

    def test_mixer_paths_are_explicit_and_reject_unsafe_methods(self):
        sid="c"*12
        pairs=(
            ("POST","session","/montara/session"),
            ("GET","session/latest","/montara/session/latest"),
            ("GET",f"session/{sid}",f"/montara/session/{sid}"),
            ("GET",f"session/{sid}/waveform",f"/montara/session/{sid}/waveform"),
            ("GET",f"session/{sid}/video-source",f"/montara/session/{sid}/video-source"),
            ("GET",f"session/{sid}/listen",f"/montara/session/{sid}/listen"),
            ("HEAD",f"session/{sid}/listen",f"/montara/session/{sid}/listen"),
            ("POST",f"session/{sid}/video-master",f"/montara/session/{sid}/video-master"),
            ("POST",f"session/{sid}/cancel",f"/montara/session/{sid}/cancel"),
            ("POST",f"session/{sid}/prepare",f"/montara/session/{sid}/prepare"),
            ("POST",f"session/{sid}/render",f"/montara/session/{sid}/render"),
            ("POST",f"session/{sid}/songs",f"/montara/session/{sid}/songs"),
            ("POST",f"session/{sid}/include",f"/montara/session/{sid}/include"),
            ("GET",f"session/{sid}/local-plan",f"/montara/session/{sid}/local-plan"),
            ("POST",f"session/{sid}/local-result",f"/montara/session/{sid}/local-result"),
            ("GET",f"session/{sid}/originals",f"/montara/session/{sid}/originals"),
            ("POST",f"session/{sid}/originals",f"/montara/session/{sid}/originals"),
            ("GET",f"session/{sid}/results.zip",f"/montara/session/{sid}/results.zip"),
            ("GET",f"session/{sid}/result/2",f"/montara/session/{sid}/result/2"),
        )
        for method,relative,expected in pairs:
            with self.subTest(relative=relative,method=method):
                actual=session_operation(method,relative)
                self.assertEqual(actual[0],expected)
        for method,relative in (
            ("DELETE","session"),("GET","session"),
            ("GET","session/../../etc/passwd"),
            ("GET",f"session/{sid}/../../project"),
            ("POST",f"session/{sid}/result/2"),
            ("DELETE",f"session/{sid}"),
            ("GET","session/"+"e"*40),
            ("POST",f"session/{sid}/local-plan"),
            ("GET",f"session/{sid}/cancel")
        ):
            with self.subTest(denied=relative,method=method):
                self.assertIsNone(session_operation(method,relative))

    def test_query_is_bounded_and_untrusted_paths_are_never_forwarded(self):
        sid="c"*12
        approved=[
            (f"session/{sid}/listen",MultiDict([("start","0.5"),("end","15")])),
            (f"session/{sid}/originals",MultiDict([("song","2")])),
            (f"session/{sid}/local-plan",MultiDict([("song","2"),("start","2"),("end","8")])),
            (f"session/{sid}/result/1",MultiDict([("download","1")])),
        ]
        for op,args in approved:
            with self.subTest(op=op):
                self.assertTrue(session_query(op,args).startswith("?"))
        blocked=[
            (f"session/{sid}/listen",MultiDict([("start","../../etc/passwd"),("end","20")])),
            (f"session/{sid}/local-plan",MultiDict([("song","1"),("path","/etc/shadow")])),
            (f"session/{sid}/originals",MultiDict([("song","1"),("song","2")])),
            (f"session/{sid}/result/1",MultiDict([("download","../secrets")])),
            (f"session/{sid}/waveform",MultiDict([("path","/root")]))
        ]
        for op,args in blocked:
            with self.subTest(op=op):
                self.assertIsNone(session_query(op,args))
        self.assertTrue(session_media("GET",f"session/{sid}/listen"))
        self.assertTrue(session_media("GET",f"session/{sid}/result/1"))
        self.assertTrue(session_media("HEAD",f"session/{sid}/listen"))
        self.assertFalse(session_media("GET",f"session/{sid}"))

    def test_session_cannot_be_reused_from_another_project_or_owner(self):
        sid="d"*12
        self.claims.bind("owner-a",self.a.id,sid)
        self.claims.bind("owner-a",self.a.id,sid)  # idempotent restore
        self.assertEqual(self.claims.latest("owner-a",self.a.id),sid)
        self.claims.require("owner-a",self.a.id,sid)
        with self.assertRaises(SessionOwnershipError):
            self.claims.require("owner-a",self.b.id,sid)
        with self.assertRaises(SessionOwnershipError):
            self.claims.require("owner-b",self.foreign.id,sid)
        with self.assertRaises(SessionOwnershipError):
            self.claims.bind("owner-a",self.b.id,sid)
        with self.assertRaises(SessionOwnershipError):
            self.claims.bind("owner-b",self.foreign.id,sid)
        self.assertIsNone(self.claims.latest("owner-a",self.b.id))
        self.assertIsNone(self.claims.latest("owner-b",self.foreign.id))

    def test_malformed_ids_fail_closed(self):
        for sid in ("ABCDEFABCDEF", "../bad", "a"*32, "0"*11):
            with self.subTest(sid=sid):
                with self.assertRaises(ValueError):
                    self.claims.bind("owner-a",self.a.id,sid)
                with self.assertRaises(ValueError):
                    self.claims.require("owner-a",self.a.id,sid)


if __name__=="__main__":
    unittest.main()
