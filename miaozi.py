# -*- coding:utf-8 -*-
"""
cron: 0 3 8 * * *
new Env('喵子小屋签到');
"""
import json
import os
from urllib.parse import quote

from scrapy import Selector

from gifcode import handle_yzm
from notify import send
from base import BaseSign


class MiaoSign(BaseSign):
    def __init__(self, username, password):
        super(MiaoSign, self).__init__("https://forum.h3dhub.com", username, password)

    def login(self, times=3) -> bool:
        if times == 0:
            print("失败次数过多")
            return False
        print(f"进行 {self.username} 登录-times:{times}")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first("")
        sec_data = selector.re(r"updateseccode\('(\w*?)'")
        update_data = selector.re(r"update=([0-9]*)&")
        sec_hash = ""
        update = "16626"
        if len(sec_data) != 0:
            sec_hash = sec_data[0]
        if len(update_data) != 0:
            update = update_data[0]
        if sec_hash and form_hash:
            verify_code = self.code(sec_hash, update)
            url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LwTq2&inajax=1"
            payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2F.%2F&username={self.username}&password={self.password}&questionid=0&answer=&cookietime=2592000&seccodehash={sec_hash}&seccodemodid=member%3A%3Alogging&seccodeverify={verify_code}'
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
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
            }
            response = self.session.post(url, headers=headers, data=payload)
            result_selector = Selector(response=response)
            jump_src = result_selector.re(r"succeedhandle_\('(.*?)'")
            if len(jump_src) == 0:
                result = result_selector.re(r"errorhandle_\('(.*?)'")
                print(result[0])
                return self.login(times - 1)
            else:
                self.session.get(jump_src[0])
            print(f'登录成功')
            return True
        else:
            print(f"表单校验异常:{form_hash}-{sec_hash}")

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
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
        }
        response = self.session.get(url, headers=headers, data=payload)
        return handle_yzm(response.content)

    def sign(self) -> bool:
        print("每日签到开始")
        url = f"{self.base_url}/home.php?mod=task&do=apply&id=22"
        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/home.php?mod=task',
            'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
        }
        response = self.session.get(url, headers=headers, data=payload)
        selector = Selector(response=response)
        result = selector.xpath('//*[@id="messagetext"]/p[1]/text()').extract_first("")
        self.pwl(f"结果：{result}")
        if "成功" in result:
            return True
        return False


if __name__ == "__main__":
    UP = os.getenv('SIGN_UP_MIAOZI')
    if UP:
        user_info = UP.split("|")
        username = user_info[0]
        password = user_info[1]
        s = MiaoSign(username, password)
        sign = False
        if s.login():
            sign = s.sign()
        send(title="喵子小屋签到", content=f"日志：{s.log()}\n签到结果：{sign}")
    else:
        print("请设置账号")
