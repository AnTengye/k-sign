# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('调侃签到');
"""

import json
from urllib.parse import quote
from base import BaseSign
from scrapy import Selector


class TiaoKSign(BaseSign):
    def __init__(self):
        super(TiaoKSign, self).__init__("https://www.tiaokanwang.vip", app_name="调侃", app_key="TIAOK", proxy=True)
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.exec_method = ["sign"]

    def login(self) -> bool:
        url = f"{self.base_url}/wp-login.php"
        self.session.get(url)
        payload = f'log={self.username}&pwd={self.password}&rememberme=forever&wp-submit=%E7%99%BB%E5%BD%95&redirect_to={quote(self.base_url, safe="")}%2Fwp-admin%2F&testcookie=1'
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
            result_selector = Selector(response=response)
            score = result_selector.re(r"<td>(.*?)币</td>")
            if len(score) == 0:
                self.pwl('登录失败, 无法获取到积分信息')
                return False
            self.pwl('登录成功，当前积分：' + score[0])
            return True
        self.pwl('登录失败' + response.text)
        return False

    def sign(self) -> bool:
        url = f"{self.base_url}/wp-admin/admin-ajax.php"

        payload = 'action=epd_checkin'
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
            self.pwl('签到成功')
            return True
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = TiaoKSign()
    s.run()
