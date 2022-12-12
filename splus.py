# -*- coding:utf-8 -*-
"""
cron: 0 0 18 * * *
new Env('南+登录');
"""
import re
import time
from urllib.parse import quote

from scrapy import Selector

from base import BaseSign
from gifcode import handle_yzm


class SouthPlusSign(BaseSign):
    def __init__(self):
        super(SouthPlusSign, self).__init__("https://www.summer-plus.net", app_name="南+", app_key="SPLUS")
        # 支持的方法
        self.exec_method = ["sign"]

    def fetch_index(self):
        url = f"{self.base_url}/login.php"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/',
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
        self.session.get(url, headers=headers, data=payload)

    def login(self, times=10) -> bool:
        if times == 0:
            self.pwl("失败次数过多")
            return False
        print(f"进行 {self.username} 登录-times:{times}")
        # 访问页面
        self.fetch_index()
        self.fetch_code()
        verify_code = self.code(20)
        if not verify_code:
            return self.login(times - 1)
        url = f"{self.base_url}/login.php?"

        payload = f'forward=&jumpurl={quote(self.base_url, safe="")}%2F&step=2&gdcode={verify_code}&lgt=0&pwuser={self.username}&pwpwd={quote(self.password)}&hideid=0&cktime=31536000'
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
        result = resp_selector.re(r"认证码不正确")
        if result is not None and len(result) > 0:
            return self.login(times - 1)
        success_result = resp_selector.re(r"您已经顺利登录")
        if success_result is not None and len(success_result) > 0:
            self.pwl("您已经顺利登录")
            return True
        print(response.text)
        return self.login(times - 1)

    def fetch_code(self):
        url = f"{self.base_url}/ck.php?"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/login.php',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'image',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }

        self.session.get(url, headers=headers, data=payload)

    def code(self, times=3) -> str:
        if times == 0:
            self.pwl("错误次数过多")
            return ""
        now_time = self.get_now()
        url = f"{self.base_url}/ck.php?nowtime={now_time}"
        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/login.php',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'image',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }
        response = self.session.get(url, headers=headers, data=payload)
        result = handle_yzm(response.content, t="img")
        if result.encode().isdigit():
            if len(result) != 4:
                return self.code(times - 1)
            return result
        else:
            return self.code(times - 1)

    def fetch_sign(self):
        url = f"{self.base_url}/plugin.php?H_name-tasks.html"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': self.base_url,
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }

        self.session.get(url, headers=headers, data=payload)

    def sign(self) -> bool:
        self.fetch_sign()
        if self.apply_task(14):
            self.confirm_task(14)
        self.apply_task(15)
        result = self.confirm_task(15)
        return result

    def apply_task(self, task_id) -> bool:
        now_time = self.get_now()
        url = f"{self.base_url}/plugin.php?H_name=tasks&action=ajax&actions=job&cid={task_id}&nowtime={now_time}&verify=22594798"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/plugin.php?H_name-tasks.html',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }

        response = self.session.get(url, headers=headers, data=payload)
        result = re.search(r"CDATA\[(.*?)	(.*?)\]>", response.text, flags=0)
        if result is not None:
            self.pwl(result.group(2))
            if result.group(1) == "success":
                return True
            return False
        print(response.text)
        return False

    def confirm_task(self, task_id) -> bool:
        now_time = self.get_now()
        url = f"{self.base_url}/plugin.php?H_name=tasks&action=ajax&actions=job2&cid={task_id}&nowtime={now_time}&verify=22594798"

        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/plugin.php?H_name-tasks.html',
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }

        response = self.session.get(url, headers=headers, data=payload)
        result = re.search(r"CDATA\[(.*?)	(.*?)\]>", response.text, flags=0)
        if result is not None:
            self.pwl(result.group(2))
            if result.group(1) == "success":
                return True
            return False
        print(response.text)
        return False

    def get_now(self) -> int:
        return int(round(time.time() * 1000))


if __name__ == "__main__":
    s = SouthPlusSign()
    s.run()
