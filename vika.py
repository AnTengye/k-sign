# -*- coding:utf-8 -*-
"""
cron: 0 14 8 * * *
new Env('vika签到');
"""
import datetime
import json
import uuid

from base import BaseSign


class VikaSign(BaseSign):
    def __init__(self):
        super(VikaSign, self).__init__("https://www.vikacg.com", app_name="vika", app_key="VIKA", proxy=True)
        # Public identifiers sent by the current official Moonlight web client.
        self.session.headers.update({
            "architecture": "AixPot",
            "x-client-code": "C6746511-E471-44DA-A0CA-2C6D17DCE8EA",
            "x-client-name": "VikACG Moonlight",
            "x-device-code": uuid.uuid5(uuid.NAMESPACE_URL, f"{self.base_url}|{self.username}").hex,
        })
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.is_sign = False
        self.exec_method = ["sign"]
        self.sign_path = "api/vikacg/v1/userMission"

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
            return self.get_info()
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
            if not isinstance(basic, dict) or not isinstance(credit, dict) or "sign_time" not in credit:
                self.pwl("用户信息缺少有效的签到状态")
                return False
            self.pwl(f"用户信息：{basic.get('name')},积分：{credit.get('count')}")
            # 2. 检查 sign_time 是否有效 (不为 0 且不为 None)
            sign_time = credit.get("sign_time")  # 先获取值
            self.is_sign = False
            if sign_time:
                try:
                    timestamp_int = int(sign_time)
                    timestamp_sec = timestamp_int / 1000.0 if timestamp_int > 100000000000 else timestamp_int
                    timestamp_date = datetime.datetime.fromtimestamp(timestamp_sec).date()
                    today_date = datetime.date.today()
                    self.pwl(f"签到时间戳: {timestamp_date}, 今天时间戳: {today_date}")
                    self.is_sign = (timestamp_date == today_date)

                except (ValueError, OSError) as e:
                    # 如果时间戳格式还是有问题，捕获异常并打印
                    self.pwl(f"处理签到时间戳出错: {e}, 原始值: {sign_time}")
                    return False

            # 6. 无论如何都会打印最终的正确状态
            self.pwl(f"签到状态:{self.is_sign}")
            return True
        else:
            self.pwl('获取用户信息失败' + response.text)
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
