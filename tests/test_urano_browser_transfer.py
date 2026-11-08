"""Privacy and accounting contracts; no actual user media or network needed."""
import json
import unittest
from types import SimpleNamespace

from urano_browser_transfer import BrowserTransferMeter


def fake(url, method, *, request_body=0, response_body=0,
         request_header=100, response_header=140):
    return SimpleNamespace(
        url=url, method=method,
        sizes=lambda: {
            "requestBodySize": request_body,
            "responseBodySize": response_body,
            "requestHeadersSize": request_header,
            "responseHeadersSize": response_header,
        })


class BrowserTransfers(unittest.TestCase):
    def setUp(self):
        self.meter = BrowserTransferMeter(
            server_origin="http://127.0.0.1:8111",
            companion_origin="http://127.0.0.1:47777")

    def test_server_proxy_and_local_final_separated(self):
        self.meter.finished(fake(
            "http://127.0.0.1:8111/montara/uploads?access_token=SECRET",
            "POST", request_body=1200000, response_body=230))
        self.meter.finished(fake(
            "http://127.0.0.1:47777/video-renders/secret-uuid/file?download=1",
            "GET", response_body=40000000))
        self.meter.finished(fake(
            "http://127.0.0.1:47777/proxies/secret-uuid/file",
            "GET", response_body=90000))
        self.meter.finished(fake(
            "https://example.com/api/v1/stages/?token=SECRET", "POST",
            request_body=999999))
        result = self.meter.report(originals_sizes=[100000000, 200000000])
        self.assertEqual(result["server_upload_browser_body_bytes_observed"], 1200000)
        self.assertEqual(result["companion_final_video_download_body_bytes_observed"], 40000000)
        self.assertEqual(result["originals_total_bytes_local"], 300000000)
        self.assertFalse(result["original_upload_proven_absent"])
        self.assertFalse(result["remote_server_bytes_measured"])
        self.assertEqual(sum(x["requests"] for x in result["request_groups"]), 3)
        string = json.dumps(result)
        for secret in ("SECRET", "secret-uuid", "access_token", "example.com"):
            self.assertNotIn(secret, string)

    def test_missing_data_marked_unmeasured_not_zero(self):
        broken = SimpleNamespace(
            url="http://127.0.0.1:8111/api/v1/project",
            method="GET", sizes=lambda: (_ for _ in ()).throw(ValueError("error with PRIVATE TOKEN")))
        self.meter.finished(broken)
        result = self.meter.report()
        self.assertEqual(result["unmeasured_requests"], 1)
        self.assertEqual(result["request_groups"], [])

    def test_unknown_hosts_never_counted(self):
        self.meter.finished(fake("http://127.0.0.1:8112/montara/uploads", "POST", request_body=50))
        self.assertEqual(self.meter.report()["request_groups"], [])

    def test_reject_same_origin_and_credentials(self):
        with self.assertRaises(ValueError):
            BrowserTransferMeter(server_origin="http://127.0.0.1:1",
                                 companion_origin="http://127.0.0.1:1")
        with self.assertRaises(ValueError):
            BrowserTransferMeter(server_origin="http://user:password@127.0.0.1:1",
                                 companion_origin="http://127.0.0.1:2")

    def test_attach_read_only_listeners(self):
        captured = {}
        page = SimpleNamespace(on=lambda kind, callback: captured.setdefault(kind, callback))
        self.assertIs(self.meter.attach(page), self.meter)
        self.assertEqual(set(captured), {"requestfinished", "requestfailed"})
        captured["requestfinished"](fake("http://127.0.0.1:8111/api/v1/project", "GET",
                                        response_body=5000))
        captured["requestfailed"](fake("http://127.0.0.1:8111/api/v1/project", "GET"))
        self.assertEqual(self.meter.report()["failed_requests"], 1)


if __name__ == "__main__":
    unittest.main()
