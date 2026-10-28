# -*- coding:utf-8 -*-
"""
cron: 0 8 8 * * *
new Env('moxing签到');
"""
import base64
import json

import requests.utils
from scrapy import Selector

from base import BaseSign
from gifcode import handle_yzm


class MoxingSign(BaseSign):
    def __init__(self):
        super(MoxingSign, self).__init__("https://moxing.app", app_name="moxing", app_key="MOXING", proxy=True)
        self.login_type = "login"
        # The official portal now links to forum 2.0; its Discuz login is gone.
        self.exec_method = ["sign_v2"]

    def _forum_url(self):
        if self.url_info.hostname.startswith("mox."):
            return self.base_url
        return f"https://mox.{self.url_info.netloc}"

    def _api_headers(self):
        token = self.session.cookies.get("XSRF-TOKEN")
        if not token:
            self.pwl("未获取到论坛 2.0 的 CSRF Cookie")
            return None
        return {
            "X-XSRF-TOKEN": requests.utils.unquote(token),
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "Origin": self._forum_url(),
            "Referer": f"{self._forum_url()}/",
        }

    def _captcha(self):
        response = self.session.get(f"{self._forum_url()}/api/forum/captcha/generate")
        if response.status_code != 200:
            self.pwl(f"获取验证码失败：HTTP {response.status_code}")
            return None
        info = response.json()
        image = info.get("img")
        if image and image.startswith("data:image/") and "," in image:
            try:
                image_bytes = base64.b64decode(image.split(",", 1)[1], validate=True)
            except ValueError:
                self.pwl("验证码图片数据无效")
                return None
            code = handle_yzm(image_bytes, t="img")
        else:
            # The official client also supports the older canvas-rendered response.
            code = info.get("image")
        if not code or not info.get("key"):
            self.pwl("未获取到有效的验证码")
            return None
        return {"captcha": code, "captcha_key": info["key"]}

    def _login(self):
        page = self.session.get(f"{self._forum_url()}/")
        if page.status_code != 200:
            self.pwl(f"论坛 2.0 初始化失败：HTTP {page.status_code}")
            return False
        headers = self._api_headers()
        if not headers:
            return False
        for _ in range(3):
            captcha = self._captcha()
            if not captcha:
                return False
            response = self.session.post(
                f"{self._forum_url()}/api/forum/login",
                headers=headers,
                json={**captcha, "username": self.username, "password": self.password,
                      "sec": None, "secanswer": "", "remember": True},
            )
            try:
                info = response.json()
            except ValueError:
                self.pwl(f"论坛 2.0 登录未返回 JSON：HTTP {response.status_code}")
                return False
            if not isinstance(info, dict):
                self.pwl("论坛 2.0 登录响应格式无效")
                return False
            if info.get("code") == "TWO_FACTOR_REQUIRED":
                self.pwl("论坛账号已启用两步验证，需要完成当前登录验证")
                return False
            if response.status_code == 200 and info.get("success") is not False:
                if self._sign_state() is None:
                    return False
                self.pwl("论坛 2.0 登录成功")
                return True
            message = info.get("message", "登录失败")
            errors = info.get("errors") or {}
            if "captcha" in errors or "captcha_key" in errors or "验证码" in message:
                self.pwl("验证码错误，刷新重试")
                continue
            self.pwl(f"论坛 2.0 登录失败：{message}")
            return False
        return False

    def _sign_state(self):
        page = self.session.get(f"{self._forum_url()}/forum/sign")
        if page.status_code != 200:
            self.pwl(f"签到页面请求失败：HTTP {page.status_code}")
            return None
        raw = Selector(text=page.text).xpath('//*[@data-page]/@data-page').get()
        try:
            props = json.loads(raw or "{}").get("props", {})
        except ValueError:
            self.pwl("签到页面状态数据无效")
            return None
        if not (props.get("auth") or {}).get("user"):
            self.pwl("论坛 2.0 未登录")
            return None
        state = props.get("is_checked_in")
        if not isinstance(state, bool):
            self.pwl("签到页面缺少有效的签到状态")
            return None
        return state

    def sign_v2(self) -> bool:
        state = self._sign_state()
        if state is None:
            return False
        if state:
            self.pwl("今日已签到")
            return True
        headers = self._api_headers()
        if not headers:
            return False
        captcha = self._captcha()
        if not captcha:
            return False
        response = self.session.post(f"{self._forum_url()}/api/forum/check-in/sign", json=captcha, headers=headers)
        try:
            info = response.json()
        except ValueError:
            self.pwl(f"签到未返回 JSON：HTTP {response.status_code}")
            return False
        if not isinstance(info, dict):
            self.pwl("签到响应格式无效")
            return False
        message = info.get("message") or (info.get("data") or {}).get("message", "")
        already_signed = any(text in message for text in ("已签到", "已经签到", "已经签过", "今日已签"))
        if (response.status_code == 200 and info.get("success")) or already_signed:
            if self._sign_state() is not True:
                self.pwl("签到状态回读未确认成功")
                return False
            self.pwl(f"已确认今日签到：{message}")
            return True
        self.pwl(f"签到失败：HTTP {response.status_code} {message}")
        return False


if __name__ == "__main__":
    s = MoxingSign()
    s.run()
