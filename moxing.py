# -*- coding:utf-8 -*-
"""
cron: 0 8 8 * * *
new Env('moxing签到');
"""
import json

import requests.utils

from base import BaseSign


class MoxingSign(BaseSign):
    def __init__(self):
        super(MoxingSign, self).__init__("https://moxing.app", app_name="moxing", app_key="MOXING", proxy=True)
        # 登录配置
        self.login_type = "login"
        # self.login_setting_code_type = "gif"
        # self.login_setting_code_check = True
        self.session.cookies.set("is_agree", "1")
        # 支持的方法
        self.exec_method = ["sign", "sign_v2"]
        # 签到配置
        self.index_path = ''
        self.sign_path = "plugin.php?id=k_misign:sign&operation=qiandao&format=global_usernav_extra&formhash=%s"
        self.sign_text_xpath = '//*[@id="fx_checkin_b"]/@alt'
        self.sign_text = '点击签到'
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'


    def sign_v2(self) -> bool:
        self.session.get(f"{self.base_url}/auth.php?redirect=discuss")
        url_v2 = f"https://mox.{self.url_info.netloc}"
        self.session.get(f"{url_v2}/discuss")
        users_resp = self.session.post(f"{url_v2}/api/forum/check-in/users", data={"page": 1})
        if users_resp.status_code >= 400:
            self.pwl(f"获取签到用户列表失败:{users_resp.status_code}")
            return False
        sign_info_resp = self.session.get(f"{url_v2}/forum/sign")
        token = self.session.cookies.get("XSRF-TOKEN") or sign_info_resp.cookies.get("XSRF-TOKEN")
        if not token:
            self.pwl("获取 XSRF-TOKEN 失败，可能未完成 2.0 论坛登录")
            return False
        captcha_resp = self.session.get(f"{url_v2}/api/forum/captcha/generate")
        if captcha_resp.status_code != 200:
            self.pwl(f"获取验证码失败:{captcha_resp.text}")
            return False
        response_info = json.loads(captcha_resp.text)
        # {key: "captcha_MeBJ5w0gcMUWMKcSEW9p6hWCqfRg4B4b", image: "JN4LC"}
        resp = self.session.post(f"{url_v2}/api/forum/check-in/sign", data={"captcha": response_info.get("image"), "captcha_key": response_info.get("key")}, headers={"X-XSRF-TOKEN": requests.utils.unquote(token), "X-Requested-With": "XMLHttpRequest"})
        if resp.status_code == 200:
            response_info = json.loads(resp.text)
            success = response_info.get("success")
            if success:
                self.pwl(f'签到成功:{response_info.get("data").get("message")}')
                return True
            else:
                self.pwl(f'签到失败:{response_info}')
        elif resp.status_code == 400:
            response_info = json.loads(resp.text)
            message = response_info.get("message", "签到失败")
            self.pwl(f'签到失败:{message}')
            if "已签到" in message or "已经" in message:
                return True
        else:
            self.pwl(f'签到失败:{resp.status_code}')
        return False


if __name__ == "__main__":
    s = MoxingSign()
    s.run()
