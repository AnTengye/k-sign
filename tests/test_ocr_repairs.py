import base64
import html
import io
import json
import os
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock, patch
from urllib.parse import urlparse

import requests

from base import BaseSign


class RuntimeRepairTests(unittest.TestCase):
    @classmethod
    def _moxing_page(cls, signed=False):
        props = {"auth": {"user": {"id": 1}}, "is_checked_in": signed}
        data = html.escape(json.dumps({"props": props}), quote=True)
        return cls._response(f'<div data-page="{data}"></div>')

    @staticmethod
    def _response(body, url="https://example.test/page"):
        response = requests.Response()
        response.status_code = 200
        response._content = body.encode()
        response.encoding = "utf-8"
        response.url = url
        return response

    def test_sijis_uses_native_login_form_when_image_captcha_is_disabled(self):
        import sijis

        signer = sijis.SiJiSSign.__new__(sijis.SiJiSSign)
        signer.base_url = "https://example.test"
        signer.username, signer.password = "fixture", "fixture"
        signer.login_resp_success = r"succeedhandle_login\('(.*?)'"
        signer.pwl = Mock()
        signer._code_login = Mock(side_effect=AssertionError("Captcha is disabled on this login form"))
        signer.session = Mock()
        form = '<form action="member.php?mod=logging&amp;loginhash=current"><input name="formhash" value="fixture"><input name="password"></form>'
        signer.session.get.return_value = self._response(form, "https://example.test/member.php")
        signer.session.post.return_value = self._response("<root><![CDATA[<script>succeedhandle_login('/forum.php', 'ok');</script>]]></root>")
        self.assertTrue(signer._login())
        signer._code_login.assert_not_called()
        self.assertIn("loginhash=current", signer.session.post.call_args.args[0])
        self.assertEqual("fixture", signer.session.post.call_args.kwargs["data"]["formhash"])
        self.assertEqual("https://example.test/forum.php", signer.session.get.call_args.args[0])

        signer._code_login = Mock(return_value=True)
        signer.session.get.return_value = self._response("<script>updateseccode('fixture');</script>")
        self.assertTrue(signer._login())
        signer._code_login.assert_called_once_with()

    def test_sijis_requires_real_signed_marker_and_post_sign_readback(self):
        import sijis

        signer = sijis.SiJiSSign.__new__(sijis.SiJiSSign)
        signer.base_url = "https://example.test"
        signer.index_path = "k_misign-sign.html"
        signer.pwl = Mock()
        signer._get_sign = Mock(return_value=True)
        signer.session = Mock()
        signer.session.get.return_value = self._response("<html>今日签到排行榜<style>.btnvisted{}</style></html>")
        self.assertFalse(signer.sign())
        signer._get_sign.assert_not_called()
        signed = self._response('<span class="btn btnvisted"></span>')
        signer.session.get.return_value = signed
        self.assertTrue(signer.sign())
        signer._get_sign.assert_not_called()
        unsigned = self._response('<input name="formhash" value="fixture">')
        for confirmed in (False, True):
            signer.session.get.side_effect = [unsigned, signed if confirmed else unsigned]
            self.assertEqual(confirmed, signer.sign())

    def test_ljd_reports_email_and_captcha_requirements_without_false_success(self):
        import ljd

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://example.test"
        signer.pwl = Mock()
        signer.session = Mock()
        signer.session.get.return_value = self._response(self._ljd_page())
        for message, expected in (("必须绑定邮箱后才能签到", "绑定邮箱"), ("验证码错误", "腾讯滑块"),
                                  ("今日未回复任何帖子，无法签到！", "今日先回复")):
            signer.session.post.return_value = self._response(f"<html>{message} 今日已签到排行榜</html>")
            self.assertFalse(signer.sign())
            self.assertIn(expected, signer.pwl.call_args.args[0])

    @staticmethod
    def _ljd_page(signed=False, captcha=False):
        state = "今天已签到" if signed else "今天未签到"
        return (f'<table><tr><td>您累计已签到：<b>37</b>天【<span>{state}</span>】'
                '今日已签到：<b>35000</b>人</td></tr><tr><td>今天已签到</td></tr></table>'
                + ('<script>qdCaptchaStart("pc")</script>' if captcha else ''))

    def test_ljd_uses_account_state_and_skips_browser_for_already_signed(self):
        import ljd

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://example.test"
        signer.session, signer.pwl, signer._tencent_ticket = Mock(), Mock(), Mock()
        self.assertIsNone(signer._sign_state('<td>今日已签到排行榜：今天已签到</td>'))
        self.assertFalse(signer._sign_state(self._ljd_page()))
        signer.session.get.return_value = self._response(self._ljd_page(signed=True, captcha=True))
        self.assertTrue(signer.sign())
        signer._tencent_ticket.assert_not_called()
        signer.session.post.assert_not_called()

    def test_ljd_stops_before_post_for_missing_or_fallback_captcha_ticket(self):
        import ljd

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://example.test"
        signer.session, signer.pwl, signer._tencent_ticket = Mock(), Mock(), Mock()
        signer.session.get.return_value = self._response(self._ljd_page(captcha=True))
        for result in (None, {}, {"ticket": "fixture", "randstr": ""},
                       {"ticket": "trerror_fixture", "randstr": "fixture"}):
            signer._tencent_ticket.return_value = result
            self.assertFalse(signer.sign())
        signer.session.post.assert_not_called()

    def test_ljd_submits_current_ticket_once_and_requires_state_readback(self):
        import ljd

        signer = ljd.LJDSign.__new__(ljd.LJDSign)
        signer.base_url = "https://example.test"
        signer.session, signer.pwl = Mock(), Mock()
        signer._tencent_ticket = Mock(return_value={"ticket": "fixture-ticket", "randstr": "fixture-rand"})
        signer.session.post.return_value = self._response("签到成功！今日已签到排行榜")
        for signed in (False, True):
            signer.session.get.side_effect = [self._response(self._ljd_page(captcha=True)), self._response(self._ljd_page(signed=signed))]
            signer.session.post.reset_mock()
            self.assertEqual(signed, signer.sign())
            signer.session.post.assert_called_once()
            data = signer.session.post.call_args.kwargs["data"]
            self.assertEqual(("fixture-ticket", "fixture-rand"), (data["hycode"], data["hyrandstr"]))

    def test_ljd_slider_matches_sprite_crop_and_converts_to_browser_distance(self):
        import ljd
        import numpy as np
        from PIL import Image

        random = np.random.default_rng(42)
        target = random.integers(0, 256, (40, 40, 3), dtype=np.uint8)
        background = np.zeros((140, 300, 3), dtype=np.uint8)
        background[40:80, 160:200] = target
        sprite = np.zeros((100, 200, 3), dtype=np.uint8)
        sprite[16:56, 12:52] = target
        buffers = []
        for pixels in (background, sprite):
            buf = io.BytesIO()
            Image.fromarray(pixels).save(buf, format="PNG")
            buffers.append(buf.getvalue())
        piece = {"image": "fixture", "size": "100px 50px", "pos": "-6px -8px", "w": 20, "h": 20, "left": 10, "top": 20}
        meta = {"bg": {"w": 150}, "items": [piece]}
        self.assertAlmostEqual(70, ljd.LJDSign._tencent_slider_distance(meta, *buffers), delta=1)
        piece["top"] = 60
        with self.assertRaises(ValueError):
            ljd.LJDSign._tencent_slider_distance(meta, *buffers)

    def test_djgame_claims_rewards_in_prerequisite_order_and_stops_on_database_error(self):
        import djgame

        signer = djgame.DJGameSign.__new__(djgame.DJGameSign)
        signer.base_url = "https://example.test"
        signer.url_info = urlparse(signer.base_url)
        signer.pwl = Mock()
        signer.session = Mock()
        signer.session.get.return_value = self._response('<div id="messagetext"><p>任務已成功完成</p></div>')
        self.assertTrue(signer.sign())
        operations = [call.args[0].split("&do=")[1] for call in signer.session.get.call_args_list]
        self.assertEqual(["apply&id=1", "draw&id=1", "apply&id=5", "draw&id=5", "apply&id=6", "draw&id=6"], operations)
        self.assertFalse(signer._task_succeeded("申請此任務需要先完成另一個任務"))
        self.assertFalse(signer._task_succeeded("任務尚未完成"))
        signer.session.reset_mock()
        signer.session.get.return_value = self._response("<title>Database Error</title>")
        self.assertFalse(signer.sign())
        self.assertEqual(1, signer.session.get.call_count)

    def test_laowang_checks_signed_state_after_ambiguous_post_response(self):
        import laowang

        signer = laowang.LaoWangSSign.__new__(laowang.LaoWangSSign)
        signer.base_url = "https://example.test"
        signer.url_info = urlparse(signer.base_url)
        signer.pwl = Mock()
        signer.fetch_index = Mock(return_value="fixture_ok")
        signer.session = Mock()
        initial = '<div id="wp"><div></div><div><div><div><a href="captcha">签到</a></div></div></div></div>'
        signer.session.get.side_effect = [self._response(initial), self._response('<form id="v2_captcha_form" action="/submit"></form>'), self._response('<span class="btn btnvisted">今日已签到</span>')]
        signer.session.post.return_value = self._response("<html>Redirecting...</html>")
        self.assertTrue(signer.sign())
        signer.session.post.assert_called_once()
        self.assertEqual(3, signer.session.get.call_count)

    def test_titi_login_reads_checkin_state_without_loading_mission_history(self):
        import titi

        signer = titi.TitiSign.__new__(titi.TitiSign)
        signer.base_url = "https://example.test"
        signer.url_info = urlparse(signer.base_url)
        signer.username, signer.password = "fixture", "fixture"
        signer.session = Mock()
        signer.session.headers = {}
        signer.session.post.return_value = types.SimpleNamespace(status_code=200, text='{"name":"fixture","token":"fixture-token","credit":10}')
        signer.pwl = Mock()
        signer.get_info = Mock(return_value=True)
        signer.get_mission = Mock(side_effect=AssertionError("Mission history is not needed for check-in"))
        self.assertTrue(signer._login())
        signer.get_info.assert_called_once_with()
        signer.get_mission.assert_not_called()

    def test_splus_reads_verifyhash_from_current_task_page(self):
        import splus

        signer = splus.SouthPlusSign.__new__(splus.SouthPlusSign)
        signer.base_url = "https://example.test"
        signer.url_info = urlparse(signer.base_url)
        signer.pwl = Mock()
        signer.session = Mock()
        signer.session.get.return_value = types.SimpleNamespace(status_code=200, text="<script>var imgpath='images';var verifyhash = 'fixture-hash';</script>")
        self.assertTrue(signer.fetch_sign())
        self.assertEqual("fixture-hash", signer.task_verify)

    def test_laowang_submits_current_post_protocol_and_rejects_html_as_token(self):
        import laowang

        signer = laowang.LaoWangSSign.__new__(laowang.LaoWangSSign)
        signer.base_url = "https://example.test"
        signer.login_t = "123"
        signer.pwl = Mock()
        signer.session = Mock()
        signer.session.get.side_effect = [types.SimpleNamespace(status_code=200, text="var hmacSecret='fixture-public-key';"), types.SimpleNamespace(status_code=200, content=b"image")]
        signer.session.post.return_value = types.SimpleNamespace(status_code=200, text="fixture_ok")
        with patch.object(laowang.slidecode, "get_slide_width", return_value=42), patch.object(laowang.time, "sleep"):
            self.assertEqual("fixture_ok", signer.fetch_index())
        call = signer.session.post.call_args
        self.assertEqual("https://example.test/captcha/check.php", call.args[0])
        self.assertEqual({"tn_r", "track", "ts", "sign"}, set(call.kwargs["data"]))
        self.assertEqual("42.00", call.kwargs["data"]["tn_r"])
        signer.session.get.side_effect = None
        signer.session.get.return_value = types.SimpleNamespace(status_code=200, content=b"image")
        signer.session.post.return_value = types.SimpleNamespace(status_code=200, text="<html>Access denied</html>")
        with patch.object(laowang.slidecode, "get_slide_width", return_value=42), patch.object(laowang.time, "sleep"):
            self.assertEqual("", signer.fetch_index(times=1))

    def test_html_error_page_does_not_count_as_successful_checkin(self):
        signer = BaseSign.__new__(BaseSign)
        signer.base_url = "https://example.test"
        signer.sign_path = "sign?formhash=%s"
        signer.pwl = Mock()
        signer.session = Mock()
        for status, body in [(200, "<html>Please log in</html>"), (503, "<root/>"), (200, "")]:
            signer.session.get.return_value = types.SimpleNamespace(status_code=status, text=body)
            self.assertFalse(signer._get_sign("fixture"))
        signer.session.get.return_value = types.SimpleNamespace(status_code=200, text="<root><![CDATA[签到成功]]></root>")
        self.assertTrue(signer._get_sign("fixture"))

    def test_feixue_returns_503_without_sleeping_for_retry_after(self):
        import fxacg

        class Handler(BaseHTTPRequestHandler):
            calls = 0

            def do_GET(self):
                type(self).calls += 1
                self.send_response(503)
                self.send_header("Retry-After", "3600")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(os.environ, {"SIGN_UP_FXACG": "fixture|fixture", "SIGN_PROXY_FXACG": "false", "SIGN_URL_FXACG": f"http://127.0.0.1:{server.server_port}"}, clear=True):
                signer = fxacg.FXAcgSign()
            signer.pwl = Mock()
            with patch("requests.packages.urllib3.util.retry.time.sleep", side_effect=AssertionError("Retry-After must not block the task")):
                self.assertFalse(signer.sign())
            self.assertEqual(1, Handler.calls)
            self.assertIn("3600", signer.pwl.call_args.args[0])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_yyg_uses_redirected_origin_for_login_and_decodes_image(self):
        import yyg

        signer = yyg.YYGSign.__new__(yyg.YYGSign)
        signer.base_url = "https://yyg.app"
        signer.url_info = urlparse(signer.base_url)
        signer.username, signer.password = "fixture", "fixture"
        signer.pwl = Mock()
        signer._get_with_anti_cc = Mock(return_value=types.SimpleNamespace(url="https://yyg2.app/"))
        signer.code = Mock(return_value="1234")
        signer.session = Mock()
        signer.session.post.return_value = types.SimpleNamespace(status_code=200, json=lambda: {"msg": "登录成功"})
        self.assertTrue(signer.login())
        self.assertEqual("https://yyg2.app/wp-admin/admin-ajax.php", signer.session.post.call_args.args[0])
        self.assertEqual("yyg2.app", signer.url_info.hostname)

        del signer.code
        image_bytes = b"fixture image bytes"
        image_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
        signer._get_with_anti_cc.return_value = types.SimpleNamespace(status_code=200, json=lambda: {"img": image_uri})
        with patch.object(yyg, "handle_yzm", return_value="1234") as recognize:
            self.assertEqual("1234", signer.code())
        recognize.assert_called_once_with(image_bytes, t="img")

    def test_akile_normalizes_frontend_and_legacy_api_urls(self):
        import akile

        for url in ["https://akile.ai", "https://api.akile.io"]:
            with patch.dict(os.environ, {"SIGN_UP_AKILE": "fixture|fixture", "SIGN_URL_AKILE": url}, clear=True):
                signer = akile.AkileSign()
            self.assertEqual("https://api.akile.ai", signer.base_url)
            self.assertEqual("api.akile.ai", signer.url_info.hostname)

    def test_moxing_fetches_csrf_cookie_before_first_api_post(self):
        import moxing

        signer = moxing.MoxingSign.__new__(moxing.MoxingSign)
        signer.base_url = "https://moxing.app"
        signer.url_info = urlparse(signer.base_url)
        signer.pwl = Mock()
        signer.session = Mock()
        signer.session.cookies = {"XSRF-TOKEN": "encoded%2Fcsrf"}
        signer.session.get.return_value = self._moxing_page()
        signer._captcha = Mock(return_value={"captcha": "ABCD", "captcha_key": "fixture"})
        signer.session.post.return_value = types.SimpleNamespace(status_code=401, json=lambda: {"message": "Unauthenticated"})
        self.assertFalse(signer.sign_v2())
        calls = signer.session.method_calls
        first_post = next(i for i, call in enumerate(calls) if call[0] == "post")
        self.assertTrue(any(call.args[0].endswith("/forum/sign") for call in calls[:first_post] if call[0] == "get"))
        self.assertEqual("encoded/csrf", signer.session.post.call_args.kwargs["headers"]["X-XSRF-TOKEN"])
        self.assertTrue(signer.session.post.call_args.args[0].endswith("/api/forum/check-in/sign"))

    def test_moxing_uses_forum_2_login_and_handles_current_image_payload(self):
        import moxing

        signer = moxing.MoxingSign.__new__(moxing.MoxingSign)
        signer.base_url = "https://moxing.app"
        signer.url_info = urlparse(signer.base_url)
        signer.username, signer.password = "fixture", "fixture"
        signer.pwl = Mock()
        signer.session = Mock()
        signer.session.cookies = {"XSRF-TOKEN": "fixture-csrf"}
        image = b"fixture image"
        captcha = types.SimpleNamespace(status_code=200, json=lambda: {"key": "fixture-key", "img": "data:image/png;base64," + base64.b64encode(image).decode()})
        signer.session.get.side_effect = [self._moxing_page(), captcha, self._moxing_page()]
        signer.session.post.return_value = types.SimpleNamespace(status_code=200, json=lambda: {"message": "登录成功"})
        with patch.object(moxing, "handle_yzm", return_value="ABCD") as recognize:
            self.assertTrue(signer._login())
        recognize.assert_called_once_with(image, t="img")
        self.assertEqual("https://mox.moxing.app/api/forum/login", signer.session.post.call_args.args[0])
        self.assertEqual("ABCD", signer.session.post.call_args.kwargs["json"]["captcha"])
        signer.session.get.side_effect = [self._moxing_page(), captcha]
        signer.session.post.return_value = types.SimpleNamespace(status_code=200, json=lambda: {"code": "TWO_FACTOR_REQUIRED"})
        with patch.object(moxing, "handle_yzm", return_value="ABCD"):
            self.assertFalse(signer._login())

    def test_moxing_skips_signed_day_and_requires_state_readback_after_post(self):
        import moxing

        signer = moxing.MoxingSign.__new__(moxing.MoxingSign)
        signer.base_url = "https://moxing.app"
        signer.url_info = urlparse(signer.base_url)
        signer.pwl = Mock()
        signer.session = Mock()
        signer.session.cookies = {"XSRF-TOKEN": "fixture-csrf"}
        signer._captcha = Mock(return_value={"captcha": "ABCD", "captcha_key": "fixture"})
        signer.session.get.return_value = self._moxing_page(signed=True)
        self.assertTrue(signer.sign_v2())
        signer.session.post.assert_not_called()

        signer.session.post.return_value = types.SimpleNamespace(status_code=200, json=lambda: {"success": True, "data": {"message": "签到奖励"}})
        for confirmed in (False, True):
            signer.session.get.side_effect = [self._moxing_page(), self._moxing_page(signed=confirmed)]
            self.assertEqual(confirmed, signer.sign_v2())

        signer.session.get.side_effect = None
        signer.session.get.return_value = self._response('<html>Login required</html>')
        signer.session.post.reset_mock()
        self.assertFalse(signer.sign_v2())
        signer.session.post.assert_not_called()

    def test_vika_reads_both_seconds_and_milliseconds_without_repeating_checkin(self):
        import datetime
        import vika

        signer = vika.VikaSign.__new__(vika.VikaSign)
        signer.base_url = "https://example.test"
        signer.url_info = urlparse(signer.base_url)
        signer.is_sign = False
        signer.pwl = Mock()
        signer.session = Mock()
        now = int(datetime.datetime.now().timestamp())
        for timestamp in (now, now * 1000):
            payload = {"code": 200, "data": {"basic": {"name": "fixture"}, "credit": {"count": 0, "sign_time": timestamp}}}
            import json
            signer.session.post.return_value = types.SimpleNamespace(status_code=200, text=json.dumps(payload))
            self.assertTrue(signer.get_info())
            self.assertTrue(signer.is_sign)

    def test_ocr_cache_preserves_custom_models_and_numeric_ctc_repeats(self):
        import gifcode

        gifcode._get_ocr.cache_clear()
        try:
            with patch.object(gifcode.ddddocr, "DdddOcr") as factory:
                factory.return_value.classification.return_value = "ABCD"
                self.assertEqual("ABCD", gifcode.recogition2(b"image", "charset.json", "model.onnx"))
                self.assertEqual("ABCD", gifcode.recogition2(b"image", "charset.json", "model.onnx"))
                factory.assert_called_once_with(show_ad=False, import_onnx_path="model.onnx", charsets_path="charset.json")
                factory.return_value.classification.return_value = {"charsets": ["", "1", "2"], "probability": [[0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]]}
                self.assertEqual("112", gifcode.recogition2(b"image", digits=True))
                factory.return_value.set_ranges.assert_called_once_with("0123456789")
                self.assertEqual(2, factory.call_count)
        finally:
            gifcode._get_ocr.cache_clear()


if __name__ == "__main__":
    unittest.main()
