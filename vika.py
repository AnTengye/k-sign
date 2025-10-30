# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('vika签到');
"""
import json

from base import BaseSign


class VikaSign(BaseSign):
    def __init__(self):
        super(VikaSign, self).__init__("https://www.vikacg.com", app_name="vika", app_key="VIKA", proxy=True)
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.is_sign = False
        self.exec_method = ["sign"]
        self.sign_path = "/api/vikacg/v1/userMission"

    def _login(self):
        """
        通用登录（不含验证码）
        :return:
        """
        print(f"进行 {self.username} 登录")
        url = f"{self.base_url}/api/vikacg/v1/login"

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
            "account": self.username,
            "password": self.password
        })
        # {'status': 'success', 'code': 200, 'statusCode': 200, 'statusMessage': '登录成功', 'message': '登录成功', 'data': {'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOjMwMDI2MCwicm9sZSI6InVzZXIiLCJpYXQiOjE3NjE4MzM1MDMsImV4cCI6MTc5MzM5MTEwM30.HH495U1kodpzHtaQoUYfQfEKlvAE6haSQxfKA8HOekk'}}
        if response.status_code == 200:
            response_info = json.loads(response.text)
            resp_code = response_info.get("code")
            if resp_code != 200:
                self.pwl(f"登录失败:{response_info.get('message')}，请检查返回值")
                return False
            token = response_info.get("data").get("token")
            token_header = {
                "Authorization": "Bearer " + token
            }
            self.session.headers.update(token_header)
            self.get_info()
            return True
        self.pwl('登录失败' + response.text)
        return False

    def get_info(self):
        url = f"{self.base_url}/api/vikacg/v1/getUserInfo"

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
            "detail": True
        })
        if response.status_code == 200:
            response_info = json.loads(response.text)
            resp_code = response_info.get("code")
            if resp_code != 200:
                self.pwl(f"获取用户信息失败:{response_info.get('message')}，请检查返回值")
                return False
            basic = response_info.get("data").get("basic")
            credit = response_info.get("data").get("credit")
            self.pwl(f"用户信息：{basic.get('name')},积分：{credit.get('count')}")
            if credit.get("sign_count") != 0:
                self.is_sign = True
            self.pwl(f"签到状态:{self.is_sign}")
        else:
            self.pwl('获取用户信息失败' + response.text)

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
        response = self.session.post(f"{self.base_url}/{self.sign_path}", headers=headers, json={
        })
        if response.status_code == 200:
            response_info = json.loads(response.text)
            resp_code = response_info.get("code")
            if resp_code != 200:
                self.pwl(f"签到失败:{response_info.get('message')}，请检查返回值")
                return False
            count = response_info.get("data").get("count")
            sign_count = response_info.get("data").get("sign_count")
            self.pwl(f"签到成功：获得积分：{sign_count}, 总积分：{count}")
            return True
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = VikaSign()
    s.run()
