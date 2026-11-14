# -*- coding:utf-8 -*-
"""
cron: 0 8 8 * * *
new Env('moxing签到');
"""
import base64
import io
import json
from functools import lru_cache

import ddddocr
import requests.utils
from PIL import Image, ImageOps
from scrapy import Selector
from requests.packages.urllib3.util.retry import Retry

from base import BaseSign
from gifcode import handle_yzm


@lru_cache(maxsize=3)
def _click_model(kind):
    return ddddocr.DdddOcr(
        show_ad=False, det=kind == "det", ocr=kind != "det", beta=kind == "beta"
    )


class MoxingSign(BaseSign):
    def __init__(self):
        super(MoxingSign, self).__init__("https://moxing.app", app_name="moxing", app_key="MOXING", proxy=True)
        self.login_type = "login"
        # The official portal now links to forum 2.0; its Discuz login is gone.
        self.exec_method = ["sign_v2"]
        self.retry_times = 1
        self._captcha_config = {}
        # Respect captcha rate limits instead of sleeping on Retry-After or replaying requests.
        for adapter in self.session.adapters.values():
            adapter.max_retries = Retry(total=0)

    def _forum_url(self):
        if self.url_info.hostname == "mox.live" or self.url_info.hostname.startswith("mox."):
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

    def _page_props(self, page):
        try:
            raw = Selector(text=page.text, type="html").xpath('//*[@data-page]/@data-page').get()
            data = json.loads(raw or "{}")
        except ValueError:
            data = None
        props = data.get("props") if isinstance(data, dict) else None
        if not isinstance(props, dict):
            self.pwl("论坛页面状态数据无效")
            return None
        config = props.get("captcha")
        if isinstance(config, dict):
            self._captcha_config = config
        return props

    def _captcha(self, scene="sign"):
        config = getattr(self, "_captcha_config", {})
        scenes = config.get("scenes") or {}
        driver = scenes.get(scene) or scenes.get("default") or config.get("driver") or "image"
        if driver == "none":
            return {}
        if driver == "click":
            return self._click_captcha()
        if driver != "image":
            self.pwl(f"当前验证方式 {driver} 需要在浏览器中人工完成")
            return None
        return self._image_captcha()

    @staticmethod
    def _image_data(value):
        if not isinstance(value, str) or not value.startswith("data:image/") or "," not in value:
            raise ValueError("invalid captcha image")
        return base64.b64decode(value.split(",", 1)[1], validate=True)

    def _click_points(self, data):
        image_bytes = self._image_data(data.get("image"))
        thumb = Image.open(io.BytesIO(self._image_data(data.get("thumb")))).convert("RGBA")
        # GoCaptcha's transparent hint must be composited, not converted to a black background.
        hint = Image.new("RGBA", thumb.size, "white")
        hint.alpha_composite(thumb)
        hint = hint.convert("RGB")
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        def encode(crop):
            buffer = io.BytesIO()
            crop.save(buffer, format="PNG")
            return buffer.getvalue()

        def labels(crop):
            raw = encode(crop)
            texts = {
                _click_model("ocr").classification(raw),
                _click_model("beta").classification(raw),
                _click_model("ocr").classification(encode(ImageOps.expand(crop, 5, "white"))),
            }
            return {text for text in texts if isinstance(text, str) and len(text) == 1}

        detector = _click_model("det")
        targets = sorted(detector.detection(encode(hint)), key=lambda box: box[0])
        boxes = detector.detection(image_bytes)
        if not targets or len(targets) > len(boxes):
            return None
        candidates = [(box, labels(image.crop(box))) for box in boxes]
        dots, used = [], set()
        width, height = data.get("width", image.width), data.get("height", image.height)
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)) or min(width, height) <= 0:
            return None
        for target in targets:
            wanted = labels(hint.crop(target))
            matches = [i for i, (_, texts) in enumerate(candidates) if wanted & texts]
            if len(matches) != 1 or matches[0] in used:
                return None
            index = matches[0]
            used.add(index)
            x1, y1, x2, y2 = candidates[index][0]
            dots.append({"x": round((x1 + x2) / 2 * width / image.width),
                         "y": round((y1 + y2) / 2 * height / image.height)})
        return dots

    def _click_captcha(self):
        for attempt in range(1, 4):
            headers = self._api_headers()
            if not headers:
                return None
            response = self.session.post(
                f"{self._forum_url()}/api/forum/captcha/go/click/challenge",
                json={}, headers=headers, allow_redirects=False,
            )
            if response.status_code != 200:
                self.pwl(f"获取点选验证码失败：HTTP {response.status_code}")
                return None
            try:
                info = response.json()
                data = info.get("data") if isinstance(info, dict) else None
                if not isinstance(data, dict) or not data.get("key"):
                    raise ValueError("invalid challenge")
                dots = self._click_points(data)
            except (ValueError, OSError):
                self.pwl("点选验证码数据无效")
                return None
            if not dots:
                self.pwl(f"点选文字未能唯一匹配，刷新验证码（{attempt}/3）")
                continue
            response = self.session.post(
                f"{self._forum_url()}/api/forum/captcha/go/click/verify",
                json={"key": data["key"], "dots": dots},
                headers=self._api_headers(), allow_redirects=False,
            )
            try:
                info = response.json()
            except ValueError:
                self.pwl(f"点选验证未返回 JSON：HTTP {response.status_code}")
                return None
            result = info.get("data") if isinstance(info, dict) else None
            passed = result.get("pass") if isinstance(result, dict) else None
            if (response.status_code == 200 and isinstance(info, dict) and info.get("success") is not False
                    and isinstance(passed, str) and passed):
                self.pwl("点选人机验证通过")
                return {"captcha_pass": passed}
            if response.status_code != 422:
                self.pwl(f"点选验证失败：HTTP {response.status_code}")
                return None
            self.pwl(f"点选验证未通过，刷新验证码（{attempt}/3）")
        self.pwl("点选验证连续失败，停止本次登录")
        return None

    def _image_captcha(self):
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
        page = self.session.get(f"{self._forum_url()}/login")
        if page.status_code != 200:
            self.pwl(f"论坛 2.0 初始化失败：HTTP {page.status_code}")
            return False
        if self._page_props(page) is None:
            return False
        for _ in range(3):
            captcha = self._captcha()
            if captcha is None:
                return False
            headers = self._api_headers()
            if not headers:
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
            if any(key in errors for key in ("captcha", "captcha_key", "captcha_pass")) or "验证码" in message:
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
        props = self._page_props(page)
        if props is None:
            return None
        auth = props.get("auth")
        if not isinstance(auth, dict) or not auth.get("user"):
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
        captcha = self._captcha("signin")
        if captcha is None:
            return False
        headers = self._api_headers()
        if not headers:
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
