# -*- coding:utf-8 -*-
"""
cron: 0 15 18 * * *
new Env('2048签到');
"""
import datetime
import os
import random
import re
from urllib.parse import urljoin

from scrapy import Selector

from base import BaseSign


# from http.client import HTTPConnection
# HTTPConnection.debuglevel = 1
class LJDSign(BaseSign):
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    # 自动回复列表
    auto_reply_msg = [
        "gan xie luo zhu fen xiang",
        "ganxiefenxiang",
        "ganxielouzhufenxiang!"
    ]

    def __init__(self):
        # 站点当前证书已过期，暂时只对该站点关闭校验，避免影响其他任务。
        super(LJDSign, self).__init__("https://www.epl80.net", app_name="2048", app_key="LJD", proxy=False,
                                      verify=False)
        self.retry_times = 3
        self.login_type = "login_cookie" if os.getenv("SIGN_COOKIE_LJD") else "login"
        self.session.headers.update({"User-Agent": self.user_agent})
        # 支持的方法
        self.exec_method = ["auto_reply", "sign"]

    def login(self) -> bool:
        if self.login_type == "login_cookie":
            return self._cookie_login()
        self.session.get(f"{self.base_url}/")
        login_page_url = f"{self.base_url}/login.php?"
        response = self.session.get(login_page_url)
        response = self.pass_safe_challenge(response, login_page_url)
        selector = Selector(response)

        verify_hash = selector.re(r"verifyhash = '(\w*?)'")
        if verify_hash:
            verify_hash = verify_hash[0]
        else:
            self.pwl("获取verifyhash失败")
            return False
        self.session.get(f"{self.base_url}/login.php?action=quit&verify={verify_hash}")
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "origin": f"{self.base_url}",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": f"{self.base_url}/2048/search.php?",
            "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        }

        # 请求数据
        data = {
            "forward": "",
            "lgt": "0",
            "pwuser": self.username,
            "pwpwd": self.password,
            "ticket": "",
            "randstr": "",
            "customquest": "",
            "answer": "",
            "hideid": "0",
            "jumpurl": f"{self.base_url}/index.php",
            "step": "2",
            "cktime": "31536000",
            "submit": "登录",
        }

        # 发送请求
        login_resp = self.session.post(f"{self.base_url}/login.php?", headers=headers, data=data)
        if login_resp.status_code == 200:
            resp_selector = Selector(response=login_resp)
            success_result = resp_selector.re(r"您已经顺利登录")
            if success_result is not None and len(success_result) > 0:
                self.session.get(f"{self.base_url}/search.php")
                self.pwl("您已经顺利登录")
                return True
            return False
        return False

    def pass_safe_challenge(self, response, retry_url):
        if "safeid='" not in response.text or "verifyhash" in response.text:
            return response
        result = re.search(r"safeid='([^']+)'", response.text)
        if not result:
            return response
        safe_id = result.group(1)
        self.session.cookies.set("_safe", safe_id, domain=self.url_info.hostname, path="/")
        self.pwl("已处理安全挑战页")
        return self.session.get(retry_url)

    def sign(self) -> bool:
        self.session.get(f"{self.base_url}/hack.php?H_name=qiandao")
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "origin": f"{self.base_url}",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": f"{self.base_url}/hack.php?H_name=qiandao",
            "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        }

        # 请求数据
        data = {
            "action": "qiandao",
            "qdxq": "shuai",
            "hycode": "",
            "hyrandstr": "",
        }
        sign_resp = self.session.post(f"{self.base_url}/hack.php?H_name=qiandao&", headers=headers, data=data)
        if sign_resp.status_code == 200:
            resp_selector = Selector(response=sign_resp)
            success_result = resp_selector.re(r"签到成功|已经签到|今日已签到")
            if success_result is not None and len(success_result) > 0:
                self.session.get(f"{self.base_url}/search.php")
                self.pwl(success_result[0])
                return True
        # //*[@id="scbar_form"]/input[2]/@value
        return False

    def auto_reply(self) -> bool:
        target, title = self.get_target()
        if target == "":
            self.pwl("帖子获取失败")
            return False
        return self.reply(target, title)

    def get_target(self) -> (str, str):
        self.pwl("获取第一个帖子")
        url = f"{self.base_url}/thread.php?fid=57"
        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
        }
        response = self.session.get(url, headers=headers, data=payload)
        selector = Selector(response=response)
        t_id = ''
        t_title = ''
        today_str = datetime.date.today().strftime("[%m-%d]")
        for tal_td in selector.xpath('//td[contains(@class,"tal")][@id][starts-with(@id,"td_")]'):
            row_text = ''.join(tal_td.xpath(".//text()").getall()).strip()
            if not row_text.startswith(today_str):
                continue
            tid = tal_td.xpath("@id").extract_first()[3:]
            title = ''.join(
                tal_td.xpath('.//a[contains(@href,"read.php?tid=")][contains(@class,"subject")]//text()').getall()
            ).strip()
            if len(tid) > 2 and title:
                t_id = tid
                t_title = title
                break
        result = self.build_read_url(t_id)
        self.pwl(f"第一个帖子链接：{result},标题:{t_title}")
        if t_id == '':
            return "", ""
        return result, t_title

    def build_read_url(self, tid: str) -> str:
        return f"{self.base_url}/read.php?tid={tid}"

    def extract_reply_form(self, html: str):
        selector = Selector(text=html)
        form = selector.xpath('//form[@name="FORM" or @id="FORM"]')
        if not form:
            form = selector.xpath('//form[.//input[@name="action" and @value="reply"]]')
        if not form:
            return "", {}
        form = form[0]
        action = form.xpath("@action").extract_first() or "post.php"
        fields = {}
        for item in form.xpath('.//input[@name]'):
            name = item.xpath("@name").extract_first()
            fields[name] = item.xpath("@value").extract_first("") or ""
        return action, fields

    def reply(self, target, title) -> bool:
        form_response = self.session.get(target)
        action, form_fields = self.extract_reply_form(form_response.text)
        if action == "" or not form_fields:
            self.pwl("获取回复表单失败")
            return False
        form_data = {
            **form_fields,
            "atc_title": f"Re:00",
            "atc_content": random.choice(self.auto_reply_msg),
            "atc_desc1": "",
        }
        if not form_data.get("_hexie") or not form_data.get("verify"):
            self.pwl("获取hexie失败")
            return False
        # 构造cookie
        append_cookie = {
            'zh_choose': 'n',
            'a22e7_jobpop': '0',
            'a22e7_qdstart': '1',
            'istip_57': '1',
        }
        self.session.cookies.update(append_cookie)
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "origin": f"{self.base_url}",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": target,
            "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        }

        url = urljoin(f"{self.base_url}/", action)
        # 发送请求
        send_resp = self.session.post(
            url,
            headers=headers,
            data=form_data,
            files={"attachment_1": ("", b"", "application/octet-stream")},
        )
        if send_resp.status_code == 200:
            result_selector = Selector(response=send_resp)
            jump_src = result_selector.re(r"发帖完毕")
            if len(jump_src) == 0:
                self.pwl(f'回复失败')
                return False
            else:
                self.pwl('回复成功')
                return True
        self.pwl(f'响应状态{send_resp.status_code}')
        return False


if __name__ == "__main__":
    s = LJDSign()
    s.run()
