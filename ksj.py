# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('4ksj签到');
"""
from urllib.parse import quote

from scrapy import Selector

from base import BaseSign


class KsjSign(BaseSign):
    def __init__(self):
        super(KsjSign, self).__init__("https://www.4ksj.com", app_name="4K视界", app_key="4K")
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'qiandao/'
        self.sign_text_xpath = '//*[@class="paiming cl"]/div[1]/text()'
        self.sign_text = '您今天还没有签到'
        self.sign_path = "qiandao/?mod=sign&operation=qiandao&formhash=%s&format=empty"
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'

    def login(self) -> bool:
        print(f"进行 {self.username} 登录")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first()
        url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LocOL&inajax=1"
        payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fportal.php&username={self.username}&password={self.password}&questionid=0&answer=&cookietime=2592000'
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,'
                      '*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/member.php?mod=logging&action=login',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/102.0.0.0 Safari/537.36 '
        }
        response = self.session.post(url, headers=headers, data=payload)
        result_selector = Selector(response=response)
        jump_src = result_selector.re(r'succeedhandle_\(\'(.*?)\',')
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_\((.*?),')
            print(result[0])
            return False
        else:
            self.session.get(jump_src[0])
        print(f'登录成功')
        return True


if __name__ == "__main__":
    s = KsjSign()
    s.run()
