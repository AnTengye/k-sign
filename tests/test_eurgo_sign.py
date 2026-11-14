import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.parse import urlparse

import requests

from base import SignExecutionError
from examples.eurgo import EurgoSign, main


LOGIN_FORM = """
<form id="aspnetForm" action="./login.aspx?returnUrl=%2Fmember%2Forder%2Flist.aspx">
  <input type="hidden" name="__VIEWSTATE" value="view-{attempt}">
  <input type="hidden" name="__EVENTVALIDATION" value="event-{attempt}">
  <input type="text" name="ctl00$body$txtUserName">
  <input type="password" name="ctl00$body$txtPassword">
  <input type="submit" name="ctl00$body$login_btn" value="立即登录">
</form>
"""
ORDER_PAGE = '<title>我的运单 - 会员中心</title><span id="ctl00_body_lbl_waybillsCount">0</span>'


def response(url, body="", status=200):
    result = requests.Response()
    result.status_code = status
    result.url = url
    result.encoding = "utf-8"
    result._content = body.encode()
    return result


class LoginSession(requests.Session):
    """仅接受正确表单且会话保存成功时，才开放订单页。"""

    def __init__(self, captcha_failures=0, authenticated=True, order_body=ORDER_PAGE):
        super().__init__()
        self.calls = []
        self.forms = 0
        self.posts = 0
        self.captcha_failures = captcha_failures
        self.authenticated = authenticated
        self.order_body = order_body
        self.cookies.set("unrelated", "do-not-export", domain="unrelated.test", path="/")

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        path = urlparse(url).path
        if path == "/member/login.aspx":
            self.forms += 1
            return response(url, LOGIN_FORM.format(attempt=self.forms))
        if path == "/GetCode.aspx":
            self.cookies.set("ASP.NET_SessionId", "session-secret", domain="www.eurgo.com", path="/")
            return response(url, "fake-image")
        if path == "/member/order/list.aspx":
            if self.authenticated and self.posts > self.captcha_failures:
                return response(url, self.order_body)
            return response(url, LOGIN_FORM.format(attempt=self.forms), 302)
        raise AssertionError(f"Unexpected GET: {url}")

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        self.posts += 1
        data = kwargs["data"]
        if data["__VIEWSTATE"] != f"view-{self.forms}" or data["__EVENTVALIDATION"] != f"event-{self.forms}":
            raise AssertionError("Stale ASP.NET form state")
        if self.posts <= self.captcha_failures:
            return response(url, "<script>alert('所填写的验证码与所给的不符！');</script>")
        if self.authenticated:
            self.cookies.set("Member", "member-secret", domain=".eurgo.com", path="/")
        return response(url, status=302)


class EurgoLoginTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        env = patch.dict(os.environ, {
            "SIGN_UP_EURGO": "fixture|password-secret",
            "SIGN_URL_EURGO": "https://www.eurgo.com/member/order/list.aspx",
            "SIGN_PROXY_EURGO": "false",
            "SIGN_NOTIFY_EACH": "0",
            "SIGN_SUMMARY_DIR": self.temp_dir.name,
        })
        env.start()
        self.addCleanup(env.stop)
        self.output = io.StringIO()
        output = redirect_stdout(self.output)
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        ocr = patch("examples.eurgo.handle_yzm", return_value="aB12")
        self.ocr = ocr.start()
        self.addCleanup(ocr.stop)

    def signer(self, session):
        signer = EurgoSign()
        signer.session.close()
        signer.session = session
        self.addCleanup(session.close)
        return signer

    def test_default_entry_does_not_initialize_signer_or_log_in(self):
        with patch("sys.argv", ["examples.eurgo"]), patch("examples.eurgo.EurgoSign") as constructor:
            main()
        constructor.assert_not_called()
        self.assertIn("--run", self.output.getvalue())

    def test_login_submits_current_form_and_exports_only_verified_scoped_cookies(self):
        session = LoginSession()
        signer = self.signer(session)
        self.assertTrue(signer.run())
        self.assertEqual(signer.base_url, "https://www.eurgo.com")
        post = next(call for call in session.calls if call[0] == "POST")
        self.assertEqual(post[2]["data"]["ctl00$body$txtUserName"], "fixture")
        self.assertEqual(post[2]["data"]["ctl00$body$txtPassword"], "password-secret")
        self.assertEqual(post[2]["data"]["getcode"], "aB12")
        self.assertEqual(post[2]["data"]["remeberMe"], "true")
        self.assertFalse(post[2]["allow_redirects"])
        self.assertEqual(session.calls[-1][1], signer.order_url)
        self.assertEqual(signer.cookie_header, "ASP.NET_SessionId=session-secret; Member=member-secret")
        self.assertEqual(signer.exec_method, [])
        for secret in ("password-secret", "session-secret", "member-secret"):
            self.assertNotIn(secret, signer.log())
            self.assertNotIn(secret, self.output.getvalue())

    def test_redirect_without_authenticated_readback_fails_and_emits_no_cookie(self):
        session = LoginSession(authenticated=False)
        signer = self.signer(session)
        with self.assertRaises(SignExecutionError):
            signer.run()
        self.assertFalse(signer.last_run_success)
        self.assertEqual(signer.cookie_header, "")
        self.assertEqual(session.posts, 1)

    def test_http_200_waf_or_login_page_is_not_success(self):
        for body in ("<title>访问验证</title>", LOGIN_FORM.format(attempt=1)):
            with self.subTest(body=body):
                signer = self.signer(LoginSession(order_body=body))
                self.assertFalse(signer.login())
                self.assertEqual(signer.cookie_header, "")

    def test_captcha_error_refreshes_form_before_retry(self):
        session = LoginSession(captcha_failures=1)
        signer = self.signer(session)
        self.assertTrue(signer.login())
        self.assertEqual(session.posts, 2)
        self.assertEqual(session.forms, 2)
        self.assertEqual(self.ocr.call_args.kwargs, {"t": "img"})

    def test_bad_ocr_never_submits_password_and_stops_after_three_attempts(self):
        self.ocr.return_value = "abc"
        session = LoginSession()
        signer = self.signer(session)
        self.assertFalse(signer.login())
        self.assertEqual(session.posts, 0)
        self.assertEqual(session.forms, 3)

    def test_server_captcha_rejections_are_bounded(self):
        session = LoginSession(captcha_failures=10)
        signer = self.signer(session)
        self.assertFalse(signer.login())
        self.assertEqual(session.posts, 3)
        self.assertEqual(signer.cookie_header, "")

    def test_unexpected_form_and_external_action_do_not_receive_credentials(self):
        for form in ("<title>维护中</title>", LOGIN_FORM.format(attempt=1).replace(
                './login.aspx?', 'https://unrelated.test/login?')):
            with self.subTest(form=form):
                session = LoginSession()
                session.get = lambda url, **kwargs: response(url, form)
                signer = self.signer(session)
                self.assertFalse(signer.login())
                self.assertEqual(session.posts, 0)

    def test_missing_or_empty_password_fails_before_network(self):
        for credentials in ("", "fixture|", "missing-separator"):
            with self.subTest(credentials=credentials), patch.dict(os.environ, {"SIGN_UP_EURGO": credentials}):
                with self.assertRaises(ValueError):
                    EurgoSign()


if __name__ == "__main__":
    unittest.main()
