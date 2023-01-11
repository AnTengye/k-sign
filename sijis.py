# -*- coding:utf-8 -*-
"""
cron: 0 0 0 * * *
new Env('司机社签到');
"""
from urllib.parse import quote

from scrapy import Selector

from base import BaseSign, CipherSuiteAdapter


class SiJiSSign(BaseSign):
    def __init__(self):
        super(SiJiSSign, self).__init__("https://sijishea.com", app_name="司机社", app_key="SJS", proxy=True)
        self.login_retry = 3
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'k_misign-sign.html'
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'
        self.sign_path = "plugin.php?id=k_misign:sign&operation=qiandao&format=empty&formhash=%s"
        self.sign_text_xpath = '//*[@id="wp"]//div[contains(text(),"签到")]/text()'
        self.sign_text = '您今天还没有签到'

    def login(self) -> bool:
        if self.login_retry <= 0:
            return False
        print(f"进行 {self.username} 登录")
        response = self.session.get(f"{self.base_url}")
        selector = Selector(response=response)
        form_hash = selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first()
        if form_hash is None:
            print("页面", response.text)
            self.pwl("页面变更")
            self.login_retry -= 1
            return self.login()
        url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&handlekey=login&loginhash=LocOL&inajax=1"
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
        }
        response = self.session.post(url, headers=headers, data=payload)
        result_selector = Selector(response=response)
        jump_src = result_selector.re(r"succeedhandle_\('(.*?)'")
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_\((.*?),')
            if len(result) == 0:
                self.pwl(f'登录失败:{response.text}')
            else:
                self.pwl(result[0])
            self.login_retry -= 1
            return self.login()
        self.sign_url = jump_src[0]
        self.pwl('登录成功')
        return True


if __name__ == "__main__":
    s = SiJiSSign()
    s.run()
