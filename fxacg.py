# -*- coding:utf-8 -*-
"""
cron: 0 15 8 * * *
new Env('飞雪acg签到');
"""
from base import BaseSign


class FXAcgSign(BaseSign):
    def __init__(self):
        super(FXAcgSign, self).__init__("https://fxacg.cc", app_name="飞雪ACG", app_key="FXACG",
                                        proxy=True)

        self.retry_times = 3
        # 登录配置
        self.login_type = "login_code"
        self.login_setting_code_type = "img"
        self.login_setting_code_check = True
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'dc_signin-dc_signin.html'
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'
        self.sign_path = "plugin.php?id=dc_signin:sign"
        self.sign_text_xpath = '//*[@id="dcsignin"]/div[2]/div[2]/div/a/text()'
        self.sign_text = '签到'
        self.sign_method = 'post'



if __name__ == "__main__":
    s = FXAcgSign()
    s.run()
