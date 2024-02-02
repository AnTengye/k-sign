# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('JavPlater登录');
"""

from base import BaseSign


class JavPlayerSign(BaseSign):
    """
    由于登录增加了google code，目前失效中
    """

    def __init__(self):
        super(JavPlayerSign, self).__init__("https://javpcn.com", app_name="JavPlater", app_key="JAVPCN")
        self.retry_times = 3
        # 登录配置
        self.login_type = "login_cookie"
        # 支持的方法
        self.exec_method = []
        # 签到配置
        self.index_path = 'qiandao/'
        self.sign_text_xpath = '//*[@id="wp"]/div[3]/div[1]/div[1]/div/div[1]/text()'
        self.sign_text = '您今天还没有签到'
        self.sign_path = "qiandao/?mod=sign&operation=qiandao&formhash=%s&format=empty"
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'


if __name__ == "__main__":
    s = JavPlayerSign()
    s.run()
