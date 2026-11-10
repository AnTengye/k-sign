import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

from tests.test_newapi_sign import _install_stubs, FakeResponse


_install_stubs()

TINY_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06'
    b'\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class FakeBrowserTimeout(Exception):
    pass


def _ensure_playwright_stub():
    requests_mod = sys.modules.get("requests")
    if requests_mod is not None:
        if not hasattr(requests_mod, "__path__"):
            requests_mod.__path__ = []
        if "requests.utils" not in sys.modules:
            requests_utils = types.ModuleType("requests.utils")
            requests_utils.select_proxy = lambda url, proxies: None
            requests_utils.unquote = lambda value: value
            requests_mod.utils = requests_utils
            sys.modules["requests.utils"] = requests_utils
        elif not hasattr(sys.modules["requests.utils"], "select_proxy"):
            sys.modules["requests.utils"].select_proxy = lambda url, proxies: None

    if "playwright" not in sys.modules:
        pw_mod = types.ModuleType("playwright")
        pw_mod.__path__ = []
        sync_api_mod = types.ModuleType("playwright.sync_api")
        sync_api_mod.TimeoutError = FakeBrowserTimeout
        sync_api_mod.sync_playwright = None
        pw_mod.sync_api = sync_api_mod
        sys.modules["playwright"] = pw_mod
        sys.modules["playwright.sync_api"] = sync_api_mod
    else:
        sync_api_mod = sys.modules["playwright.sync_api"]
        if not hasattr(sync_api_mod, "TimeoutError"):
            sync_api_mod.TimeoutError = FakeBrowserTimeout


class FakeNetworkResponse:
    def __init__(self, url, body_bytes=TINY_PNG, json_data=None):
        self.url = url
        self._body = body_bytes
        self._json = json_data or {}

    def body(self):
        return self._body

    def json(self):
        return self._json


class FakePlaywrightLocator:
    def __init__(self, frame=None, bounding_box=None, evaluate_handler=None, click_handler=None, is_visible=True):
        self._frame = frame
        self._bounding_box = bounding_box or {"x": 100, "y": 200, "width": 40, "height": 40}
        self._evaluate_handler = evaluate_handler
        self._click_handler = click_handler
        self._is_visible = is_visible
        self.clicked = False

    def wait_for(self, state="visible", timeout=None):
        return None

    def is_visible(self):
        return self._is_visible

    def click(self):
        self.clicked = True
        if self._click_handler:
            self._click_handler()

    def bounding_box(self):
        return self._bounding_box

    def evaluate(self, script, arg=None):
        if self._evaluate_handler:
            return self._evaluate_handler(script, arg)
        return None

    def element_handle(self):
        return self

    def content_frame(self):
        return self._frame


class FakePlaywrightFrame:
    def __init__(self, bg_image="url('https://t.captcha.qq.com/cap_union_new_getcapbysig?id=bg1')", delayed_fg=False, always_missing=False):
        self.bg_image = bg_image
        self.delayed_fg = delayed_fg
        self.always_missing = always_missing
        self.is_fg_ready = not delayed_fg and not always_missing
        self.reload_clicked = False
        self.wait_for_function_calls = []

        self.valid_piece = {
            "image": "url('https://t.captcha.qq.com/cap_union_new_getcapbysig?id=sprite1')",
            "size": "40px 40px",
            "pos": "-10px -20px",
            "w": 40.0,
            "h": 40.0,
            "left": 20.0,
            "top": 60.0,
        }

    def locator(self, selector):
        if selector == ".tc-slider-normal":
            return FakePlaywrightLocator(bounding_box={"x": 100, "y": 200, "width": 40, "height": 40})
        elif selector == "#slideBg":
            return FakePlaywrightLocator(evaluate_handler=lambda s, a=None: self.bg_image)
        elif selector == "#reload":
            return FakePlaywrightLocator(click_handler=self._handle_reload)
        return FakePlaywrightLocator()

    def _handle_reload(self):
        self.reload_clicked = True
        self.bg_image = "url('https://t.captcha.qq.com/cap_union_new_getcapbysig?id=bg2_new')"
        self.valid_piece = {
            "image": "url('https://t.captcha.qq.com/cap_union_new_getcapbysig?id=sprite2_new')",
            "size": "40px 40px",
            "pos": "-15px -25px",
            "w": 40.0,
            "h": 40.0,
            "left": 25.0,
            "top": 65.0,
        }
        self.is_fg_ready = True

    def wait_for_function(self, script, arg=None, timeout=None):
        self.wait_for_function_calls.append({"script": script, "arg": arg})
        if self.always_missing:
            BrowserTimeout = sys.modules["playwright.sync_api"].TimeoutError
            raise BrowserTimeout("Timeout 15000ms exceeded waiting for function")
        if self.delayed_fg:
            self.is_fg_ready = True
        return True

    def evaluate(self, script, arg=None):
        if "document.querySelector('#slideBg')" in script:
            items = []
            if self.is_fg_ready:
                items.append(self.valid_piece)
                items.append({"image": "none", "size": "0px 0px", "pos": "0px 0px", "w": 0.0, "h": 0.0, "left": 0.0, "top": 0.0})
            else:
                items.append({"image": "none", "size": "0px 0px", "pos": "0px 0px", "w": 0.0, "h": 0.0, "left": 0.0, "top": 0.0})

            return {
                "bg": {
                    "image": self.bg_image,
                    "size": "680px 340px",
                    "pos": "0px 0px",
                    "w": 680.0,
                    "h": 340.0,
                    "left": 0.0,
                    "top": 0.0,
                },
                "items": items,
            }
        return None


