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
            self.assertEqual("ABCD", login_payload["captcha_code"])
            self.assertEqual("nonce123", login_payload["nonce"])
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
        result = signer.pass_safe_challenge(response, "https://www.epl80.net/login.php?")

        self.assertIn("verifyhash", result.text)
        self.assertEqual("https://www.epl80.net/login.php?", signer.session.retried[0])
        self.assertEqual(("_safe", "SAFE,123"), signer.session.cookies.values[0][0][:2])

    def test_ljd_target_url_uses_site_root_after_redirect(self):
        import ljd

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://www.epl80.net"

        self.assertEqual(
            "https://www.epl80.net/read.php?tid=123",
            signer.build_read_url("123"),
        )

    def test_ljd_sign_uses_site_root(self):
        import ljd

        class FakeSession:
            def __init__(self):
                self.gets = []
                self.posts = []

            def get(self, url, **kwargs):
                self.gets.append(url)
                return FakeResponse(status_code=200, text="")

            def post(self, url, **kwargs):
                self.posts.append(url)
                return FakeResponse(status_code=200, text="签到成功")

        class FakeSelector:
            def __init__(self, response=None, **kwargs):
                pass

            def re(self, pattern):
                return ["签到成功"]

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://www.epl80.net"
        signer.session = FakeSession()
        signer.pwl = lambda msg: None
        original_selector = ljd.Selector
        ljd.Selector = FakeSelector
        try:
            self.assertTrue(signer.sign())
        finally:
            ljd.Selector = original_selector
        self.assertEqual("https://www.epl80.net/hack.php?H_name=qiandao", signer.session.gets[0])
        self.assertNotIn("/2048/", signer.session.posts[0])

    def test_ljd_extracts_dynamic_reply_form_fields(self):
        import ljd

        class XPathList(list):
            def extract_first(self, default=None):
                if not self:
                    return default
                return self[0]

        class FakeInput:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def xpath(self, expr):
                if expr == "@name":
                    return XPathList([self.name])
                if expr == "@value":
                    return XPathList([self.value])
                return XPathList()

        class FakeForm:
            fields = {
                "atc_usesign": "1",
                "action": "reply",
                "fid": "57",
                "tid": "268",
                "verify": "dynverify",
                "_hexie": "dynhexie",
                "one_sess": "1",
            }

            def xpath(self, expr):
                if expr == "@action":
                    return XPathList(["post.php?"])
                if expr == './/input[@name]':
                    return XPathList(FakeInput(name, value) for name, value in self.fields.items())
                return XPathList()

        class HtmlSelector:
            def __init__(self, text):
                self.text = text

            def xpath(self, expr):
                if expr.startswith("//form"):
                    return XPathList([FakeForm()])
                return XPathList()

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

    def test_vika_sign_uses_single_slash_api_path(self):
        import vika

        class FakeSession:
            def __init__(self):
                self.urls = []

            def post(self, url, **kwargs):
                self.urls.append(url)
                return FakeResponse(
                    status_code=200,
                    payload={"code": 200, "data": {"count": 10, "sign_count": 1}},
                    text=json.dumps({"code": 200, "data": {"count": 10, "sign_count": 1}}),
                )

        signer = vika.VikaSign.__new__(vika.VikaSign)
        signer.base_url = "https://www.vikacg.com"
        signer.sign_path = "api/vikacg/v1/userMission"
        signer.is_sign = False
        signer.url_info = types.SimpleNamespace(hostname="www.vikacg.com")
        signer.session = FakeSession()
        signer.pwl = lambda msg: None
        self.assertTrue(signer.sign())
        self.assertEqual(
            "https://www.vikacg.com/api/vikacg/v1/userMission",
            signer.session.urls[0],
        )

    def test_yyg_resolves_anti_cc_redirect(self):
        import yyg

        challenge = (
            "<html id='anticc_redirect'><script>var cbk_var='';"
            "cbk_var='b'+cbk_var;cbk_var='a'+cbk_var;</script></html>"
        )

        class FakeSession:
            def __init__(self):
                self.urls = []
                self.requests = []

            def get(self, url, **kwargs):
                self.urls.append(url)
                self.requests.append(kwargs)
                if len(self.urls) == 1:
                    return FakeResponse(text=challenge, url="https://yyg.app/captcha")
                return FakeResponse(text="{}", payload={}, url=url)

        signer = yyg.YYGSign.__new__(yyg.YYGSign)
        signer.session = FakeSession()
        signer.pwl = lambda msg: None
        response = signer._get_with_anti_cc("https://yyg.app/captcha")
        self.assertEqual("{}", response.text)
        self.assertEqual("https://yyg.app/ab", signer.session.urls[1])
        self.assertEqual(
            "https://yyg.app/captcha",
            signer.session.requests[1]["headers"]["Referer"],
        )


if __name__ == "__main__":
    unittest.main()
