import json
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from strategy_core.paper_dashboard import Dashboard


class PaperDashboardTests(unittest.TestCase):
    def test_publish_detaches_objects_and_get_is_only_read_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            dashboard = Dashboard(temporary)
            url = dashboard.start()
            try:
                status = {"state": "RUNNING", "positions": {"1": {"qty": 7}},
                          "source_status": MappingProxyType({"btc_current": True})}
                rows = [{"epoch_ms": 1000, "btc_price": 80000, "unneeded_geometry_state": "omit"}]
                dashboard.publish(status, rows)
                status["positions"]["1"]["qty"] = 100
                rows[0]["btc_price"] = 0
                with urlopen(url + "api/state", timeout=2) as response:
                    payload = json.load(response)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(payload["status"]["positions"]["1"]["qty"], 7)
                self.assertEqual(payload["geometry_rows"][0]["btc_price"], 80000)
                self.assertEqual(set(payload["geometry_rows"][0]), {"epoch_ms", "btc_price", "ema9", "ema30"})
                with self.assertRaises(HTTPError) as rejected:
                    urlopen(Request(url + "api/state", data=b"{}", method="POST"), timeout=2)
                self.assertEqual(rejected.exception.code, 405)
                with self.assertRaises(HTTPError) as unknown:
                    urlopen(url + "STATUS.json", timeout=2)
                self.assertEqual(unknown.exception.code, 404)
                self.assertEqual(list(Path(temporary).iterdir()), [])
            finally:
                dashboard.close()
                dashboard.close()

    def test_loopback_host_and_assets_have_no_external_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            dashboard = Dashboard(temporary)
            url = dashboard.start()
            try:
                self.assertTrue(url.startswith("http://127.0.0.1:"))
                with self.assertRaises(HTTPError) as rejected:
                    urlopen(Request(url, headers={"Host": "untrusted.example"}), timeout=2)
                self.assertEqual(rejected.exception.code, 403)
                for suffix in ("", "dashboard.js", "dashboard.css"):
                    with urlopen(url + suffix, timeout=2) as response:
                        body = response.read().decode()
                        self.assertNotIn("https://", body)
                        self.assertNotIn("http://", body)
                        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            finally:
                dashboard.close()


if __name__ == "__main__":
    unittest.main()
