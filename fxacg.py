# -*- coding:utf-8 -*-
"""
cron: 0 20 8 * * *
new Env('飞雪acg签到');
"""
import os
import re
from typing import Tuple
from urllib.parse import quote

from requests.packages.urllib3.util.retry import Retry
from scrapy import Selector

from base import BaseSign


class FXAcgSign(BaseSign):
    SIGNED_MESSAGES = ("已经签过到", "今日已签到", "今天已经签到", "今日已签")
    LOGIN_REQUIRED_MESSAGES = ("请先登录", "先登录才能继续", "登录后才能")

    def __init__(self):
        super(FXAcgSign, self).__init__("https://feixueacg.org", app_name="飞雪ACG", app_key="FXACG",
                                        proxy=True)

        self.retry_times = 3
        # The sign-in plugin currently sends HTTP 503 with Retry-After: 3600.
        # Return the response to the caller without holding the task for an hour.
        for adapter in self.session.adapters.values():
            adapter.max_retries = Retry(total=0, raise_on_status=False)
        # 登录配置
        self.login_type = "login_cookie" if os.getenv("SIGN_COOKIE_FXACG") else "login_code"
        self.login_setting_code_type = "img"
        self.login_setting_code_check = True
        referer = quote(f"{self.base_url}/forum.html", safe="")
        self.login_page_path = f'member.php?mod=logging&action=login&referer={referer}&infloat=yes&handlekey=login&inajax=1&ajaxtarget=fwin_content_login'
        self.login_resp_success = r"succeedhandle_login\('(.*?)'"
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置（避免访问稳定 503 的 dc_signin-dc_signin.html，直接通过首页与 AJAX 接口签到及回读）
        self.index_path = ""
        self.form_hash_xpath = '//input[@name="formhash"]/@value'
        self.sign_path = "plugin.php?id=dc_signin:sign&inajax=1"
        self.sign_emotid = "8"
        self.sign_mood = "每天萌萌哒~~"

    def _fetch_home_formhash(self, log_error: bool = True) -> str:
        home = self.session.get(f"{self.base_url}/")
        if home.status_code != 200:
            if log_error:
                retry_after = home.headers.get("Retry-After")
                suffix = f"，服务端要求 {retry_after} 秒后重试" if retry_after else ""
                self.pwl(f"签到页面请求失败：HTTP {home.status_code}{suffix}")
            return ""
        selector = Selector(response=home)
        form_hash = (
            selector.xpath(self.form_hash_xpath).extract_first()
            or selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first()
            or ""
        ).strip()
        if not form_hash and log_error:
            self.pwl("获取签到表单验证失败")
        return form_hash

    def _inspect_sign_state(self, form_hash: str) -> Tuple[str, str]:
        headers = {"Referer": f"{self.base_url}/"}
        check_resp = self.session.get(
            f"{self.base_url}/plugin.php?id=dc_signin:check&formhash={form_hash}",
            headers=headers,
        )
        if check_resp.status_code == 200 and "signin_yes.png" in (check_resp.text or ""):
            return "signed", form_hash

        modal_resp = self.session.get(
            f"{self.base_url}/plugin.php?id=dc_signin:sign&infloat=yes&handlekey=signin&inajax=1&ajaxtarget=fwin_content_signin",
            headers=headers,
        )
        if modal_resp.status_code == 200:
            modal_text = modal_resp.text or ""
            if any(msg in modal_text for msg in self.SIGNED_MESSAGES):
                return "signed", form_hash
            if any(msg in modal_text for msg in self.LOGIN_REQUIRED_MESSAGES):
                return "unauthenticated", form_hash
            match = re.search(
                r'name=["\']formhash["\'][^>]*value=["\']([^"\']+)["\']',
                modal_text,
            )
            if match:
                form_hash = match.group(1).strip() or form_hash
        return "unsigned", form_hash

    def sign(self) -> bool:
        form_hash = self._fetch_home_formhash(log_error=True)
        if not form_hash:
            return False

        state, form_hash = self._inspect_sign_state(form_hash)
        if state == "signed":
            self.pwl("今日已签到，已确认页面状态")
            return True
        if state == "unauthenticated":
            self.pwl("签到状态检查失败：当前会话未登录")
            return False

        self.pwl("进行签到中...")
        payload = {
            "formhash": form_hash,
            "signsubmit": "yes",
            "handlekey": "signin",
            "emotid": self.sign_emotid,
            "referer": f"{self.base_url}/",
            "content": self.sign_mood,
        }
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Pragma": "no-cache",
            "Referer": f"{self.base_url}/",
            "Upgrade-Insecure-Requests": "1",
        }
        # 提交后服务端可能跳转或回调到稳定 503 的 dc_signin 错误页，禁止自动跟随重定向并改由首页动态状态回读确认
        response = self.session.post(
            f"{self.base_url}/{self.sign_path}",
            headers=headers,
            data=payload,
            allow_redirects=False,
        )
        resp_text = response.text or ""
        succeed_match = re.search(
            r"succeedhandle_\w*\(\s*'[^']*'\s*,\s*'([^']*)'",
            resp_text,
        )
        if succeed_match and succeed_match.group(1):
            self.pwl(succeed_match.group(1))
        elif any(msg in resp_text for msg in self.SIGNED_MESSAGES):
            self.pwl("今日已签到")

        latest_hash = self._fetch_home_formhash(log_error=False) or form_hash
        post_state, _ = self._inspect_sign_state(latest_hash)
        if post_state == "signed":
            self.pwl("签到成功，已回读确认今日签到状态")
            return True

        err_match = re.search(r"errorhandle_\w*\(\s*'([^']*)'", resp_text)
        if err_match and err_match.group(1):
            self.pwl(f"签到失败：{err_match.group(1)}")
        else:
            self.pwl(f"签到未生效：HTTP {response.status_code}")
        return False



if __name__ == "__main__":
    s = FXAcgSign()
    s.run()