class FakePlaywrightPage:
    def __init__(self, frame, simulate_reload_failure=False, ticket_result=None):
        self.frame = frame
        self.simulate_reload_failure = simulate_reload_failure
        self.ticket_result = ticket_result or {"ticket": "test_ticket_123", "randstr": "@test_rand_456"}
        self.response_listeners = []
        self.attempt_count = 0
        self.slide_completed = False
        self.mouse = MagicMock()
        self.mouse.up.side_effect = self._on_mouse_up

    def _on_mouse_up(self):
        self.slide_completed = True

    def set_default_timeout(self, timeout):
        pass

    def on(self, event, handler):
        if event == "response":
            self.response_listeners.append(handler)
            handler(FakeNetworkResponse("https://t.captcha.qq.com/cap_union_new_getcapbysig?id=bg1"))
            handler(FakeNetworkResponse("https://t.captcha.qq.com/cap_union_new_getcapbysig?id=sprite1"))
            handler(FakeNetworkResponse("https://t.captcha.qq.com/cap_union_new_getcapbysig?id=bg2_new"))
            handler(FakeNetworkResponse("https://t.captcha.qq.com/cap_union_new_getcapbysig?id=sprite2_new"))

    def goto(self, url, **kwargs):
        pass

    def locator(self, selector):
        if selector == "#pwDomainNoticeBtn":
            return FakePlaywrightLocator(is_visible=False)
        elif selector == "#tcaptcha_iframe_dy":
            return FakePlaywrightLocator(frame=self.frame)
        return FakePlaywrightLocator()

    def wait_for_function(self, script, arg=None, timeout=None):
        if "!!window.__signCaptchaResult" in script and timeout == 20000:
            if self.simulate_reload_failure and self.attempt_count == 0:
                self.attempt_count += 1
                self.slide_completed = False
                for listener in self.response_listeners:
                    listener(FakeNetworkResponse("https://t.captcha.qq.com/cap_union_new_verify", json_data={"errorCode": "50"}))
                BrowserTimeout = sys.modules["playwright.sync_api"].TimeoutError
                raise BrowserTimeout("Slide verification failed with errorCode 50")
            return True
        return True

    def evaluate(self, script, arg=None):
        if script == "window.__signCaptchaResult":
            if not self.slide_completed:
                return None
            return self.ticket_result
        return None

    def wait_for_timeout(self, ms):
        pass


