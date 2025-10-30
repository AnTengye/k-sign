# -*- coding:utf-8 -*-
"""
cron: 0 0 9 * * *
new Env('哥特萝莉签到');
"""
from urllib.parse import quote

from scrapy import Selector

from gifcode import handle_yzm
from base import BaseSign, CipherSuiteAdapter


class GTloliSign(BaseSign):
    def __init__(self):
        super(GTloliSign, self).__init__("https://www.gtloli.gay", app_name="哥特萝莉", app_key="GTLL",
                                         proxy=True)
        self.retry_times = 2
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36"})
        adapter = CipherSuiteAdapter(server_hostname=self.url_info.hostname)
        self.session.mount(self.base_url, adapter)
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'forum.php'
        self.form_hash_xpath = '//input[@name="formhash"]/@value'
        self.sign_path = "plugin.php?id=k_misign:sign&operation=qiandao&format=button&formhash=%s"
        self.sign_text_xpath = '//*[@id="JD_sign"]/div/text()'
        self.sign_text = '签到'

    def login(self) -> bool:
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login&referer=https%3A%2F%2F{self.url_info.hostname}%2Fhome.php%3Fmod%3Dspace%26uid%3D344248%26do%3Dprofile%26mycenter%3D1%26navactivate%3Dwd%26mobile%3D2")
        selector = Selector(response=response)
        form_hash = selector.xpath('//input[@name="formhash"]/@value').extract_first("")
        sec_hash = selector.xpath('//input[@name="seccodehash"]/@value').extract_first("")
        update_data = selector.re(r"update=([0-9]*)&")
        update = ""
        if len(update_data) != 0:
            update = update_data[0]
        login_hash_text = selector.xpath('//select[contains(@id,"questionid_")]/@id').extract_first("")
        login_hash = ""
        if login_hash_text is not None:
            login_hash = login_hash_text[len("questionid_"):]
        if sec_hash and form_hash:
            verify_code = self.code(sec_hash, update, 5)
            if not verify_code:
                return False
            url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash={login_hash}&inajax=1&mobile=2"
            payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fhome.php%3Fmod%3Dspace%26uid%3D344248%26do%3Dprofile%26mycenter%3D1%26navactivate%3Dwd%26mobile%3D2&fastloginfield=username&cookietime=2592000&username={self.username}&password={self.password}&questionid=0&answer=&seccodehash={sec_hash}&seccodeverify={verify_code}'
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
            }
            response = self.session.post(url, headers=headers, data=payload)
            result_selector = Selector(response=response)
            jump_src = result_selector.re(r"window.location.href='(.*?)'")
            if len(jump_src) == 0:
                print(response.text)
                return False
            else:
                self.session.get(jump_src[0])
                self.pwl(f'登录成功')
                self.session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"})
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
        }
        payload = {}
        url = f"{self.base_url}/misc.php?mod=seccode&update={update}&idhash={sec_hash}&mobile=2"
        response = self.session.get(url, headers=headers, data=payload)
        result = handle_yzm(response.content, t="img")
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
    s = GTloliSign()
    s.run()
