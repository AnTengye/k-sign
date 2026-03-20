# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('new-api每日签到');

Multi-site support via environment variable naming convention:
  SIGN_URL_NEWAPI_<SUFFIX>  - Site URL (e.g. SIGN_URL_NEWAPI_A, SIGN_URL_NEWAPI_B)
  SIGN_UP_NEWAPI_<SUFFIX>   - Username/password (e.g. SIGN_UP_NEWAPI_A)

Backward compatible: plain SIGN_URL_NEWAPI / SIGN_UP_NEWAPI still works.
"""

import os

from base import BaseSign


class NewApiSign(BaseSign):
    def __init__(self, app_key="NEWAPI", app_name="new-api"):
        super(NewApiSign, self).__init__("", app_name=app_name, app_key=app_key)
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
        user_id = data.get("data", {}).get("id")
        if user_id is None:
            self.pwl("登录返回缺少用户ID，无法设置 New-Api-User")
            return False
        self.session.headers.update({"New-Api-User": str(user_id)})
        return True

    def sign(self):
        try:
            resp = self.session.get(f"{self.base_url}/api/user/checkin")
        except Exception as e:
            self.pwl(f"签到状态请求失败: {e}")
            return False
        if resp.status_code != 200:
            self.pwl(f"签到状态请求失败: HTTP {resp.status_code}")
            return False
        try:
            data = resp.json()
        except Exception:
            self.pwl(f"签到状态解析失败: {resp.text}")
            return False
        if not data.get("success", False):
            self.pwl(data.get("message", "获取签到状态失败"))
            return False
        stats = data.get("data", {}).get("stats", {})
        if stats.get("checked_in_today"):
            self.pwl("今日已签到")
            return True

        try:
            resp = self.session.post(f"{self.base_url}/api/user/checkin")
        except Exception as e:
            self.pwl(f"签到请求失败: {e}")
            return False
        if resp.status_code != 200:
            self.pwl(f"签到失败: HTTP {resp.status_code}")
            return False
        try:
            data = resp.json()
        except Exception:
            self.pwl(f"签到解析失败: {resp.text}")
            return False
        if not data.get("success", False):
            self.pwl(data.get("message", "签到失败"))
            return False
        self.pwl(data.get("message", "签到成功"))
        return True


if __name__ == "__main__":
    import re
    keys = sorted(set(
        re.sub(r"^SIGN_URL_", "", k)
        for k in os.environ
        if k.startswith("SIGN_URL_NEWAPI")
    ))
    if not keys:
        print("No SIGN_URL_NEWAPI* environment variables found")
    for i, app_key in enumerate(keys, 1):
        print(f"[{i}/{len(keys)}] Processing: {app_key}")
        try:
            s = NewApiSign(app_key=app_key, app_name=f"new-api-{app_key}")
            s.run()
        except Exception as e:
            print(f"[{app_key}] Failed: {e}")