def make_fake_playwright_context(fake_page):
    class FakePlaywrightContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        @property
        def chromium(self):
            browser = MagicMock()
            context = MagicMock()
            context.new_page.return_value = fake_page
            browser.new_context.return_value = context
            return MagicMock(launch=MagicMock(return_value=browser))

    return FakePlaywrightContext


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
                state = "今天已签到" if self.posts else "今天未签到"
                return FakeResponse(status_code=200, text=f'<td>您累计已签到：37天【<span>{state}</span>】</td>')

            def post(self, url, **kwargs):
                self.posts.append(url)
                return FakeResponse(status_code=200, text="签到成功")

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://www.epl80.net"
        signer.session = FakeSession()
        signer.pwl = lambda msg: None
        signer._sign_state = lambda text: "今天已签到" in text
        self.assertTrue(signer.sign())
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

    def test_ljd_tencent_ticket_waits_for_delayed_fg_item(self):
        """验证 _tencent_ticket 显式等待延迟渲染的 .tc-fg-item 并成功提取拼图，消除 StopIteration"""
        import ljd
        _ensure_playwright_stub()

        fake_frame = FakePlaywrightFrame(delayed_fg=True)
        fake_page = FakePlaywrightPage(fake_frame)
        context_cls = make_fake_playwright_context(fake_page)

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://6gmz.735-yj3bfjz.shop"
        signer.url_info = types.SimpleNamespace(hostname="6gmz.735-yj3bfjz.shop")
        signer.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        signer.session = types.SimpleNamespace(
            headers={}, cookies=[],
            merge_environment_settings=lambda *args, **kwargs: {"proxies": {}}
        )
        logs = []
        signer.pwl = lambda msg: logs.append(msg)
        signer._tencent_slider_distance = MagicMock(return_value=120.0)

        with unittest.mock.patch("playwright.sync_api.sync_playwright", context_cls):
            ticket = signer._tencent_ticket()

        self.assertIsNotNone(ticket)
        self.assertEqual("test_ticket_123", ticket["ticket"])
        self.assertEqual("@test_rand_456", ticket["randstr"])

        self.assertTrue(len(fake_frame.wait_for_function_calls) >= 1)
        wait_script = fake_frame.wait_for_function_calls[0]["script"]
        self.assertIn(".tc-fg-item", wait_script)
        self.assertIn("#slideBg", wait_script)
        self.assertIn("backgroundImage", wait_script)
        self.assertFalse(any("StopIteration" in log for log in logs))

    def test_ljd_tencent_ticket_reload_waits_for_new_challenge(self):
        """验证滑动验证失败 (errorCode 50) 时触发 #reload，等待新背景和新拼图块就绪并成功重试"""
        import ljd
        _ensure_playwright_stub()

        fake_frame = FakePlaywrightFrame(delayed_fg=False)
        fake_page = FakePlaywrightPage(
            fake_frame,
            simulate_reload_failure=True,
            ticket_result={"ticket": "reloaded_ticket_888", "randstr": "@reloaded_rand_999"},
        )
        context_cls = make_fake_playwright_context(fake_page)

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://6gmz.735-yj3bfjz.shop"
        signer.url_info = types.SimpleNamespace(hostname="6gmz.735-yj3bfjz.shop")
        signer.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        signer.session = types.SimpleNamespace(
            headers={}, cookies=[],
            merge_environment_settings=lambda *args, **kwargs: {"proxies": {}}
        )
        logs = []
        signer.pwl = lambda msg: logs.append(msg)
        signer._tencent_slider_distance = MagicMock(return_value=120.0)

        with unittest.mock.patch("playwright.sync_api.sync_playwright", context_cls):
            ticket = signer._tencent_ticket()

        self.assertTrue(fake_frame.reload_clicked)

        reload_wait_calls = [c for c in fake_frame.wait_for_function_calls if c["arg"] is not None]
        self.assertTrue(len(reload_wait_calls) >= 1)
        self.assertEqual("url('https://t.captcha.qq.com/cap_union_new_getcapbysig?id=bg1')", reload_wait_calls[0]["arg"])
        self.assertIn(".tc-fg-item", reload_wait_calls[0]["script"])

        self.assertIsNotNone(ticket)
        self.assertEqual("reloaded_ticket_888", ticket["ticket"])
        self.assertFalse(any("StopIteration" in log for log in logs))

    def test_ljd_tencent_ticket_handles_missing_piece_without_stop_iteration(self):
        """验证 DOM 持续缺失有效拼图块或等待超时时，安全受控退出返回 None，绝不抛出或打印 StopIteration"""
        import ljd
        _ensure_playwright_stub()

        fake_frame = FakePlaywrightFrame(always_missing=True)
        fake_page = FakePlaywrightPage(fake_frame)
        context_cls = make_fake_playwright_context(fake_page)

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://6gmz.735-yj3bfjz.shop"
        signer.url_info = types.SimpleNamespace(hostname="6gmz.735-yj3bfjz.shop")
        signer.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        signer.session = types.SimpleNamespace(
            headers={}, cookies=[],
            merge_environment_settings=lambda *args, **kwargs: {"proxies": {}}
        )
        logs = []
        signer.pwl = lambda msg: logs.append(msg)

        with unittest.mock.patch("playwright.sync_api.sync_playwright", context_cls):
            ticket = signer._tencent_ticket()

        self.assertIsNone(ticket)
        self.assertTrue(any("腾讯滑块处理失败" in log for log in logs))
        self.assertFalse(any("StopIteration" in log for log in logs))

    def test_ljd_slider_distance_raises_value_error_on_invalid_meta(self):
        """验证 _tencent_slider_distance 在传入缺少方形有效拼图块的元数据时抛出 ValueError 而非 StopIteration"""
        import ljd

        meta_empty = {"bg": {"w": 680.0}, "items": []}
        with self.assertRaises(ValueError) as cm:
            ljd.LJDSign._tencent_slider_distance(meta_empty, TINY_PNG, TINY_PNG)
        self.assertNotIsInstance(cm.exception, StopIteration)

        meta_rect = {
            "bg": {"w": 680.0},
            "items": [{"image": "url('x.png')", "w": 40.0, "h": 80.0}],
        }
        with self.assertRaises(ValueError) as cm:
            ljd.LJDSign._tencent_slider_distance(meta_rect, TINY_PNG, TINY_PNG)
        self.assertNotIsInstance(cm.exception, StopIteration)

        meta_no_img = {
            "bg": {"w": 680.0},
            "items": [{"image": "none", "w": 40.0, "h": 40.0}],
        }
        with self.assertRaises(ValueError) as cm:
            ljd.LJDSign._tencent_slider_distance(meta_no_img, TINY_PNG, TINY_PNG)
        self.assertNotIsInstance(cm.exception, StopIteration)


if __name__ == "__main__":
    unittest.main()
