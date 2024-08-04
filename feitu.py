# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('FeiTu签到');
"""
import json

from base import BaseSign


class FeiTuSign(BaseSign):
    def __init__(self):
        super(FeiTuSign, self).__init__("https://api-cdn.feitu.im", app_name="feitu", app_key="FEITU")
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
        url = f"{self.base_url}/ft/gateway/cn/passport/auth/login"

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
            "password": self.password
        })
        if response.status_code == 200:
            response_info = json.loads(response.text)
            data = response_info.get("data")
            if data is None:
                self.pwl("登录失败，请检查返回值")
                return False
            token = data.get("auth_data")
            token_header = {
                "Authorization": token
            }
            self.session.headers.update(token_header)
            return self.get_info()
        self.pwl('登录失败' + response.text)
        return False

    def get_info(self) -> bool:
        url = f"{self.base_url}/ft/gateway/cn/user/info"

        headers = {
            'authority': self.url_info.hostname,
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'content-type': 'application/json'
        }
        response = self.session.get(url, headers=headers)
        if response.status_code == 200:
            response_info = json.loads(response.text)
            transfer = response_info.get("data").get("transfer_enable")
            self.pwl(f"剩余流量:{transfer/1024/1024/1024} GB")
            return True
        else:
            self.pwl('获取用户信息失败' + response.text)
            return False

    def sign(self) -> bool:
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}',
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'content-type': 'application/json'
        }
        response = self.session.get(f"{self.base_url}/ft/gateway/cn/user/sign", headers=headers)
        if response.status_code == 200:
            self.pwl(f"签到成功")
            return True
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = FeiTuSign()
    s.run()
