# -*- coding:utf-8 -*-
"""
cron: 0 18 8 * * *
new Env('薄荷公益站签到');

环境变量：
  SIGN_COOKIE_X666 - 浏览器 Cookie，例如 auth_token=xxx
  SIGN_URL_X666    - 可选，默认 https://up.x666.me
"""
import os
import sys
import types
from http.cookies import CookieError, SimpleCookie

# 该站点不使用验证码。青龙的轻量环境若未安装 OCR 原生依赖，避免因
# base.py 顶层导入 gifcode 而阻止本脚本启动；仅在依赖不可用时降级。
try:
    import gifcode  # noqa: F401
except (ImportError, OSError):
    gifcode_stub = types.ModuleType("gifcode")
    gifcode_stub.handle_yzm = lambda *args, **kwargs: ""
    sys.modules["gifcode"] = gifcode_stub

from base import BaseSign


class X666Sign(BaseSign):
    def __init__(self):
        env_key = "SIGN_UP_X666"
        original_up = os.environ.get(env_key)
        if original_up is None:
            os.environ[env_key] = "cookie-user|cookie-auth"
        try:
            super(X666Sign, self).__init__(
                "https://up.x666.me", app_name="薄荷公益站", app_key="X666"
            )
        finally:
            if original_up is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = original_up
        self.exec_method = ["sign"]

    def login(self) -> bool:
        cookie_value = os.getenv("SIGN_COOKIE_X666", "").strip()
        if not cookie_value:
            self.pwl("未设置 Cookie，请添加变量 SIGN_COOKIE_X666")
            return False

        # 既支持完整 Cookie，也支持只填写 auth_token 的值。
        if "=" not in cookie_value:
            cookie_value = f"auth_token={cookie_value}"
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_value)
        except CookieError as exc:
            self.pwl(f"Cookie 格式无效: {exc}")
            return False
        cookies = {key: morsel.value for key, morsel in cookie.items()}
        if "auth_token" not in cookies:
            self.pwl("Cookie 中缺少 auth_token")
            return False
        self.session.cookies.update(cookies)
        self.session.headers.update({"Accept": "*/*", "Referer": f"{self.base_url}/"})

        data = self._request_json("get", "/api/user/info", "登录验证")
        if not data or not data.get("success"):
            self.pwl((data or {}).get("message", "Cookie 已过期或登录验证失败"))
            return False
        self.pwl(f"登录成功：{data.get('username', '未知用户')}")
        return True

    def sign(self) -> bool:
        status = self._request_json("get", "/api/checkin/status", "签到状态")
        if not status or not status.get("success"):
            self.pwl((status or {}).get("message", "获取签到状态失败"))
            return False
        if status.get("can_spin") is False:
            self.pwl("今日已签到")
            self._log_status(status)
            return True

        result = self._request_json("post", "/api/checkin/spin", "签到")
        if not result:
            return False
        if not result.get("success"):
            message = result.get("message", "签到失败")
            self.pwl(message)
            return "已签到" in message

        self.pwl(f"签到成功：{result.get('label', '获得签到奖励')}")
        self._log_status(result)
        return True

    def _request_json(self, method: str, path: str, action: str):
        try:
            response = self.session.request(method, f"{self.base_url}{path}")
        except Exception as exc:
            self.pwl(f"{action}请求失败: {exc}")
            return None
        if response.status_code != 200:
            self.pwl(f"{action}请求失败: HTTP {response.status_code}")
            return None
        try:
            return response.json()
        except ValueError:
            self.pwl(f"{action}响应解析失败")
            return None

    def _log_status(self, data):
        fields = (
            ("quota", "获得额度"),
            ("new_balance", "当前余额"),
            ("streak_days", "连续签到"),
            ("today_rank", "今日排名"),
        )
        for key, label in fields:
            if data.get(key) is not None:
                self.pwl(f"{label}：{data[key]}")


if __name__ == "__main__":
    X666Sign().run()
