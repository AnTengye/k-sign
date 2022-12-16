# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('JavPlater登录');
"""
import json
import os
import re
from urllib.parse import quote

from scrapy import Selector

from base import BaseSign
from gifcode import handle_yzm
from notify import send


class JavPlayerSign(BaseSign):
    def __init__(self):
        super(JavPlayerSign, self).__init__("http://javpcn.com", app_name="JavPlater", app_key="JAVPCN")
        # 支持的方法
        self.exec_method = []
        # 签到配置
        self.index_path = 'qiandao/'
        self.sign_text_xpath = '//*[@id="wp"]/div[3]/div[1]/div[1]/div/div[1]/text()'
        self.sign_text = '您今天还没有签到'
        self.sign_path = "qiandao/?mod=sign&operation=qiandao&formhash=%s&format=empty"
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'

    def login(self, times=3) -> bool:
        if times == 0:
            self.pwl("失败次数过多")
            return False
        print(f"进行 {self.username} 登录-times:{times}")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//input[@name="formhash"]/@value').extract_first("")
        sec_data = selector.re(r"updateseccode\('(\w*?)'")
        update_data = selector.re(r"update=([0-9]*)&")
        update = ""
        sec_hash = ""
        if len(sec_data) != 0:
            sec_hash = sec_data[0]
        if len(update_data) != 0:
            update = update_data[0]
        if sec_hash and form_hash:
            verify_code = self.code(sec_hash, update, 5)
            if not verify_code:
                return self.login(times - 1)
            url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LXMiL&inajax=1"
            payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fforum.php&loginfield=username&username={self.username}&password={self.password}&seccodehash={sec_hash}&seccodemodid=member%3A%3Alogging&seccodeverify={verify_code}&questionid=0&answer=&cookietime=2592000'
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
                result = result_selector.re(r'errorhandle_\((.*?),')
                print(result[0])
                return self.login(times - 1)
            else:
                self.session.get(jump_src[0])
                self.pwl(f'登录成功')
            return True
        else:
            self.pwl("链接访问异常")

    def code(self, sec_hash, update, times=3) -> str:
        if times == 0:
            self.pwl("错误次数过多")
            return ""
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
        payload = {}
        url = f"{self.base_url}/misc.php?mod=seccode&update={update}&idhash={sec_hash}"
        response = self.session.get(url, headers=headers, data=payload)
        result = handle_yzm(response.content)
        if result.encode().isalnum():
            check_url = f"{self.base_url}/misc.php?mod=seccode&action=check&inajax=1&modid=member::logging&idhash={sec_hash}&secverify={result}"
            check_payload = {}
            check_headers = {
                'authority': self.url_info.hostname,
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'referer': f'{self.base_url}/member.php?mod=logging&action=login',
                'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest'
            }
            check_response = self.session.get(check_url, headers=check_headers, data=check_payload)
            check_selector = Selector(response=check_response, type='xml')
            is_success = check_selector.re(r'succeed')
            if len(is_success) != 0:
                return result
            else:
                self.pwl(f"校验失败：{check_response.text}")
        return self.code(sec_hash, update, times - 1)


if __name__ == "__main__":
    s = JavPlayerSign()
    s.run()
