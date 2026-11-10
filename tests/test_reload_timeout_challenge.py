# -*- coding:utf-8 -*-
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from tests.test_site_repairs import (
    _ensure_playwright_stub,
    FakePlaywrightFrame,
    FakePlaywrightLocator,
    FakePlaywrightPage,
    FakeNetworkResponse,
    make_fake_playwright_context,
)

_ensure_playwright_stub()
import ljd
from playwright.sync_api import TimeoutError as BrowserTimeout


class ReloadTimeoutEmpiricalChallengeTests(unittest.TestCase):
    """实证对抗性测试：验证换题重试与各类超时/异常场景下的受控退避与资源安全"""

    def setUp(self):
        self.signer = ljd.LJDSign.__new__(ljd.LJDSign)
        self.signer.base_url = "https://6gmz.735-yj3bfjz.shop"
        self.signer.url_info = types.SimpleNamespace(hostname="6gmz.735-yj3bfjz.shop")
        self.signer.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        self.signer.session = types.SimpleNamespace(
            headers={}, cookies=[],
            merge_environment_settings=lambda *args, **kwargs: {"proxies": {}}
        )
        self.logs = []
        self.signer.pwl = lambda msg: self.logs.append(msg)
        self.signer._tencent_slider_distance = MagicMock(return_value=120.0)

    def test_reload_timeout_handles_cleanly_and_closes_browser(self):
        """场景 1：errorCode 50 触发 #reload 后，新题渲染等待发生 TimeoutError，受控退出且绝不泄露 StopIteration"""
        class ReloadTimeoutFrame(FakePlaywrightFrame):
            def wait_for_function(self, script, arg=None, timeout=None):
                if arg is not None:
                    raise BrowserTimeout("Timed out waiting 15000ms for new captcha background")
                return super().wait_for_function(script, arg=arg, timeout=timeout)

        fake_frame = ReloadTimeoutFrame(delayed_fg=False)
        fake_page = FakePlaywrightPage(
            fake_frame,
            simulate_reload_failure=True,
            ticket_result={"ticket": "should_not_reach", "randstr": "@rand"}
        )

        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = fake_page
        mock_browser.new_context.return_value = mock_context

        class FakePlaywrightContext:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            @property
            def chromium(self):
                m = MagicMock()
                m.launch.return_value = mock_browser
                return m

        with patch("playwright.sync_api.sync_playwright", FakePlaywrightContext):
            ticket = self.signer._tencent_ticket()

        self.assertIsNone(ticket, "发生换题超时后必须返回 None")
        mock_browser.close.assert_called_once()
        self.assertTrue(fake_frame.reload_clicked, "必须已点击 #reload 换题按钮")
        self.assertTrue(any("腾讯滑块未通过，错误码：50" in log for log in self.logs))
        self.assertTrue(any("腾讯滑块处理失败" in log for log in self.logs))
        self.assertFalse(any("StopIteration" in log for log in self.logs), "绝不能在日志中出现 StopIteration")

    def test_reload_non_50_error_skips_reload(self):
        """场景 2：滑块验证未通过且 errorCode 非 50（如 100），不应触发 reload，直接返回 None"""
        class Non50Page(FakePlaywrightPage):
            def wait_for_function(self, script, arg=None, timeout=None):
                if "!!window.__signCaptchaResult" in script and timeout == 20000:
                    for listener in self.response_listeners:
                        listener(FakeNetworkResponse("https://t.captcha.qq.com/cap_union_new_verify", json_data={"errorCode": "100"}))
                    raise BrowserTimeout("Slide verification failed with errorCode 100")
                return True

        fake_frame = FakePlaywrightFrame(delayed_fg=False)
        fake_page = Non50Page(fake_frame)
        context_cls = make_fake_playwright_context(fake_page)

        with patch("playwright.sync_api.sync_playwright", context_cls):
            ticket = self.signer._tencent_ticket()

        self.assertIsNone(ticket)
        self.assertFalse(fake_frame.reload_clicked, "非 50 错误码不应触发 #reload")
        self.assertTrue(any("腾讯滑块未通过，错误码：100" in log for log in self.logs))
        self.assertFalse(any("StopIteration" in log for log in self.logs))

    def test_reload_attempt_limit_prevents_infinite_loop(self):
        """场景 3：两次 attempt 均返回 50 时，仅在 attempt==0 触发换题，attempt==1 必须正常返回 None，杜绝无限重试"""
        clicks = []

        class Persistent50Frame(FakePlaywrightFrame):
            def _handle_reload(self):
                super()._handle_reload()
                clicks.append(1)

        class Persistent50Page(FakePlaywrightPage):
            def evaluate(self, script, arg=None):
                return None

            def wait_for_function(self, script, arg=None, timeout=None):
                if "!!window.__signCaptchaResult" in script and timeout == 20000:
                    for listener in self.response_listeners:
                        listener(FakeNetworkResponse("https://t.captcha.qq.com/cap_union_new_verify", json_data={"errorCode": "50"}))
                    raise BrowserTimeout("Always errorCode 50")
                return True

        fake_frame = Persistent50Frame(delayed_fg=False)
        fake_page = Persistent50Page(fake_frame)
        context_cls = make_fake_playwright_context(fake_page)

        with patch("playwright.sync_api.sync_playwright", context_cls):
            ticket = self.signer._tencent_ticket()

        self.assertIsNone(ticket)
        self.assertEqual(1, len(clicks), "最多只能触发 1 次 #reload 换题")
        self.assertEqual(2, self.logs.count("腾讯滑块未通过，错误码：50"))
        self.assertFalse(any("StopIteration" in log for log in self.logs))

    def test_reload_click_exception_handled_safely(self):
        """场景 4：点击 #reload 时发生异常（如元素脱附、不可交互），能够安全被外层捕获并关闭浏览器"""
        class FailingReloadLocator(FakePlaywrightLocator):
            def click(self):
                raise Exception("Element is detached from DOM")

        class FailingReloadFrame(FakePlaywrightFrame):
            def locator(self, selector):
                if selector == "#reload":
                    return FailingReloadLocator()
                return super().locator(selector)

        fake_frame = FailingReloadFrame(delayed_fg=False)
        fake_page = FakePlaywrightPage(
            fake_frame,
            simulate_reload_failure=True
        )

        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = fake_page
        mock_browser.new_context.return_value = mock_context

        class FakePlaywrightContext:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            @property
            def chromium(self):
                m = MagicMock()
                m.launch.return_value = mock_browser
                return m

        with patch("playwright.sync_api.sync_playwright", FakePlaywrightContext):
            ticket = self.signer._tencent_ticket()

        self.assertIsNone(ticket)
        mock_browser.close.assert_called_once()
        self.assertTrue(any("腾讯滑块处理失败（Exception）" in log for log in self.logs))
        self.assertFalse(any("StopIteration" in log for log in self.logs))


if __name__ == "__main__":
    unittest.main()
