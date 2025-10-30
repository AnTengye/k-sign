# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('嘤嘤怪签到');
"""

import json

from base import BaseSign
from gifcode import handle_yzm


class YYGSign(BaseSign):
    def __init__(self):
        super(YYGSign, self).__init__("https://yyg.one", app_name="嘤嘤怪之家", app_key="YYG")
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.exec_method = ["sign"]
    def login(self) -> bool:
        self.session.get(self.base_url)
        code = self.code()
        if code == "":
            self.pwl("验证码无法识别")
            return False
        url = f"{self.base_url}/wp-admin/admin-ajax.php"
        payload = f'username={self.username}&password={self.password}&canvas_yz={code}&remember=forever&action=user_signin'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/dc_signin-dc_signin.html',
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
            response_info = json.loads(response.text)
            score = response_info.get("error")
            if score:
                self.pwl(f"登录失败:{response.text}")
                return False
            self.pwl(response_info.get("msg"))
            return True
        self.pwl('登录失败' + response.text)
        return False

    def code(self, retry=10) -> str:
        if retry == 0:
            return ""
        url = f"{self.base_url}/wp-content/themes/zibll/action/captcha.php?type=image&id=img_yz_signin"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/dc_signin-dc_signin.html',
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

        response = self.session.get(url, headers=headers, data=payload)

        if response.status_code != 200:
            return ""
        img_data = json.loads(response.text)
        img_str = img_data.get("img")
        if img_str != "":
            _, content = img_str.split(",")
            result = handle_yzm(content, t=self.login_setting_code_type)
            if self.check_code(result):
                return result
            return self.code(retry-1)
        return ""
    def sign(self) -> bool:
        url = f"{self.base_url}/wp-admin/admin-ajax.php"

        payload = 'action=user_checkin'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
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
            response_info = json.loads(response.text)
            score = response_info.get("error")
            if score:
                self.pwl(f"签到失败:{response.text}")
                return False
            self.pwl(response_info.get("msg"))
            return True
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = YYGSign()
    s.run()
