# -*- coding:utf-8 -*-
"""
cron: 0 15 9 * * *
new Env('2048签到');
"""
import datetime
import random
import string

from scrapy import Selector

from base import BaseSign
from requests_toolbelt import MultipartEncoder


# from http.client import HTTPConnection
# HTTPConnection.debuglevel = 1
class LJDSign(BaseSign):
    # 自动回复列表
    auto_reply_msg = [
        "谢谢楼主分享！",
        "感谢分享"
        "感谢楼主分享！"
        "啧啧啧，有点东西"
    ]

    def __init__(self):
        super(LJDSign, self).__init__("https://www.epl80.net", app_name="2048", app_key="LJD", proxy=True)
        self.retry_times = 3
        # 支持的方法
        self.exec_method = ["auto_reply", "sign"]

    def login(self) -> bool:
        self.session.get(f"{self.base_url}/2048/")
        url = f"{self.base_url}/2048/login.php?"
        response = self.session.get(url)
        selector = Selector(response)

        verify_hash = selector.re(r"verifyhash = '(\w*?)'")
        if verify_hash:
            verify_hash = verify_hash[0]
        else:
            self.pwl("获取verifyhash失败")
            return False
        self.session.get(f"{self.base_url}/2048/login.php?action=quit&verify={verify_hash}")
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
            "lgt": "0",
            "pwuser": "as2674as",
            "pwpwd": "Wwrr2674996160",
            "question": "0",
            "customquest": "",
            "answer": "",
            "hideid": "0",
            "forward": "",
            "jumpurl": "http%3A%2F%2Fwww.epl80.net%2F2048%2Fsearch.php",
            "m": "bbs",
            "step": "2",
            "cktime": "31536000"
        }

        # 发送请求
        login_resp = self.session.post(url, headers=headers, data=data)
        login_resp.encoding = 'gzip'
        if login_resp.status_code == 200:
            resp_selector = Selector(response=login_resp)
            success_result = resp_selector.re(r"您已经顺利登录")
            if success_result is not None and len(success_result) > 0:
                self.session.get(f"{self.base_url}/2048/search.php")
                self.pwl("您已经顺利登录")
                return True
            return False
        return False

    def sign(self) -> bool:
        self.session.get(f"{self.base_url}/2048/hack.php?H_name=qiandao")
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded",
            "origin": f"{self.base_url}",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": f"{self.base_url}/2048/hack.php?H_name=qiandao",
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
        sign_resp = self.session.post(f"{self.base_url}/2048/hack.php?H_name=qiandao&", headers=headers, data=data)
        if sign_resp.status_code == 200:
            resp_selector = Selector(response=sign_resp)
            success_result = resp_selector.re(r"签到成功")
            if success_result is not None and len(success_result) > 0:
                self.session.get(f"{self.base_url}/2048/search.php")
                self.pwl("签到成功")
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
        url = f"{self.base_url}/2048/thread.php?fid=57"
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
        response.encoding = 'gzip'
        selector = Selector(response=response)
        tr_list = selector.xpath('//tr')
        times = 0
        i = 0
        for index, tr in enumerate(tr_list):
            class_name = tr.xpath('@class').extract()
            if len(class_name) == 0:
                continue
            if class_name[0] == "tr2":
                times += 1
                if times == 2:
                    i = index
                    break
        t_id = ''
        t_title = ''
        today_str = datetime.date.today().strftime("[%m-%d]")
        for tr_temp in tr_list[i + 2:]:
            for tal_td in tr_temp.xpath(".//td[@class='tal']"):
                num = tal_td.xpath(".//font[@color]").getall()
                if len(num) > 0:
                    continue
                # 获取当前日期格式化为 MM-DD
                target = tal_td.xpath("text()").get()
                if not target.startswith(today_str, 0, len(today_str)):
                    continue
                tid = tal_td.xpath("@id").extract_first()[3:]
                if len(tid) > 2:
                    t_id = tid
                    t_title = tal_td.xpath(".//a/text()").extract_first()
            # print(tr_temp.xpath("//td[@class='tal']/@id").text())
        result = f'read.php?tid={t_id}'
        self.pwl(f"第一个帖子链接：{result},标题:{t_title}")
        if t_id == '':
            return "", ""
        return self.base_url + "/2048/" + result, t_title

    def reply(self, target, title) -> bool:
        form_response = self.session.get(target)
        selector = Selector(response=form_response)
        form_data = {
            "atc_title": f"Re:00",
            "atc_content": random.choice(self.auto_reply_msg),
            "step": "2",
            "atc_desc1": "",
            'attachment_1': ('', b'', 'application/octet-stream'),
        }
        for i in selector.xpath('//*[@id="anchor"]/input'):
            form_data[i.xpath('@name').extract_first()] = i.xpath('@value').extract_first()
        hexie = selector.re(r"_hexie.value = '(.*?)';")
        if hexie is None or len(hexie) == 0:
            self.pwl("获取hexie失败")
            return False
        form_data["_hexie"] = hexie[0]
        # boundary = '----WebKitFormBoundary' \
        #            + ''.join(random.sample(string.ascii_letters + string.digits, 16))
        rand_boundary = ''.join(random.sample(string.ascii_letters + string.digits, 16))
        # m = MultipartEncoder(fields=form_data, boundary=boundary)
        data = f'''------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="atc_usesign"

{form_data['atc_usesign']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="atc_convert"

{form_data['atc_convert']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="atc_autourl"

{form_data['atc_autourl']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="step"

{form_data['step']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="action"

{form_data['action']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="fid"

{form_data['fid']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="tid"

{form_data['tid']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="verify"

94b8e230
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="_hexie"

{form_data['_hexie']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="atc_title"

{form_data['atc_title']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="atc_content"

{form_data['atc_content']}
------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="attachment_1"; filename=""
Content-Type: application/octet-stream


------WebKitFormBoundary{rand_boundary}
Content-Disposition: form-data; name="atc_desc1"


------WebKitFormBoundary{rand_boundary}--'''

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
            'Content-Type': f'multipart/form-data; boundary=----WebKitFormBoundary{rand_boundary}',
            "origin": f"{self.base_url}",
            "pragma": "no-cache",
            "priority": "u=0, i",
            "referer": f"{self.base_url}/2048/read.php?tid={form_data['tid']}",
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

        url = f"{self.base_url}/2048/post.php"
        # 发送请求
        send_resp = self.session.post(url, headers=headers, data=data)
        send_resp.encoding = 'gzip'
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
