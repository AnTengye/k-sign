# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('moxing签到');
"""
from urllib.parse import quote

import requests
from scrapy import Selector

from base import BaseSign

class MoxingSign(BaseSign):
    def __init__(self):
        super(MoxingSign, self).__init__("", app_name="魔性论坛", app_key="MOXING", proxy=True)
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = ''
        self.sign_path = "plugin.php?id=k_misign:sign&operation=qiandao&format=global_usernav_extra&formhash=%s&inajax=1&ajaxtarget=k_misign_topb"
        self.sign_text_xpath = '//*[@id="fx_checkin_b"]/@alt'
        self.sign_text = '点击签到'
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'

    def login(self) -> bool:
        print(f"进行 {self.username} 登录")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//input[@name="formhash"]/@value').extract_first()
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
        jump_src = result_selector.re(r"succeedhandle_\('(.*?)'")
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_\((.*?),')
            if len(result) == 0:
                self.pwl(f'登录失败:{response.text}')
                return False
            self.pwl(result[0])
            return False
        else:
            self.sign_url = jump_src[0]
        self.pwl('登录成功')
        return True


if __name__ == "__main__":
    s = MoxingSign()
    s.run()
