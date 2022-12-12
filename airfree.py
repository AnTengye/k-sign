# -*- coding:utf-8 -*-
"""
cron: 0 3 8 * * *
new Env('机场-airfree');
"""

from base import BaseSign
from urllib.parse import quote


class AirFreeSign(BaseSign):
    def __init__(self):
        super(AirFreeSign, self).__init__("https://airfree.cloud", app_name="airfree机场", app_key="AIRFREE")
        # 支持的方法
        self.exec_method = ["sign"]

    def login(self) -> bool:
        url = self.base_url + "/auth/login"
        payload = f"code=&email={quote(self.username, safe='')}&passwd={self.password}&remember_me=on&fingerprint={self.uid()} "
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': url,
            'sec-ch-ua': '"Google Chrome";v="105", "Not)A;Brand";v="8", "Chromium";v="105"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }

        response = self.session.post(url, headers=headers, data=payload)
        result = response.json()
        self.pwl(result.get("msg"))
        if result.get("ret") == 1:
            return True
        return False

    def sign(self) -> bool:
        url = self.base_url + "/user/checkin"
        response = self.session.post(url, data={})
        result = response.json()
        if result.get("ret") == 1:
            self.pwl(f"今日：{result.get('msg')},当前总流量：{result.get('traffic')}")
            return True
        self.pwl(result.get("msg"))
        return False


if __name__ == "__main__":
    s = AirFreeSign()
    s.run()
