# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('luolck签到');
"""
import json

from base import BaseSign


class LuoLcySign(BaseSign):
    def __init__(self):
        super(LuoLcySign, self).__init__("https://luolcy.com", app_name="luolcy", app_key="LUOLCY", proxy=True)
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.is_sign = False
        self.exec_method = ["sign"]
        self.sign_path = "/wp-json/b2/v1/userMission"

    def _login(self):
        """
        通用登录（不含验证码）
        :return:
        """
        print(f"进行 {self.username} 登录")
        url = f"{self.base_url}/wp-json/jwt-auth/v1/token"

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
            "username": self.username,
            "password": self.password
        })
        if response.status_code == 200:
            response_info = json.loads(response.text)
            name = response_info.get("name")
            if name == "":
                self.pwl("登录失败，请检查返回值")
                return False
            score = response_info.get("credit")
            token = response_info.get("token")
            token_header = {
                "Authorization": "Bearer " + token
            }
            self.session.headers.update(token_header)
            self.pwl(f"登录信息：用户名{name},当前积分：{score}")
            self.get_mission()
            return True
        self.pwl('登录失败' + response.text)
        return False

    def get_info(self):
        url = f"{self.base_url}/wp-json/b2/v1/getUserInfo"

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
        response = self.session.post(url, headers=headers)
        if response.status_code == 200:
            response_info = json.loads(response.text)
            finish = response_info.get("user_data").get("task_").get("finish")
            if finish == 1:
                self.is_sign = True
            self.pwl(f"签到状态:{self.is_sign}")
        else:
            self.pwl('获取用户信息失败' + response.text)

    def get_mission(self):
        url = f"{self.base_url}/wp-json/b2/v1/getUserMission"
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
            "count": 20,
            "paged": 1
        })
        if response.status_code == 200:
            self.pwl('获取任务信息成功')
            self.get_info()
        else:
            self.pwl('获取任务信息失败' + response.text)

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
        response = self.session.post(f"{self.base_url}/{self.sign_path}", headers=headers)
        if response.status_code == 200:
            response_info = json.loads(response.text)
            if isinstance(response_info, str):
                self.pwl(f"签到失败，请检查返回值:{response_info}")
                return False
            score = response_info.get("credit")
            if score == 0:
                self.pwl("签到失败，请检查返回值")
                return False
            self.pwl(f"签到成功：获得积分：{score}")
            return True
        self.pwl('签到失败' + response.text)
        return False


if __name__ == "__main__":
    s = LuoLcySign()
    s.run()