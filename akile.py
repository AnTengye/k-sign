# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('akile签到');
"""
import json
from curl_cffi import requests
from base import BaseSign


class AkileSign(BaseSign):
    def __init__(self):
        super(AkileSign, self).__init__("https://api.akile.io", app_name="akile", app_key="AKILE")
        self.session = requests.Session(impersonate="chrome101")
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.is_sign = False
        self.exec_method = ["sign"]

    def _login(self):
        """
        通用登录（不含验证码）
        :return:
        """
        print(f"进行 {self.username} 登录")
        url = f"{self.base_url}/api/v1/user/login"

        headers = {
            'authority': self.url_info.hostname,
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/post',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'content-type': 'application/json'
        }
        response = self.session.post(url, headers=headers, json={
            "email": self.username,
            "password": self.password,
            "token": "",
            "verifyCode": "",
            "remember": True
        })
        if response.status_code == 200:
            response_info = json.loads(response.text)
            name = response_info.get("status_code")
            if name != 0:
                self.pwl("登录失败，请检查返回值")
                return False
            token = response_info.get("data").get("token")
            token_header = {
                "Authorization": token
            }
            self.session.headers.update(token_header)
            return True
        self.pwl('登录失败' + response.text)
        return False

    def sign(self) -> bool:
        if self.is_sign:
            self.pwl("已经签到过了，跳过")
            return True
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/post',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'content-type': 'application/json'
        }
        response = self.session.get(f"{self.base_url}/api/v1/user/Checkin", headers=headers)
        if response.status_code == 200:
            response_info = json.loads(response.text)
            if isinstance(response_info, str):
                self.pwl(f"签到失败，请检查返回值:{response_info}")
                return False
            code = response_info.get("status_code")
            if code == 0:
                self.pwl("签到成功")
                return True
            return False
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = AkileSign()
    s.run()
