# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('ACG次元小屋签到');
"""
import os
import time
from urllib.parse import quote

from scrapy import Selector

from base import BaseSign
from notify import send


class YuanACGSign(BaseSign):
    def __init__(self, username, password):
        super(YuanACGSign, self).__init__("https://note.yuanacg.com", username, password)

    def login(self) -> bool:
        print(f"进行 {self.username} 登录")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//form[@name="login"]/div/input[1]/@value').extract_first()
        url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=Lo37m&inajax=1"
        payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2Fforum.php&username={self.username}&password={self.password}&questionid=0&answer=&cookietime=2592000'
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

    def sign(self) -> bool:
        qd_response = self.session.get(f"{self.sign_url}")
        sign_selector = Selector(response=qd_response)
        sign_url = sign_selector.xpath('//*[@id="toptb"]/div/div[1]/a[3]/@href').extract_first()
        if sign_url is None:
            self.pwl("已签到,请不要重新签到！")
            return True
        click_qd_response = self.session.get(f"{self.base_url}/{sign_url}")
        click_selector = Selector(response=click_qd_response)
        result = click_selector.xpath('//*[@id="messagetext"]/p[1]/text()').extract_first()
        self.pwl(result)
        return True


if __name__ == "__main__":
    UP = os.getenv('SIGN_UP_YACG')
    if UP:
        user_info = UP.split("|")
        username = user_info[0]
        password = user_info[1]
        s = YuanACGSign(username, password)
        sign = False
        if s.login():
            sign = s.sign()
        send(title="YuanACG签到", content=f"日志：\n{s.log()}\n签到结果：{sign}")
    else:
        print("请设置账号")
