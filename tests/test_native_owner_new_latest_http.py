"""Exact native Chema New/Latest route mapping; no generic public proxy."""
import unittest

from urano.native_owner_new_latest_http import native_new_latest_target


class NativeNewLatestHTTPTests(unittest.TestCase):
    def test_original_chema_new_and_recovery_are_admitted_unchanged(self):
        for method,path in (
            ("POST","/api/v1/wizard/projects/new"),
            ("POST","/api/v1/wizard/draft"),
            ("POST","/api/v1/wizard/projects/open"),
            ("GET","/montara/recovery/latest"),
            ("GET","/api/v1/project"),
            ("GET","/api/v1/wizard/projects"),
        ):
            with self.subTest(path=path):
                self.assertEqual(native_new_latest_target(method,path),path)

    def test_original_status_query_supports_native_before_and_after_draft(self):
        self.assertEqual(
            native_new_latest_target("GET","/api/v1/wizard/status",
                                     "project_id="),
            "/api/v1/wizard/status?project_id=")
        self.assertEqual(
            native_new_latest_target("GET","/api/v1/wizard/status",
                                     "project_id=%2Fprivate%2FProjects%2Fa"),
            "/api/v1/wizard/status?project_id=%2Fprivate%2FProjects%2Fa")

    def test_extra_queries_and_unknown_mutations_are_never_routed(self):
        for method,path,query in (
            ("POST","/montara/recovery/latest",""),
            ("GET","/api/v1/wizard/projects/new",""),
            ("POST","/api/v1/wizard/projects/open","project_id=foreign"),
            ("GET","/montara/recovery/latest","project_id=foreign"),
            ("GET","/api/v1/wizard/status","owner_id=foreign"),
            ("GET","/api/v1/wizard/status","project_id=a&project_id=b"),
            ("GET","/api/v1/wizard/status","project_id=a&owner_id=b"),
            ("GET","/montara/hidden",""),
            ("GET","/api/v1/wizard/projects/../other",""),
            ("DELETE","/api/v1/wizard/projects/open",""),
        ):
            with self.subTest(method=method,path=path,query=query):
                self.assertIsNone(native_new_latest_target(method,path,query))

    def test_untrusted_query_types_are_rejected(self):
        self.assertIsNone(native_new_latest_target(
            "GET","/api/v1/wizard/status",None))
        self.assertIsNone(native_new_latest_target(
            "GET","/api/v1/wizard/status",{"project_id":"a"}))


if __name__=="__main__":
    unittest.main()
