# -*- coding:utf-8 -*-
"""
cron: 0 0 20 * * *
new Env('2djgame签到');
"""
import json
import os
from urllib.parse import quote

from scrapy import Selector

from gifcode import handle_yzm
from notify import send
from base import BaseSign


class DJGameSign(BaseSign):
    char = "djgame_char.json"
    onnx = "djgame_cd.onnx"

    def __init__(self, username, password):
        super(DJGameSign, self).__init__("https://bbs4.2djgame.net/home", username, password, proxy=True)

    def login(self, times=3) -> bool:
        if times == 0:
            print("失败次数过多")
            return False
        print(f"进行 {self.username} 登录-times:{times}")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first("")
        sec_data = selector.re(r"updateseccode\('(\w*?)'")
        sec_hash = ""
        if len(sec_data) != 0:
            sec_hash = sec_data[0]
        if sec_hash and form_hash:
            verify_code = self.code(sec_hash, 5)
            if not verify_code:
                return self.login(times - 1)
            url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LzZ1M&inajax=1"
            payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2F.%2F&loginfield=username&username={self.username}&password={self.password}&questionid=0&answer=&sechash={sec_hash}&seccodeverify={verify_code}&cookietime=2592000'
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
            #
            result_selector = Selector(response=response)
            jump_src = result_selector.re(r"succeedhandle_\('(.*?)'")
            if len(jump_src) == 0:
                result = result_selector.re(r'errorhandle_\((.*?),')
                print(result[0])
                return self.login(times - 1)
            else:
                self.session.get(jump_src[0])
            print(f'登录成功')
            return True

    def code(self, sec_hash, times=3) -> str:
        if times == 0:
            print("错误次数过多")
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
        url = f"{self.base_url}/misc.php?mod=seccode&action=update&idhash={sec_hash}&inajax=1&ajaxtarget=seccode_{sec_hash}"
        response = self.session.get(url, headers=headers, data=payload)
        selector = Selector(response=response)
        code_url = selector.re(r'src="(.*?)"')
        if code_url:
            img_url = f"{self.base_url}/{code_url[0].replace('&amp;', '&')}"
            code_headers = {
                'authority': self.url_info.hostname,
                'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'accept-language': 'zh-CN,zh;q=0.9',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'referer': f'{self.base_url}/member.php?mod=logging&action=login',
                'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'image',
                'sec-fetch-mode': 'no-cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
            }
            response = self.session.get(img_url, headers=code_headers, data=payload)
            result = handle_yzm(response.content, self.char, self.onnx)
            if result.encode().isalnum():
                check_url = f"{self.base_url}/misc.php?mod=seccode&action=check&inajax=1&&idhash={sec_hash}&secverify={result}"
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
                    print(f"校验失败：{check_response.text}")
                    return self.code(sec_hash, times - 1)
            return self.code(sec_hash, times - 1)
        else:
            print(f"not found code url:{response.text}")
        return ""

    def sign(self) -> bool:
        sign_list = {
            "6": "今日之星",
            "5": "神之手",
            "1": "每日签到",
        }
        for k, v in sign_list.items():
            print(f"{v} 开始")
            url = f"{self.base_url}/home.php?mod=task&do=apply&id={k}"
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
            result = selector.xpath('//*[@id="messagetext"]/p[1]/text()').extract_first()
            self.pwl(f"{v} 结果：{result}")
        return True


if __name__ == "__main__":
    UP = os.getenv('SIGN_UP_2DJ')
    if UP:
        user_info = UP.split("|")
        username = user_info[0]
        password = user_info[1]
        s = DJGameSign(username, password)
        sign = False
        if s.login():
            sign = s.sign()
        send(title="2djgame签到", content=f"日志：{s.log()}\n签到结果：{sign}")
    else:
        print("请设置账号")
