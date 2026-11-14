# -*- coding:utf-8 -*-
"""
欧洲GO登录及 Cookie 导出示例，默认不登录，不注册青龙定时任务。

SIGN_UP_EURGO：账号密码，格式为 用户名|密码（必填）。
SIGN_URL_EURGO：可选，默认 https://www.eurgo.com。
SIGN_PROXY_EURGO / SIGN_UP_PROXY：沿用 BaseSign 的代理配置。
在仓库根目录手动运行 python3 -m examples.eurgo --run，验证登录态后输出 Cookie: ...。
Cookie 不加入 self.pwl() 日志或消息通知。
"""
import argparse
import re
import sys
from urllib.parse import urljoin, urlparse

from requests import Request
from requests.packages.urllib3.util.retry import Retry
from scrapy import Selector

from base import BaseSign
from gifcode import handle_yzm


class EurgoSign(BaseSign):
    def __init__(self):
        super().__init__("https://www.eurgo.com", app_name="欧洲GO登录", app_key="EURGO")
        if not self.password:
            raise ValueError("密码不能为空，请检查 SIGN_UP_EURGO")
        self.url_info = self.url_info._replace(path="", params="", query="", fragment="")
        self.base_url = self.url_info.geturl()
        self.order_url = f"{self.base_url}/member/order/list.aspx"
        self.exec_method = []
        self.retry_times = 1  # 仅验证码错误可重试，避免重复提交错误密码。
        self.cookie_header = ""
        for adapter in self.session.adapters.values():
            adapter.max_retries = Retry(total=0)

    def login(self) -> bool:
        self.cookie_header = ""
        for attempt in range(1, 4):
            response = self.session.get(
                f"{self.base_url}/member/login.aspx",
                params={"returnUrl": self.order_url},
                allow_redirects=False,
            )
            if response.status_code != 200:
                self.pwl(f"登录页面请求失败：HTTP {response.status_code}")
                return False
            form = Selector(text=response.text).xpath('//form[@id="aspnetForm"]')
            data = {
                item.xpath("@name").get(): item.xpath("@value").get("")
                for item in form.xpath('.//input[@type="hidden" and @name]')
            }
            username_field = form.xpath('.//input[contains(@name, "$txtUserName")]/@name').get()
            password_field = form.xpath('.//input[@type="password"]/@name').get()
            submit = form.xpath('.//input[@type="submit"]')
            submit_field = submit.xpath("@name").get()
            if not all((data.get("__VIEWSTATE"), data.get("__EVENTVALIDATION"),
                        username_field, password_field, submit_field)):
                self.pwl("登录表单不完整，网站可能发生变更")
                return False
            action_url = urljoin(response.url, form.xpath("@action").get(""))
            if urlparse(action_url).netloc != self.url_info.netloc or urlparse(action_url).scheme != self.url_info.scheme:
                self.pwl("登录表单地址异常，停止提交账号密码")
                return False

            image = self.session.get(f"{self.base_url}/GetCode.aspx", headers={"Referer": response.url})
            if image.status_code != 200:
                self.pwl(f"验证码请求失败：HTTP {image.status_code}")
                return False
            # 站点返回单帧 GIF，需要按普通图片识别。
            code = handle_yzm(image.content, t="img").strip()
            if not re.fullmatch(r"[A-Za-z0-9]{4}", code):
                self.pwl(f"验证码识别不完整，重新获取（{attempt}/3）")
                continue
            data.update({username_field: self.username, password_field: self.password,
                         submit_field: submit.xpath("@value").get("立即登录"),
                         "getcode": code, "remeberMe": "true"})
            posted = self.session.post(
                action_url, data=data, allow_redirects=False,
                headers={"Origin": self.base_url, "Referer": response.url},
            )
            if posted.status_code not in (200, 302, 303):
                self.pwl(f"登录提交失败：HTTP {posted.status_code}")
                return False
            selector = Selector(text=posted.text)
            messages = selector.xpath('//*[@id="error"]//text()').getall()
            messages += re.findall(r"\balert\s*\(\s*['\"]([^'\"]*)['\"]", posted.text)
            if any("验证码" in message for message in messages):
                self.pwl(f"验证码未通过，重新获取（{attempt}/3）")
                continue

            # 不以 HTTP 200/302 判成功，必须能访问受保护的订单页。
            order = self.session.get(self.order_url, allow_redirects=False)
            page = Selector(text=order.text)
            if (order.status_code != 200
                    or not page.xpath('//title[contains(., "我的运单")]')
                    or not page.xpath('//*[contains(@id, "lbl_waybillsCount")]')
                    or page.xpath('//input[@type="password"]')):
                self.pwl("登录态校验失败，请检查账号密码或站点登录要求")
                return False
            prepared = self.session.prepare_request(Request("GET", self.order_url))
            self.cookie_header = prepared.headers.get("Cookie", "")
            if not self.cookie_header:
                self.pwl("订单页校验通过，但未获取到 Cookie")
                return False
            self.pwl("登录成功，订单页登录态校验通过")
            return True
        self.pwl("验证码连续三次未通过，请稍后重新运行")
        return False


def main():
    parser = argparse.ArgumentParser(description="欧洲GO登录示例，默认仅显示用法，不发起登录请求。")
    parser.add_argument("--run", action="store_true", help="手动执行登录并输出 Cookie")
    args = parser.parse_args()
    if not args.run:
        parser.print_help()
        return
    s = EurgoSign()
    try:
        s.run()
        # 用户要求导出 Cookie；单独输出，避免进入通知内容。
        sys.stdout.write(f"Cookie: {s.cookie_header}\n")
    finally:
        s.session.close()


if __name__ == "__main__":
    main()
