# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('new-api每日签到');
"""

from base import BaseSign


class NewApiSign(BaseSign):
    def __init__(self):
        super(NewApiSign, self).__init__("", app_name="new-api", app_key="NEWAPI")
        self.login_type = "login"
        self.exec_method = ["sign"]
        self.skip_login = False

    def pre(self):
        status = self._get_status()
        if status is None:
            return
        if status.get("turnstile_check"):
            self.pwl("Turnstile 已启用，跳过登录")
            self.skip_login = True
            return
        if not status.get("checkin_enabled", True):
            self.pwl("签到未启用，跳过登录")
            self.skip_login = True

    def _get_status(self):
        try:
            resp = self.session.get(f"{self.base_url}/api/status")
        except Exception as e:
            self.pwl(f"状态请求失败: {e}")
            return None
        if resp.status_code != 200:
            self.pwl(f"状态请求失败: HTTP {resp.status_code}")
            return None
        try:
            return resp.json()
        except Exception:
            self.pwl(f"状态解析失败: {resp.text}")
            return None

    def _login(self):
        if self.skip_login:
            return False
        payload = {"username": self.username, "password": self.password}
        try:
            resp = self.session.post(f"{self.base_url}/api/user/login", json=payload)
        except Exception as e:
            self.pwl(f"登录请求失败: {e}")
            return False
        if resp.status_code != 200:
            self.pwl(f"登录失败: HTTP {resp.status_code}")
            return False
        try:
            data = resp.json()
        except Exception:
            self.pwl(f"登录解析失败: {resp.text}")
            return False
        if not data.get("success", False):
            self.pwl(data.get("message", "登录失败"))
            return False
        if data.get("data", {}).get("require_2fa"):
            self.pwl("已启用 2FA，跳过登录")
            return False
        return True

    def sign(self):
        return True


if __name__ == "__main__":
    s = NewApiSign()
    s.run()
