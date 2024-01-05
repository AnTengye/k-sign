# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('4ksj签到');
"""

from base import BaseSign


class KsjSign(BaseSign):
    def __init__(self):
        super(KsjSign, self).__init__("https://www.4ksj.com", app_name="4K视界", app_key="4K")
        self.login_type = "login"
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'qiandao.php'
        self.sign_text_xpath = '//div[@class="ct2 cl"]/div[2]/div[1]/a/text()'
        self.sign_text = '点击打卡'
        self.sign_path = "qiandao.php?sign=%s"
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'


if __name__ == "__main__":
    s = KsjSign()
    s.run()
