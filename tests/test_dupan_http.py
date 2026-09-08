"""Optional real requests transport checks against a loopback-only synthetic server.

Run with: DUPAN_RUN_HTTP_TESTS=1 python3 -m unittest tests.test_dupan_http -v
"""
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


@unittest.skipUnless(os.getenv("DUPAN_RUN_HTTP_TESTS") == "1", "opt-in loopback HTTP integration")
class DuPanHTTPTests(unittest.TestCase):
    def setUp(self):
        import dupan
        self.module = dupan
        self.code = 200
        self.body = b'{"errno":0}'
        self.calls = []
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                test.calls.append(self.path)
                self.send_response(test.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Location", "/must-not-follow")
                self.end_headers()
                self.wfile.write(test.body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.05), daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup_server)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.output = io.StringIO()
        self.console = redirect_stdout(self.output)
        self.console.__enter__()
        self.addCleanup(self.console.__exit__, None, None, None)
        self.sign = dupan.DuPanSign()
        self.addCleanup(self.sign.session.close)
        self.sign.profile = {"native_static_params": {k: "synthetic-" + k for k in dupan.STATIC_KEYS}}
        self.sign.locked = True
        self.origin = patch("dupan.ORIGIN", "http://127.0.0.1:" + str(self.server.server_port))
        self.origin.start()
        self.addCleanup(self.origin.stop)

    def cleanup_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def submit(self):
        return self.sign._request_json(self.sign.SIGN, {
            "task_id": "12345678901234567890", "task_id_str": "12345678901234567890",
            "task_from": "task_sys_daily", "is_growth": "1"})

    def test_503_mutation_is_not_retried_by_requests(self):
        self.code = 503
        with self.assertRaises(self.module.DuPanError):
            self.submit()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.sign.session.get_adapter("https://").max_retries.total, 0)
        self.assertEqual(self.sign.session.get_adapter("http://").max_retries.total, 0)

    def test_redirect_is_not_followed(self):
        self.code = 302
        with self.assertRaises(self.module.DuPanError):
            self.submit()
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("/must-not-follow", self.calls)

    def test_actual_wire_parameters_are_exact_s1_and_fresh(self):
        self.assertEqual(self.submit(), {"errno": 0})
        self.sign._request_json(self.sign.HOME)
        first, second = [parse_qs(urlsplit(path).query) for path in self.calls]
        self.assertEqual(set(first), self.module.STATIC_KEYS | self.sign.BUSINESS_KEYS | {"rand", "time"})
        self.assertEqual(first["task_id_str"], ["12345678901234567890"])
        self.assertNotEqual(first["rand"], second["rand"])

    def test_malformed_response_is_not_logged_or_retried(self):
        self.body = b"BDUSS=synthetic-secret"
        with self.assertRaises(self.module.DuPanError):
            self.submit()
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("synthetic-secret", self.output.getvalue())
        self.assertNotIn("synthetic-secret", json.dumps(self.sign.report))


if __name__ == "__main__":
    unittest.main()
