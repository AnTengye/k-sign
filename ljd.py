# -*- coding:utf-8 -*-
"""
cron: 0 15 18 * * *
new Env('2048签到');
"""
import datetime
import io
import math
import os
import random
import re
import time
from urllib.parse import unquote, urljoin, urlsplit

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
        # 官方发布页：https://2046.info
        super(LJDSign, self).__init__("https://6gmz.735-yj3bfjz.shop", app_name="2048", app_key="LJD", proxy=False)
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
        page = self.session.get(f"{self.base_url}/hack.php?H_name=qiandao")
        if page.status_code != 200:
            self.pwl(f"签到页面请求失败：HTTP {page.status_code}")
            return False
        state = self._sign_state(page.text)
        if state is True:
            self.pwl("今天已签到")
            return True
        if state is None:
            self.pwl("无法读取当前账号签到状态，请检查登录状态或页面结构")
            return False
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
        if "qdCaptchaStart" in page.text:
            ticket = self._tencent_ticket()
            if not self._valid_ticket(ticket):
                self.pwl("未取得有效腾讯滑块票据，停止提交签到")
                return False
            data.update(hycode=ticket["ticket"], hyrandstr=ticket["randstr"])
        sign_resp = self.session.post(f"{self.base_url}/hack.php?H_name=qiandao&", headers=headers, data=data)
        if sign_resp.status_code == 200:
            if "必须绑定邮箱后才能签到" in sign_resp.text:
                self.pwl("签到失败：站点要求先绑定邮箱")
                return False
            if "今日未回复任何帖子" in sign_resp.text:
                self.pwl("签到失败：站点要求今日先回复一个帖子")
                return False
            if any(message in sign_resp.text for message in ("请完成滑块验证", "验证码不正确", "验证码错误", "滑块验证失败")):
                self.pwl("签到失败：站点拒绝腾讯滑块票据")
                return False
            confirmed = self.session.get(f"{self.base_url}/hack.php?H_name=qiandao")
            if confirmed.status_code == 200 and self._sign_state(confirmed.text) is True:
                self.pwl("签到成功，已回读当前账号状态")
                return True
            self.pwl("签到未确认：当前账号状态没有变为已签到")
        else:
            self.pwl(f"签到请求失败：HTTP {sign_resp.status_code}")
        # //*[@id="scbar_form"]/input[2]/@value
        return False

    @staticmethod
    def _sign_state(html):
        # 排行榜及“今日已签到人数”不代表当前账号的签到结果。
        summary = Selector(text=html).xpath('//td[text()[contains(., "您累计已签到")]]')
        text = ''.join(summary.xpath('.//text()').getall())
        match = re.search(r"【\s*(今天已签到|今天未签到)\s*】", text)
        return match.group(1) == "今天已签到" if match else None

    @staticmethod
    def _valid_ticket(result):
        return (isinstance(result, dict)
                and isinstance(result.get("ticket"), str) and bool(result["ticket"])
                and isinstance(result.get("randstr"), str) and bool(result["randstr"])
                and not result["ticket"].startswith(("trerror_", "terror_")))

    @staticmethod
    def _tencent_slider_distance(meta, background_bytes, sprite_bytes):
        import ddddocr
        from PIL import Image

        piece_meta = next(item for item in meta["items"]
                          if item["image"] != "none" and abs(item["w"] - item["h"]) < 1)
        sprite = Image.open(io.BytesIO(sprite_bytes))
        background = Image.open(io.BytesIO(background_bytes))
        sprite_scale = float(piece_meta["size"].split()[0].removesuffix("px")) / sprite.width
        background_scale = meta["bg"]["w"] / background.width
        left, top = [-float(value.removesuffix("px")) / sprite_scale for value in piece_meta["pos"].split()]
        piece = sprite.crop((round(left), round(top),
                             round(left + piece_meta["w"] / sprite_scale),
                             round(top + piece_meta["h"] / sprite_scale)))
        piece = piece.resize((round(piece_meta["w"] / background_scale), round(piece_meta["h"] / background_scale)))
        encoded = io.BytesIO()
        piece.save(encoded, format="PNG")
        matcher = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
        match = matcher.slide_match(encoded.getvalue(), background_bytes, simple_target=True)
        x, y, _, _ = match["target"]
        distance = x * background_scale - piece_meta["left"]
        if abs(y * background_scale - piece_meta["top"]) > 3 or not 0 < distance < meta["bg"]["w"] - piece_meta["w"]:
            raise ValueError("滑块定位结果超出有效范围")
        return distance

    def _tencent_ticket(self):
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
            from requests.utils import select_proxy
        except ImportError:
            self.pwl("腾讯滑块需要 Playwright 和 Chromium，请安装 requirements.txt 并执行 python3 -m playwright install --with-deps --only-shell chromium")
            return None

        try:
            with sync_playwright() as playwright:
                settings = self.session.merge_environment_settings(self.base_url, {}, False, None, None)
                proxy_url = select_proxy(self.base_url, settings["proxies"])
                proxy = None
                if proxy_url:
                    parsed = urlsplit(proxy_url)
                    proxy = {"server": f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")}
                    if parsed.username:
                        proxy.update(username=unquote(parsed.username), password=unquote(parsed.password or ""))
                browser = playwright.chromium.launch(headless=True, proxy=proxy, args=["--disable-dev-shm-usage"])
                try:
                    context = browser.new_context(user_agent=self.session.headers.get("User-Agent", self.user_agent),
                                                  locale="zh-CN", timezone_id="Asia/Shanghai",
                                                  viewport={"width": 1280, "height": 900})
                    context.add_cookies([
                        {"name": c.name, "value": c.value, "domain": c.domain or self.url_info.hostname,
                         "path": c.path or "/", "secure": c.secure}
                        for c in self.session.cookies if c.expires is None or c.expires > time.time()
                    ])
                    page = context.new_page()
                    page.set_default_timeout(15000)
                    images, verifications = {}, []

                    def remember(response):
                        path = urlsplit(response.url).path
                        if path == "/cap_union_new_getcapbysig":
                            images[response.url] = response
                        elif path == "/cap_union_new_verify":
                            verifications.append(response)

                    page.on("response", remember)
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    page.goto(f"{self.base_url}/hack.php?H_name=qiandao", wait_until="domcontentloaded", timeout=45000)
                    notice = page.locator("#pwDomainNoticeBtn")
                    if notice.is_visible():
                        notice.click()
                    page.wait_for_function("typeof qdCaptchaStart === 'function' && typeof TencentCaptcha === 'function'")
                    # 使用站点当前 SDK，只接管成功回调；票据仍由腾讯签发。
                    page.evaluate("""() => {
                        window.__signCaptchaResult = null;
                        qdDoSubmit = (type, ticket, randstr) => { window.__signCaptchaResult = {ticket, randstr}; };
                        document.querySelector('form[name="form2"] input[name="qdxq"][value="shuai"]').checked = true;
                        qdCaptchaStart('pc');
                    }""")
                    for attempt in range(2):
                        page.wait_for_function("!!window.__signCaptchaResult || !!document.querySelector('#tcaptcha_iframe_dy')")
                        immediate = page.evaluate("window.__signCaptchaResult")
                        if immediate:
                            return immediate if self._valid_ticket(immediate) else None
                        page.locator("#tcaptcha_iframe_dy").wait_for(state="visible")
                        frame = page.locator("#tcaptcha_iframe_dy").element_handle().content_frame()
                        frame.locator(".tc-slider-normal").wait_for(state="visible")
                        meta = frame.evaluate("""() => {
                            const read = e => { const s=getComputedStyle(e); return {image:s.backgroundImage,
                                size:s.backgroundSize,pos:s.backgroundPosition,w:parseFloat(s.width),
                                h:parseFloat(s.height),left:parseFloat(s.left),top:parseFloat(s.top)}; };
                            return {bg:read(document.querySelector('#slideBg')),
                                items:[...document.querySelectorAll('.tc-fg-item')].map(read)};
                        }""")
                        piece = next(item for item in meta["items"] if item["image"] != "none" and abs(item["w"] - item["h"]) < 1)

                        def image_bytes(css):
                            url = css[4:-1].strip('\"\'')
                            for _ in range(30):
                                if url in images:
                                    return images[url].body()
                                page.wait_for_timeout(100)
                            if url not in images:
                                raise ValueError("验证码图片尚未加载")

                        distance = self._tencent_slider_distance(meta, image_bytes(meta["bg"]["image"]), image_bytes(piece["image"]))
                        box = frame.locator(".tc-slider-normal").bounding_box()
                        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                        previous = len(verifications)
                        page.mouse.move(x, y)
                        page.mouse.down()
                        for step in range(1, 41):
                            page.mouse.move(x + distance * (1 - math.cos(math.pi * step / 40)) / 2, y)
                            page.wait_for_timeout(25)
                        page.mouse.up()
                        try:
                            page.wait_for_function("!!window.__signCaptchaResult", timeout=20000)
                        except BrowserTimeout:
                            code = verifications[-1].json().get("errorCode") if len(verifications) > previous else None
                            self.pwl(f"腾讯滑块未通过，错误码：{code if str(code).isdigit() else '未收到验证结果'}")
                            if str(code) == "50" and attempt == 0:
                                old_background = frame.locator("#slideBg").evaluate("e => getComputedStyle(e).backgroundImage")
                                frame.locator("#reload").click()
                                frame.wait_for_function("old => getComputedStyle(document.querySelector('#slideBg')).backgroundImage !== old", arg=old_background)
                                continue
                            return None
                        result = page.evaluate("window.__signCaptchaResult")
                        if self._valid_ticket(result):
                            self.pwl("腾讯滑块验证通过")
                            return result
                        return None
                finally:
                    browser.close()
        except Exception as error:
            # Playwright 异常可能包含带签名的 URL，不输出原始异常或票据。
            self.pwl(f"腾讯滑块处理失败（{type(error).__name__}），请检查浏览器依赖及网络")
        return None

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
