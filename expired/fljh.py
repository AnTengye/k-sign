# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('福利江湖-cookie登录');
"""
import json
import os
import re
from urllib.parse import quote

from scrapy import Selector

from base import BaseSign
from gifcode import handle_yzm
from notify import send


class FljhSign(BaseSign):
    """
    由于登录增加了google code，目前失效中
    """
    def __init__(self):
        super(FljhSign, self).__init__("https://fulijianghu.com", app_name="Fljh", app_key="FLJH", proxy=True)
        self.retry_times = 3
        # 登录配置
        self.login_type = "login_cookie"
        # 支持的方法
        self.exec_method = []


if __name__ == "__main__":
    s = FljhSign()
    s.run()
