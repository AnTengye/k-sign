# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('ACG次元小屋签到');
"""

from scrapy import Selector

from base import BaseSign


class YuanACGSign(BaseSign):
    def __init__(self):
        super(YuanACGSign, self).__init__("https://south.yuanacg.com", app_name="ACG次元小屋", app_key="YACG")
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.exec_method = ["sign"]

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
    s = YuanACGSign()
    s.run()
