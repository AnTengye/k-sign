# -*- coding:utf-8 -*-
"""
cron: 0 0 0 * * *
new Env('司机社签到');
"""

from base import BaseSign


class SiJiSSign(BaseSign):
    def __init__(self):
        super(SiJiSSign, self).__init__("https://sjs47.me", app_name="司机社", app_key="SJS", proxy=True)
        self.retry_times = 3
        self.login_type = "login_code"
        self.login_resp_success = r"succeedhandle_login\('(.*?)'"
        self.login_resp_error = r'errorhandle_login\((.*?),'
        self.login_page_path = "member.php?mod=logging&action=login&infloat=yes&handlekey=login&inajax=1&ajaxtarget=fwin_content_login"
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = 'k_misign-sign.html'
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'
        self.sign_path = "plugin.php?id=k_misign:sign&operation=qiandao&format=empty&formhash=%s"
        self.sign_text_xpath = '//*[@id="wp"]//div[contains(text(),"签到")]/text()'
        self.sign_text = '您今天还没有签到'

if __name__ == "__main__":
    s = SiJiSSign()
    s.run()
