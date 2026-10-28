# -*- coding:utf-8 -*-
"""
cron: 0 0 0 * * *
new Env('司机社签到');
"""

import os
from urllib.parse import urljoin

from scrapy import Selector

from base import BaseSign


class SiJiSSign(BaseSign):
    def __init__(self):
        super(SiJiSSign, self).__init__("https://xsijishe.net", app_name="司机社", app_key="SJS", proxy=True)
        self.retry_times = 3
        self.login_type = "login_cookie" if os.getenv("SIGN_COOKIE_SJS") else "login"
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

    def _login(self) -> bool:
        page = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        if page.status_code != 200:
            self.pwl(f"登录页面请求失败：HTTP {page.status_code}")
            return False
        selector = Selector(response=page)
        if selector.re(r"updateseccode\('\w+"):
            return self._code_login()
        form = selector.xpath('//form[.//input[@name="password"]]')
        form_hash = form.xpath('.//input[@name="formhash"]/@value').get()
        action = form.xpath('@action').get()
        if not form_hash or not action:
            self.pwl("未找到有效的登录表单")
            return False
        response = self.session.post(
            urljoin(page.url, action),
            params={"inajax": "1", "handlekey": "login"},
            data={"formhash": form_hash, "username": self.username, "password": self.password,
                  "questionid": "0", "answer": "", "cookietime": "2592000",
                  "referer": f"{self.base_url}/forum.php"},
        )
        result = Selector(response=response).re(self.login_resp_success)
        if response.status_code == 200 and result:
            self.session.get(urljoin(self.base_url, result[0]))
            self.pwl("登录成功")
            return True
        self.pwl(f"登录失败：HTTP {response.status_code}")
        return False

    def sign(self) -> bool:
        page = self.session.get(f"{self.base_url}/{self.index_path}")
        if page.status_code != 200:
            self.pwl(f"签到页面请求失败：HTTP {page.status_code}")
            return False
        selector = Selector(response=page)
        signed_xpath = '//span[contains(concat(" ",normalize-space(@class)," ")," btnvisted ")]'
        if selector.xpath(signed_xpath):
            self.pwl("今日已签到，已确认页面状态")
            return True
        form_hash = selector.xpath('//input[@name="formhash"]/@value').get()
        if not form_hash or not self._get_sign(form_hash):
            self.pwl("未确认签到成功")
            return False
        confirmed = self.session.get(f"{self.base_url}/{self.index_path}")
        if confirmed.status_code == 200 and Selector(response=confirmed).xpath(signed_xpath):
            self.pwl("签到成功，已回读今日签到状态")
            return True
        self.pwl("签到状态回读未确认成功")
        return False

if __name__ == "__main__":
    s = SiJiSSign()
    s.run()
