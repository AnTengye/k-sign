# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('moxing签到');
"""
from base import BaseSign


class MoxingSign(BaseSign):
    def __init__(self):
        super(MoxingSign, self).__init__("", app_name="moxing", app_key="MOXING", proxy=True)
        # 登录配置
        self.login_type = "login_code"
        self.login_setting_code_type = "gif"
        self.login_setting_code_check = True
        # 支持的方法
        self.exec_method = ["sign"]
        # 签到配置
        self.index_path = ''
        self.sign_path = "plugin.php?id=k_misign:sign&operation=qiandao&format=global_usernav_extra&formhash=%s&inajax=1&ajaxtarget=k_misign_topb"
        self.sign_text_xpath = '//*[@id="fx_checkin_b"]/@alt'
        self.sign_text = '点击签到'
        self.form_hash_xpath = '//*[@id="scbar_form"]/input[2]/@value'


if __name__ == "__main__":
    s = MoxingSign()
    s.run()
