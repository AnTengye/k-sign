# -*- coding:utf-8 -*-
"""
cron: 0 6 8 * * *
new Env('老王论坛签到');
"""
import base64
import json
import math
import os
import re
import time

from scrapy import Selector

import slidecode
from base import BaseSign
from urllib.parse import quote, urljoin


class LaoWangSSign(BaseSign):
    def __init__(self):
        super(LaoWangSSign, self).__init__("https://laowang.vip", app_name="老王论坛", app_key="LW", proxy=True)
        self.retry_times = 3
        self.login_type = "login_cookie" if os.getenv("SIGN_COOKIE_LW") else "login"
        # 随机生成一个t
        self.login_t = str(round(time.time()))
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置


    def fetch_index(self, times=3) -> str:
        if times == 0:
            self.pwl("滑动验证错误次数过多")
            return ""
        if not getattr(self, "_slider_secret", None):
            script = self.session.get(f"{self.base_url}/captcha/tn_code.js")
            match = re.search(r"var\s+hmacSecret\s*=\s*['\"]([^'\"]+)['\"]", script.text)
            if script.status_code != 200 or not match:
                self.pwl("无法获取当前滑块校验协议")
                return ""
            self._slider_secret = match.group(1)
        # /captcha/tncode.php?t=0.39280096330223313
        resp = self.session.get(f"{self.base_url}/captcha/tncode.php?t=0.{self.login_t}")
        # 读取webp图片
        if resp.status_code == 200:
            width = slidecode.get_slide_width(resp.content)
            if width is None:
                self.pwl("未识别到滑块位置")
                return self.fetch_index(times - 1)
            time.sleep(1.1)
            payload = self._slider_payload(width, self._slider_secret)
            check_resp = self.session.post(f"{self.base_url}/captcha/check.php", data=payload)
            if check_resp.status_code == 200 and "_ok" in check_resp.text:
                return check_resp.text
            self.pwl(f"滑动验证失败:HTTP {check_resp.status_code} {check_resp.text[:120]}")
            return self.fetch_index(times - 1)
        else:
            self.pwl("滑动验证失败")
        return self.fetch_index(times - 1)

    @staticmethod
    def _slider_payload(width, secret):
        # Match the track summary, XOR encoding and FNV-1a signature used by tn_code.js.
        track = [{"x": width * (1 - math.cos(math.pi * i / 31)) / 2,
                  "y": math.sin(i * math.pi / 10), "t": i * 35} for i in range(32)]
        speeds, directions = [], []
        distance = 0
        for previous, current in zip(track, track[1:]):
            dx, dy = current["x"] - previous["x"], current["y"] - previous["y"]
            dt = current["t"] - previous["t"]
            segment = math.hypot(dx, dy)
            distance += segment
            speeds.append(segment / dt)
            directions.append(math.atan2(dy, dx))
        average = sum(speeds) / len(speeds)
        summary = {"valid": True, "points": len(track), "totalTime": track[-1]["t"],
                   "totalDist": distance, "avgSpeed": average, "maxSpeed": max(speeds),
                   "minSpeed": min(speeds), "speedVar": sum((v - average) ** 2 for v in speeds) / len(speeds),
                   "dirChanges": sum(abs(a - b) > math.pi / 4 for a, b in zip(directions, directions[1:])),
                   "finalX": width}
        text = json.dumps(summary, separators=(",", ":"))
        timestamp, offset = str(int(time.time() * 1000)), f"{width:.2f}"
        encrypted = "".join(chr(ord(char) ^ ord(secret[i % len(secret)])) for i, char in enumerate(text))
        signature = 0x811c9dc5
        for char in text + timestamp + offset + secret:
            signature = ((signature ^ ord(char)) * 0x01000193) & 0xffffffff
        return {"tn_r": offset, "track": base64.b64encode(encrypted.encode()).decode(),
                "ts": timestamp, "sign": f"{signature:x}"}
        

    def login(self) -> bool:
        if self.login_type == "login_cookie":
            return self._cookie_login()
        self.session.cookies.set("is_agree", "1", domain=self.url_info.hostname, path="/")
        self.session.get(f"{self.base_url}/home.php?mod=space&do=pm")
        # 访问页面
        token = self.fetch_index()
        if token == "":
            return False
        self.pwl(f"进行 {self.username} 登录")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//input[@name="formhash"]/@value').extract_first()
        if form_hash is None:
            self.pwl("formhash匹配失败")
            return False
        url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LDUGb&inajax=1"
        #
        password_base64 = base64.standard_b64encode(self.password.encode("utf-8")).decode("utf-8")
        payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fforum.php&username={self.username}&password=base64%3A%2F%2F{password_base64}&answer=&cookietime=2592000&clicaptcha-submit-info={token}'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/login.php',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }
        response = self.session.post(url, headers=headers, data=payload)
        resp_selector = Selector(response=response)
        success_result = resp_selector.re(r"succeedmessage")
        if success_result is not None and len(success_result) > 0:
            self.pwl("您已经顺利登录")
            return True
        self.pwl(response.text)
        return False

    def sign(self) -> bool:
        sign_btn_html = self.session.get(f"{self.base_url}/plugin.php?id=k_misign:sign")
        sign_btn_selector = Selector(response=sign_btn_html)
        sign_href = sign_btn_selector.xpath('//*[@id="wp"]/div[2]/div[1]/div[1]/a/@href').extract_first()
        if sign_href is None:
            is_signed = sign_btn_selector.xpath('//span[@class="btn btnvisted"]').extract_first()
            if is_signed is not None:
                self.pwl("已经签到过了")
                return True
            self.pwl("sign_href匹配失败")
            return False
        sign_html = self.session.get(f"{self.base_url}/{sign_href}")
        sign_selector = Selector(response=sign_html)
        sign_action = sign_selector.xpath('//*[@id="v2_captcha_form"]/@action').extract_first()
        if sign_action is None:
            self.pwl("sign_action匹配失败")
            return False
        token = self.fetch_index(5)
        if token == "":
            return False
        url = urljoin(sign_html.url, sign_action)
        payload = f'clicaptcha-submit-info={token}'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }
        response = self.session.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            confirmed = self.session.get(f"{self.base_url}/plugin.php?id=k_misign:sign")
            if confirmed.status_code == 200 and Selector(response=confirmed).xpath('//span[contains(@class,"btnvisted")]'):
                self.pwl("签到成功，已回读今日签到状态")
                return True
            self.pwl("未确认今日签到状态")
            return False
        self.pwl(response.text)
        return False

if __name__ == "__main__":
    s = LaoWangSSign()
    s.run()
