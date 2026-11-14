import base64
import html
import io
import json
import os
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw

import moxing
from base import SignExecutionError


SCENES = {"sign": "click", "signin": "none", "default": "click"}


def page(signed=None, scenes=SCENES):
    props = {"captcha": {"scenes": scenes}, "auth": {"user": {"id": 1} if signed is not None else None},
             "turnstile": {"enabled": True, "siteKey": "public-site-key"}}
    if signed is not None:
        props["is_checked_in"] = signed
    data = html.escape(json.dumps({"props": props}), quote=True)
    return response(text=f'<div data-page="{data}"></div>')


def response(payload=None, status=200, text=""):
    def parse():
        if payload is None:
            raise ValueError("not JSON")
        return payload
    return types.SimpleNamespace(status_code=status, text=text, json=parse)


class FakeSession:
    def __init__(self, expected):
        self.expected = list(expected)
        self.calls = []
        self.cookies = requests.cookies.RequestsCookieJar()
        self.cookies.set("XSRF-TOKEN", "fixture%2Fcsrf")

    def request(self, method, url, **kwargs):
        if not self.expected:
            raise AssertionError(f"Unexpected {method} {urlparse(url).path}")
        want_method, path, result = self.expected.pop(0)
        if (method, urlparse(url).path) != (want_method, path):
            raise AssertionError(f"Expected {want_method} {path}, got {method} {urlparse(url).path}")
        self.calls.append((method, path, kwargs))
        return result

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


class MoxingSignTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env = patch.dict(os.environ, {
            "SIGN_UP_MOXING": "fixture-user|fixture-password",
            "SIGN_PROXY_MOXING": "off", "SIGN_SUMMARY_DIR": folder.name,
        }, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.signer = moxing.MoxingSign()

    def session(self, expected):
        session = FakeSession(expected)
        self.signer.session = session
        return session

    def test_official_main_and_legacy_domains(self):
        for url, want in [("https://mox.live", "https://mox.live"),
                          ("https://moxing.app", "https://mox.moxing.app"),
                          ("https://mox.moxing.my", "https://mox.moxing.my")]:
            self.signer.base_url, self.signer.url_info = url, urlparse(url)
            self.assertEqual(want, self.signer._forum_url())
        self.assertEqual(1, self.signer.retry_times)
        self.assertTrue(all(a.max_retries.total == 0 for a in self.signer.session.adapters.values()))

    def test_click_login_and_captcha_free_checkin_use_real_state_readback(self):
        session = self.session([
            ("GET", "/login", page()),
            ("POST", "/api/forum/captcha/go/click/challenge", response({"data": {"key": "challenge"}})),
            ("POST", "/api/forum/captcha/go/click/verify", response({"data": {"pass": "private-pass"}})),
            ("POST", "/api/forum/login", response({"success": True})),
            ("GET", "/forum/sign", page(False)),
            ("GET", "/forum/sign", page(False)),
            ("POST", "/api/forum/check-in/sign", response({"success": True})),
            ("GET", "/forum/sign", page(True)),
        ])
        dots = [{"x": 20, "y": 30}]
        with patch.object(self.signer, "_click_points", return_value=dots):
            self.assertTrue(self.signer.run())
        self.assertFalse(session.expected)
        verify, login, sign = session.calls[2], session.calls[3], session.calls[6]
        self.assertEqual({"key": "challenge", "dots": dots}, verify[2]["json"])
        self.assertEqual("private-pass", login[2]["json"]["captcha_pass"])
        self.assertNotIn("captcha", login[2]["json"])
        self.assertEqual({}, sign[2]["json"])
        self.assertEqual("fixture/csrf", sign[2]["headers"]["X-XSRF-TOKEN"])
        self.assertNotIn("private-pass", self.signer.log())
        self.assertNotIn("fixture-password", self.signer.log())

    def test_already_signed_needs_no_captcha_or_write(self):
        session = self.session([("GET", "/forum/sign", page(True))])
        with patch.object(self.signer, "_captcha", side_effect=AssertionError("must skip captcha")):
            self.assertTrue(self.signer.sign_v2())
        self.assertEqual(1, len(session.calls))

    def test_http_success_without_confirmed_state_fails_run(self):
        self.signer.login = Mock(return_value=True)
        self.session([
            ("GET", "/forum/sign", page(False)),
            ("POST", "/api/forum/check-in/sign", response({"success": True})),
            ("GET", "/forum/sign", page(False)),
        ])
        with self.assertRaises(SignExecutionError):
            self.signer.run()

    def test_expired_session_and_block_pages_never_submit(self):
        for result in [page(), response(text="<html>Cloudflare</html>"), response(text="[]")]:
            session = self.session([("GET", "/forum/sign", result)])
            self.assertFalse(self.signer.sign_v2())
            self.assertEqual(1, len(session.calls))

    def test_unsupported_security_gate_stops_before_login(self):
        self.session([("GET", "/login", page(scenes={"sign": "turnstile"}))])
        with patch.object(self.signer, "_click_captcha", side_effect=AssertionError("not click")):
            with self.assertRaises(SignExecutionError):
                self.signer.run()
        self.assertIn("人工完成", self.signer.log())

    def test_ambiguous_recognition_is_bounded_and_never_verified(self):
        session = self.session([
            ("GET", "/login", page()),
            *[("POST", "/api/forum/captcha/go/click/challenge", response({"data": {"key": "challenge"}}))] * 3,
        ])
        with patch.object(self.signer, "_click_points", return_value=None):
            with self.assertRaises(SignExecutionError):
                self.signer.run()
        self.assertFalse(session.expected)
        self.assertEqual(4, len(session.calls))

    def test_rate_limit_is_not_retried(self):
        session = self.session([
            ("GET", "/login", page()),
            ("POST", "/api/forum/captcha/go/click/challenge", response(status=429)),
        ])
        with self.assertRaises(SignExecutionError):
            self.signer.run()
        self.assertEqual(2, len(session.calls))

    def test_invalid_challenge_and_verify_response_are_not_success(self):
        for payload in [[], {"data": []}, {"data": {"key": "challenge", "image": "invalid"}}]:
            self.session([("POST", "/api/forum/captcha/go/click/challenge", response(payload))])
            self.assertIsNone(self.signer._click_captcha())
        for invalid in [response(text="<html>blocked</html>"), response([]),
                        response({"success": False, "data": {"pass": "private-pass"}})]:
            self.session([
                ("POST", "/api/forum/captcha/go/click/challenge", response({"data": {"key": "challenge"}})),
                ("POST", "/api/forum/captcha/go/click/verify", invalid),
            ])
            with patch.object(self.signer, "_click_points", return_value=[{"x": 1, "y": 2}]):
                self.assertIsNone(self.signer._click_captcha())

    def test_click_matching_sorts_hints_composites_alpha_and_scales_coordinates(self):
        def encoded(image):
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

        source = Image.new("RGB", (100, 50), "white")
        draw = ImageDraw.Draw(source)
        for box, color in [((0, 0, 19, 19), "red"), ((25, 0, 44, 19), "blue"), ((50, 0, 69, 19), "green")]:
            draw.rectangle(box, fill=color)
        hint = Image.new("RGBA", (60, 10))
        draw = ImageDraw.Draw(hint)
        draw.rectangle((5, 0, 14, 9), fill="blue")
        draw.rectangle((25, 0, 34, 9), fill="red")

        def detect(raw):
            image = Image.open(io.BytesIO(raw))
            if image.size == hint.size:
                self.assertEqual((255, 255, 255), image.getpixel((0, 0)))
                return [[25, 0, 35, 10], [5, 0, 15, 10]]
            return [[0, 0, 20, 20], [25, 0, 45, 20], [50, 0, 70, 20]]

        def recognize(raw):
            image = Image.open(io.BytesIO(raw))
            colors = {color for _, color in image.getcolors(image.width * image.height)}
            for color, text in [((255, 0, 0), "甲"), ((0, 0, 255), "乙"), ((0, 128, 0), "丙")]:
                if color in colors:
                    return text
            return ""

        detector = types.SimpleNamespace(detection=detect)
        ocr = types.SimpleNamespace(classification=recognize)
        data = {"image": encoded(source), "thumb": encoded(hint), "width": 200, "height": 100}
        with patch.object(moxing, "_click_model", side_effect=lambda kind: detector if kind == "det" else ocr):
            self.assertEqual([{"x": 70, "y": 20}, {"x": 20, "y": 20}], self.signer._click_points(data))
            ocr.classification = lambda raw: "甲"
            self.assertIsNone(self.signer._click_points(data))


if __name__ == "__main__":
    unittest.main()
