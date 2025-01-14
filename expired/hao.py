# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('hao4k签到');
"""
from urllib.parse import quote
from base import BaseSign
from tools import re_handler, FORM_HASH


class HaoSign(BaseSign):
    def __init__(self):
        super(HaoSign, self).__init__("https://www.hao4k.com", app_name="hao4k", app_key="4K", timeout=10)
        self.retry_times = 3
        # 支持的方法
        self.login_type = "login"
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'qiandao.php'
        self.sign_text_xpath = '//div[@class="ct2 cl"]/div[2]/div[1]/a/text()'
        self.sign_text = '点击打卡'
        self.sign_path = "qiandao.php?sign=%s"
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'

    def _login(self) -> bool:
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        form_hash = re_handler(FORM_HASH, response.text)
        if form_hash:
            url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&handlekey=login&loginhash=LO2CJ&inajax=1"
            payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fqiandao.php&username={self.username}&password={self.password}&questionid=0&answer='
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
            if response.status_code == 200:
                return True
            self.pwl('登录失败' + response.text)
            return False

        else:
            self.pwl(f"页面元素获取失败:form_hash {form_hash}")
            return False


if __name__ == "__main__":
    s = HaoSign()
    s.run()
