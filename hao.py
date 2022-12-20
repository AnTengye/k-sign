# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('hao4k签到');
"""
import json

from scrapy import Selector

from base import BaseSign
from gifcode import handle_yzm


class HaoSign(BaseSign):
    def __init__(self):
        super(HaoSign, self).__init__("https://www.hao4k.cn", app_name="hao4k", app_key="4K", timeout=10)
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'qiandao/'
        self.sign_text_xpath = '//*[@id="wp"]/div[3]/div[1]/div[1]/div/div[1]/text()'
        self.sign_text = '您今天还没有签到'
        self.sign_path = "qiandao/?mod=sign&operation=qiandao&formhash=%s&format=empty"
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'

    def login(self, times=3) -> bool:
        if times == 0:
            print("失败次数过多")
            return False
        print(f"进行 {self.username} 登录-times:{times}")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_data = selector.re(r"formhash:'(\w*)'")
        discode_data = selector.re(r"discode: '(\w*)'")
        sec_data = selector.re(r"seccodehash: '(\w*)'")
        update_data = selector.re(r"update=([0-9]*)&")
        sec_hash = ""
        form_hash = ""
        update = ""
        discode = ""
        if len(form_data) != 0:
            form_hash = form_data[0]
        if len(sec_data) != 0:
            sec_hash = sec_data[0]
        if len(update_data) != 0:
            update = update_data[0]
        if len(discode_data) != 0:
            discode = discode_data[0]
        if sec_hash and form_hash:
            verify_code = self.code(sec_hash, update)
            url = f"{self.base_url}/plugin.php?id=jzsjiale_isms:api"
            payload = f'module=loginmima&version=1&loginsubmit=yes&discode={discode}&type=auto&account={self.username}&password={self.password}&questionid=0&answer=&seccodehash={sec_hash}&seccodeverify={verify_code}&formhash={form_hash}&logintype=mima&device=mobile&cookietime=2592000&referer=https%3A%2F%2Fwww.hao4k.cn%2F.%2F'
            headers = {
                'authority': self.url_info.hostname,
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'pragma': 'no-cache',
                'referer': f'{self.base_url}/member.php?mod=logging&action=login',
                'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Mobile Safari/537.36'
            }
            response = self.session.post(url, headers=headers, data=payload)
            try:
                result = json.loads(response.text)
                if result.get("code") == "1":
                    self.pwl(f'登录失败：{self.err_msg_dict.get(result.get("msg", ""), result.get("msg", ""))}')
                    return self.login(times - 1)
                elif result.get("code") == "0":
                    self.pwl("登录成功")
                    return True
                else:
                    self.pwl(result)
                    return self.login(times - 1)
            except Exception as e:
                print("请求异常:\n", response.text)
                return False

    def code(self, sec_hash, update) -> str:
        url = f"{self.base_url}/misc.php?mod=seccode&update={update}&idhash={sec_hash}"
        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/member.php?mod=logging&action=login',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'image',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Mobile Safari/537.36'
        }
        response = self.session.get(url, headers=headers, data=payload)
        return handle_yzm(response.content)


if __name__ == "__main__":
    s = HaoSign()
    s.run()
