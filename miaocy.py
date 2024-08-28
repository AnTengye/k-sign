# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('喵次元签到');
"""

import json
from urllib.parse import quote
from base import BaseSign
from scrapy import Selector


class MiaoCYSign(BaseSign):
    def __init__(self):
        super(MiaoCYSign, self).__init__("https://miaociyuan.top", app_name="喵次元", app_key="MIAOCY", proxy=True)
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.exec_method = ["sign"]

    def login(self) -> bool:
        login_page = f"{self.base_url}/login"
        resp = self.session.get(login_page)
        # "ajax_nonce":"d43416ef91"
        if resp.status_code != 200:
            self.pwl("登录失败, 无法获取到登录页面")
            return False
        result_selector = Selector(response=resp)
        ajax_nonce = result_selector.re(r"ajax_nonce\":\"(.*?)\"")
        if len(ajax_nonce) == 0:
            self.pwl("登录失败, 无法获取到ajax_nonce")
            return False
        nonce = ajax_nonce[0]
        url = f"{self.base_url}/wp-admin/admin-ajax.php"

        # payload = 'nonce=d43416ef91&user_name=mc2674mc&user_password=B6zmHen!7CdqK8q&remember=on&action=zb_user_login'
        payload = f"nonce={nonce}&user_name={self.username}&user_password={self.password}&remember=on&action=zb_user_login"
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
            status = response_info.get("status")
            if status == 1:
                self.pwl('登录成功')
                return True
        self.pwl('登录失败' + response.text)
        return False

    def sign(self) -> bool:
        sign_page = f"{self.base_url}/user/"
        resp = self.session.get(sign_page)
        # "ajax_nonce":"d43416ef91"
        if resp.status_code != 200:
            self.pwl("签到失败, 无法获取到签到页面")
            return False
        result_selector = Selector(response=resp)
        ajax_nonce = result_selector.re(r"ajax_nonce\":\"(.*?)\"")
        if len(ajax_nonce) == 0:
            self.pwl("签到失败, 无法获取到ajax_nonce")
            return False
        nonce = ajax_nonce[0]
        url = f"{self.base_url}/wp-admin/admin-ajax.php"

        payload = f"nonce={nonce}&action=zb_user_qiandao"
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
            status = response_info.get("status")
            if status == 1:
                self.pwl('签到成功')
                return True
            elif status == 0:
                self.pwl(response_info.get("msg"))
                return False
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = MiaoCYSign()
    s.run()
