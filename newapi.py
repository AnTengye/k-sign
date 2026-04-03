# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('new-api每日签到');

Multi-site support via environment variable naming convention:
  SIGN_URL_NEWAPI_<SUFFIX>  - Site URL (e.g. SIGN_URL_NEWAPI_A, SIGN_URL_NEWAPI_B)
  SIGN_UP_NEWAPI_<SUFFIX>   - Username/password (e.g. SIGN_UP_NEWAPI_A)
  SIGN_TOKENS_NEWAPI_<SUFFIX> - One user_id|token per line for token check-in

Backward compatible: plain SIGN_URL_NEWAPI / SIGN_UP_NEWAPI still works.
"""

import os
import re

from base import BaseSign


class NewApiSign(BaseSign):
    def __init__(self, app_key="NEWAPI", app_name="new-api", token_entry=None):
        if token_entry is None:
            token_entries = collect_token_entries(app_key)
            if len(token_entries) == 1:
                token_entry = token_entries[0]
        restore_up = None
        if token_entry is not None:
            env_key = f"SIGN_UP_{app_key}"
            restore_up = os.environ.get(env_key)
            if restore_up is None:
                os.environ[env_key] = "token-user|token-auth"
        try:
            super(NewApiSign, self).__init__("", app_name=app_name, app_key=app_key)
        finally:
            if token_entry is not None:
                env_key = f"SIGN_UP_{app_key}"
                if restore_up is None:
                    os.environ.pop(env_key, None)
                else:
                    os.environ[env_key] = restore_up
        self.login_type = "login"
        self.exec_method = ["sign"]
        self.skip_login = False
        self.token_entry = token_entry

    def pre(self):
        if self.token_entry is not None:
            return
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
        if self.token_entry is not None:
            user_id, token = self.token_entry
            self.session.headers.update({
                "Authorization": f"Bearer {token}",
                "New-Api-User": str(user_id),
            })
            return True
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


def collect_token_entries(app_key):
    raw_value = os.getenv(f"SIGN_TOKENS_{app_key}", "")
    entries = []
    for index, line in enumerate(raw_value.splitlines(), 1):
        value = line.strip()
        if not value:
            continue
        parts = value.split("|", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise ValueError(f"SIGN_TOKENS_{app_key} 第 {index} 行格式无效，应为 user_id|token")
        entries.append((parts[0].strip(), parts[1].strip()))
    return entries


def discover_app_keys():
    return sorted(set(
        re.sub(r"^SIGN_URL_", "", key)
        for key in os.environ
        if key.startswith("SIGN_URL_NEWAPI")
    ))


def run_site(app_key):
    token_entries = collect_token_entries(app_key)
    if token_entries:
        for index, token_entry in enumerate(token_entries, 1):
            user_id, _ = token_entry
            print(f"[{app_key}] Token {index}/{len(token_entries)} user_id={user_id}")
            try:
                signer = NewApiSign(
                    app_key=app_key,
                    app_name=f"new-api-{app_key}-{user_id}",
                    token_entry=token_entry,
                )
                signer.run()
            except Exception as e:
                print(f"[{app_key}] Token user_id={user_id} failed: {e}")
        return

    signer = NewApiSign(app_key=app_key, app_name=f"new-api-{app_key}")
    signer.run()


if __name__ == "__main__":
    keys = discover_app_keys()
    if not keys:
        print("No SIGN_URL_NEWAPI* environment variables found")
    for i, app_key in enumerate(keys, 1):
        print(f"[{i}/{len(keys)}] Processing: {app_key}")
        try:
            run_site(app_key)
        except Exception as e:
            print(f"[{app_key}] Failed: {e}")
