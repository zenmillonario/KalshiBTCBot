import json
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from strategy_core.paper_dashboard import Dashboard
from tests.tool_rack.test_nautilus_projection import status as nautilus_status


class PaperDashboardTests(unittest.TestCase):
    def test_nautilus_feed_retains_unpublished_beats_and_reload_uses_detached_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            dashboard = Dashboard(temporary)
            url = dashboard.start()
            try:
                dashboard.observe(nautilus_status(ts=1000, reason="FIRST_WAIT"))
                dashboard.observe(nautilus_status(ts=1001, reason="SECOND_WAIT"))
                final = nautilus_status(ts=1002, reason="THIRD_WAIT")
                dashboard.publish(final, [])
                final["decisions"][0]["decision"]["reason"] = "MUTATED_AFTER_PUBLISH"
                with urlopen(url + "api/nautilus", timeout=2) as response:
                    payload = json.load(response)
                with urlopen(url + "api/nautilus", timeout=2) as response:
                    self.assertEqual(payload, json.load(response))
                self.assertEqual(payload["mode"], "PAPER_ONLY")
                self.assertIs(payload["readonly"], True)
                feed = [row for row in payload["feed"] if row["kind"] == "COMMANDER"]
                self.assertEqual([row["time"] for row in feed], [1000, 1001, 1002])
                self.assertIn("THIRD WAIT", feed[-1]["text"])
                self.assertNotIn("MUTATED_AFTER_PUBLISH", json.dumps(payload))
                self.assertEqual(payload["trades"], [])
                self.assertIs(payload["quote"]["fresh"], False)
                self.assertEqual(list(Path(temporary).iterdir()), [])
            finally:
                dashboard.close()

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
                for suffix in ("", "nautilus/app.js", "nautilus/chart.js", "nautilus/bridge.js",
                               "nautilus/reliability-ui.js", "nautilus/style.css", "nautilus/bridge.css"):
                    with urlopen(url + suffix, timeout=2) as response:
                        body = response.read().decode()
                        self.assertNotIn("https://", body)
                        self.assertNotIn("http://", body)
                        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
                with self.assertRaises(HTTPError) as rejected:
                    urlopen(Request(url + "api/nautilus", data=b"{}", method="POST"), timeout=2)
                self.assertEqual(rejected.exception.code, 405)
            finally:
                dashboard.close()


if __name__ == "__main__":
    unittest.main()
