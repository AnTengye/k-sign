import json
import os
import types
import unittest

from tests.test_newapi_sign import _install_stubs, FakeResponse


_install_stubs()


class SiteRepairTests(unittest.TestCase):
    def test_miaocy_login_submits_captcha_code(self):
        import miaocy

        class FakeSelector:
            def __init__(self, response=None, *args, **kwargs):
                self.response = response

            def re(self, pattern):
                return ["nonce123"]

        class FakeSession:
            def __init__(self):
                self.posts = []

            def get(self, url, **kwargs):
                return FakeResponse(status_code=200, text="<html></html>")

            def post(self, url, headers=None, data=None, **kwargs):
                self.posts.append((url, data))
                if isinstance(data, dict) and data.get("action") == "zb_get_captcha_img":
                    return FakeResponse(
                        status_code=200,
                        payload={"status": 1, "msg": "data:image/jpeg;base64,abc123"},
                        text=json.dumps({"status": 1, "msg": "data:image/jpeg;base64,abc123"}),
                    )
                return FakeResponse(
                    status_code=200,
                    payload={"status": 1, "msg": "ok"},
                    text=json.dumps({"status": 1, "msg": "ok"}),
                )

        original_selector = miaocy.Selector
        original_handle_yzm = getattr(miaocy, "handle_yzm", None)
        try:
            miaocy.Selector = FakeSelector
            miaocy.handle_yzm = lambda content, t="img": "ABCD"

            signer = miaocy.MiaoCYSign.__new__(miaocy.MiaoCYSign)
            signer.base_url = "https://miaociyuan.top"
            signer.url_info = types.SimpleNamespace(hostname="miaociyuan.top")
            signer.username = "user"
            signer.password = "pass"
            signer.session = FakeSession()
            signer.pwl = lambda msg: None

            self.assertTrue(signer.login())
            login_payload = signer.session.posts[-1][1]
            self.assertIn("captcha_code=ABCD", login_payload)
            self.assertIn("nonce=nonce123", login_payload)
        finally:
            miaocy.Selector = original_selector
            if original_handle_yzm is not None:
                miaocy.handle_yzm = original_handle_yzm

    def test_ljd_uses_cookie_login_when_cookie_is_configured(self):
        import ljd

        os.environ["SIGN_UP_LJD"] = "user|pass"
        os.environ["SIGN_COOKIE_LJD"] = "foo=bar"
        try:
            signer = ljd.LJDSign()
            self.assertEqual("login_cookie", signer.login_type)
        finally:
            os.environ.pop("SIGN_UP_LJD", None)
            os.environ.pop("SIGN_COOKIE_LJD", None)

    def test_ljd_passes_safe_challenge_with_safe_cookie(self):
        import ljd

        class CookieJar:
            def __init__(self):
                self.values = []

            def set(self, *args, **kwargs):
                self.values.append((args, kwargs))

        class FakeSession:
            def __init__(self):
                self.cookies = CookieJar()
                self.retried = []

            def get(self, url, **kwargs):
                self.retried.append(url)
                return FakeResponse(status_code=200, text="verifyhash = 'abc123'")

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.session = FakeSession()
        signer.url_info = types.SimpleNamespace(hostname="www.epl80.net")
        signer.pwl = lambda msg: None

        response = FakeResponse(status_code=200, text="<script>var safeid='SAFE,123'</script>")
        result = signer.pass_safe_challenge(response, "https://www.epl80.net/2048/login.php?")

        self.assertIn("verifyhash", result.text)
        self.assertEqual("https://www.epl80.net/2048/login.php?", signer.session.retried[0])
        self.assertEqual(("_safe", "SAFE,123"), signer.session.cookies.values[0][0][:2])

    def test_ljd_target_url_uses_site_root_after_redirect(self):
        import ljd

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://www.epl80.net"

        self.assertEqual(
            "https://www.epl80.net/read.php?tid=123",
            signer.build_read_url("123"),
        )

    def test_ljd_extracts_dynamic_reply_form_fields(self):
        import ljd
        import lxml.html

        class XPathList(list):
            def extract_first(self, default=None):
                if not self:
                    return default
                value = self[0]
                if isinstance(value, HtmlNode):
                    return value.node.text_content()
                return value

        class HtmlNode:
            def __init__(self, node):
                self.node = node

            def xpath(self, expr):
                return XPathList(
                    HtmlNode(item) if hasattr(item, "xpath") else item
                    for item in self.node.xpath(expr)
                )

        class HtmlSelector(HtmlNode):
            def __init__(self, text):
                super().__init__(lxml.html.fromstring(text))

        html = """
        <form name="FORM" action="post.php?">
          <input name="atc_usesign" value="1" />
          <input name="action" value="reply" />
          <input name="fid" value="57" />
          <input name="tid" value="268" />
          <input name="verify" value="dynverify" />
          <input name="_hexie" value="dynhexie" />
          <input name="one_sess" value="1" />
          <textarea name="atc_content"></textarea>
        </form>
        """
        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        original_selector = ljd.Selector
        ljd.Selector = HtmlSelector

        try:
            action, fields = signer.extract_reply_form(html)
        finally:
            ljd.Selector = original_selector

        self.assertEqual("post.php?", action)
        self.assertEqual("dynverify", fields["verify"])
        self.assertEqual("dynhexie", fields["_hexie"])
        self.assertEqual("1", fields["one_sess"])

    def test_sijis_uses_cookie_login_when_cookie_is_configured(self):
        import sijis

        os.environ["SIGN_UP_SJS"] = "user|pass"
        os.environ["SIGN_COOKIE_SJS"] = "foo=bar"
        try:
            signer = sijis.SiJiSSign()
            self.assertEqual("login_cookie", signer.login_type)
        finally:
            os.environ.pop("SIGN_UP_SJS", None)
            os.environ.pop("SIGN_COOKIE_SJS", None)

    def test_laowang_uses_cookie_login_when_cookie_is_configured(self):
        import laowang

        os.environ["SIGN_UP_LW"] = "user|pass"
        os.environ["SIGN_COOKIE_LW"] = "foo=bar"
        try:
            signer = laowang.LaoWangSSign()
            self.assertEqual("login_cookie", signer.login_type)
        finally:
            os.environ.pop("SIGN_UP_LW", None)
            os.environ.pop("SIGN_COOKIE_LW", None)


if __name__ == "__main__":
    unittest.main()
