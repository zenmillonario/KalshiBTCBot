"""Bridge 1.1 keeps the telemetry adapter unchanged and serves local display assets."""
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from test_nautilus import fixture
from adapter import Adapter
from server import Handler, LocalServer, Publisher, VERSION


class BridgeReleaseTests(unittest.TestCase):
    def test_adapter_blob_is_unchanged(self):
        path = Path(__file__).resolve().parents[1] / 'adapter.py'
        content = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        self.assertEqual(blob, '049bc787fd6bf5f93c3c27ea993ff923dce451cc')

    def test_publisher_versions_are_separate(self):
        with tempfile.TemporaryDirectory() as root:
            lab, run, manifest, pointer, _ = fixture(Path(root), closed=True)
            publisher = Publisher(Adapter(run, manifest, lab, pointer, True))
            publisher.once()
            state = json.loads(publisher.body)
            self.assertEqual(state['version'], '1.1.0')
            self.assertEqual(state['adapter_version'], '1.0.0')
            self.assertEqual(state['accounting']['realized'], 2)
            self.assertEqual(VERSION, '1.1.0')

    def test_display_assets_are_local_and_served(self):
        with tempfile.TemporaryDirectory() as root:
            lab, run, manifest, pointer, _ = fixture(Path(root), closed=True)
            server = LocalServer(('127.0.0.1', 0), Handler)
            server.token = 'test-only'
            server.publisher = Publisher(Adapter(run, manifest, lab, pointer, True))
            server.publisher.once()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for path in ['/bridge.css', '/bridge.js', '/']:
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    connection.request('GET', path)
                    response = connection.getresponse()
                    data = response.read()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                    self.assertTrue(data)
                    if path == '/':
                        self.assertIn(b'/bridge.js', data)
                        self.assertIn(b'/bridge.css', data)
                        self.assertIn(b'id="bridgeFullscreen"', data)
                    connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
