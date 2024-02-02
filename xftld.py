# -*- coding:utf-8 -*-
"""
cron: 0 0 1 * * *
new Env('xftld签到');
"""
import json
from urllib.parse import quote

from base import BaseSign


class XFTLDSign(BaseSign):
    def __init__(self):
        super(XFTLDSign, self).__init__("https://xfltd.net", app_name="xftld", app_key="XFTLD", proxy=True)
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.exec_method = ["sign"]

    def login(self) -> bool:
        url = f"{self.base_url}/api/?action=login&email={quote(self.username, safe='')}&password={self.password}"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/login',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }
        response = self.session.get(url, headers=headers, data=payload)
        if response.status_code == 200:
            response_info = json.loads(response.text)
            token = response_info.get("data")
            if token:
                self.pwl(f"登录成功")
                return True
        return False

    def sign(self) -> bool:
        url = f"{self.base_url}/skyapi?action=checkin"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/dashboard',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }
        response = self.session.get(url, headers=headers, data=payload)
        if response.status_code == 200:
            response_info = json.loads(response.text)
            score = response_info.get("data")
            if score:
                self.pwl(f"签到成功:获得{score}MB 流量")
                return True
            else:
                self.pwl(f"签到失败:{response_info.get('message')}")
                return False
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = XFTLDSign()
    s.run()
