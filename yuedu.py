# -*- coding:utf-8 -*-
"""
cron: 0 15 8 * * *
new Env('阅读论坛签到');
"""
from urllib.parse import quote

from scrapy import Selector

from gifcode import handle_yzm
from base import BaseSign


class YueDuSign(BaseSign):
    def __init__(self):
        super(YueDuSign, self).__init__("https://legado.cn/", app_name="阅读论坛", app_key="YUEDU")
        self.retry_times = 3
        # 登录配置
        self.login_type = "login_code"
        self.login_setting_code_type = "gif"
        self.login_setting_code_check = True
        self.login_page_path = "misc.php"
        self.session.cookies.set("is_agree", "1")
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'k_misign-sign.html'
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'
        self.sign_path = "plugin.php?id=k_misign:sign&operation=qiandao&format=empty&formhash=%s"
        self.sign_text_xpath = '//*[@id="wp"]//div[contains(text(),"签到")]/text()'
        self.sign_text = '您今天还没有签到'


if __name__ == "__main__":
    s = YueDuSign()
    s.run()
