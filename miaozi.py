# -*- coding:utf-8 -*-
"""
cron: 0 3 8,20 * * *
new Env('喵子小屋签到');
"""
import json
import os
import random
import re
from urllib.parse import quote

from scrapy import Selector

from gifcode import handle_yzm
from notify import send
from base import BaseSign


class MiaoSign(BaseSign):
    # 自动回复列表
    auto_reply_msg = [
        # {:7_234:}[color=Red]楼主发贴辛苦了，谢谢楼主分享！[/color]{:7_298:}
        "%0D%0A%7B%3A7_234%3A%7D%5Bcolor%3DRed%5D%E6%A5%BC%E4%B8%BB%E5%8F%91%E8%B4%B4%E8%BE%9B%E8%8B%A6%E4%BA%86%EF%BC%8C%E8%B0%A2%E8%B0%A2%E6%A5%BC%E4%B8%BB%E5%88%86%E4%BA%AB%EF%BC%81%5B%2Fcolor%5D%7B%3A7_298%3A%7D",
        # [color=Red]支持喵子小屋，Love Catcottage楼主辛苦了呢！[/color]{:7_234:}{:7_234:}{:7_234:}
        "%5Bcolor%3DRed%5D%E6%94%AF%E6%8C%81%E5%96%B5%E5%AD%90%E5%B0%8F%E5%B1%8B%EF%BC%8CLove%20Catcottage%E6%A5%BC%E4%B8%BB%E8%BE%9B%E8%8B%A6%E4%BA%86%E5%91%A2%EF%BC%81%5B%2Fcolor%5D%7B%3A7_234%3A%7D%7B%3A7_234%3A%7D%7B%3A7_234%3A%7D"
        # 楼主太厉害了！楼主辛苦了！{:7_233:}{:7_233:}{:7_233:}
        "%E6%A5%BC%E4%B8%BB%E5%A4%AA%E5%8E%89%E5%AE%B3%E4%BA%86%EF%BC%81%E6%A5%BC%E4%B8%BB%E8%BE%9B%E8%8B%A6%E4%BA%86%EF%BC%81%7B%3A7_233%3A%7D%7B%3A7_233%3A%7D%7B%3A7_233%3A%7D"
        # 这个帖子不回对不起自己！{:7_253:}
        "%E8%BF%99%E4%B8%AA%E5%B8%96%E5%AD%90%E4%B8%8D%E5%9B%9E%E5%AF%B9%E4%B8%8D%E8%B5%B7%E8%87%AA%E5%B7%B1%EF%BC%81%7B%3A7_253%3A%7D"
        # 这东西辣眼睛，不过还是下载看看！{:7_295:}{:7_255:}
        "%E8%BF%99%E4%B8%9C%E8%A5%BF%E8%BE%A3%E7%9C%BC%E7%9D%9B%EF%BC%8C%E4%B8%8D%E8%BF%87%E8%BF%98%E6%98%AF%E4%B8%8B%E8%BD%BD%E7%9C%8B%E7%9C%8B%EF%BC%81%7B%3A7_295%3A%7D%7B%3A7_255%3A%7D"
    ]

    def __init__(self):
        super(MiaoSign, self).__init__("https://forum.h3dhub.com", app_name="喵子小屋", app_key="MIAOZI")
        # 支持的方法
        self.exec_method = ["sign", "auto_reply"]

    def login(self, times=3) -> bool:
        if times == 0:
            print("失败次数过多")
            return False
        print(f"进行 {self.username} 登录-times:{times}")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first("")
        sec_data = selector.re(r"updateseccode\('(\w*?)'")
        update_data = selector.re(r"update=([0-9]*)&")
        sec_hash = ""
        update = "16626"
        if len(sec_data) != 0:
            sec_hash = sec_data[0]
        if len(update_data) != 0:
            update = update_data[0]
        if sec_hash and form_hash:
            verify_code = self.code(sec_hash, update)
            url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LwTq2&inajax=1"
            payload = f'formhash={form_hash}&referer={quote(self.base_url, safe="")}%2F.%2F&username={self.username}&password={self.password}&questionid=0&answer=&cookietime=2592000&seccodehash={sec_hash}&seccodemodid=member%3A%3Alogging&seccodeverify={verify_code}'
            headers = {
                'authority': self.url_info.hostname,
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'pragma': 'no-cache',
                'referer': f'{self.base_url}/member.php?mod=logging&action=login',
                'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
            }
            response = self.session.post(url, headers=headers, data=payload)
            result_selector = Selector(response=response)
            jump_src = result_selector.re(r"succeedhandle_\('(.*?)'")
            if len(jump_src) == 0:
                result = result_selector.re(r"errorhandle_\('(.*?)'")
                print(result[0])
                return self.login(times - 1)
            else:
                self.session.get(jump_src[0])
                print(f'登录成功')
            return True
        else:
            print(f"表单校验异常:{form_hash}-{sec_hash}")

    def code(self, sec_hash, update) -> str:
        url = f"{self.base_url}/misc.php?mod=seccode&update={update}&idhash={sec_hash}"
        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/member.php?mod=logging&action=login',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'image',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
        }
        response = self.session.get(url, headers=headers, data=payload)
        return handle_yzm(response.content)

    def sign(self) -> bool:
        print("每日签到开始")
        url = f"{self.base_url}/home.php?mod=task&do=apply&id=14"
        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/home.php?mod=task',
            'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
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
        result = selector.xpath('//*[@id="messagetext"]/p[1]/text()').extract_first("")
        self.pwl(f"结果：{result}")
        if "成功" in result:
            return True
        return False

    def auto_reply(self) -> bool:
        target = self.get_target()
        if target == "":
            self.pwl("帖子获取失败")
            return False
        return self.reply(target)

    def get_target(self) -> str:
        print("获取第一个帖子")
        # 团员活动2D区 forum-51-1.html
        url = f"{self.base_url}/forum-51-1.html"
        payload = {}
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': f'{self.base_url}',
            'sec-ch-ua': '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"',
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
        result = selector.xpath('//*[starts-with(@id, "normalthread_")][1]/tr/th/div[1]/span[1]/a/@href').extract_first(
            "")
        self.pwl(f"第一个帖子链接：{result}")
        if result is None:
            return ""
        return self.base_url + "/" + result

    def reply(self, target) -> bool:
        prog = re.compile(".*thread-(.*?)-")
        result = prog.match(target)
        tid = result.group(1)
        form_response = self.session.get(target)
        selector = Selector(response=form_response)
        form_hash = selector.xpath('//*[@id="scbar_form"]/input[@name="formhash"]/@value').extract_first()
        fid = selector.xpath('//*[@id="scbar_form"]/input[@name="srhfid"]/@value').extract_first()
        url = f"{self.base_url}/forum.php?mod=post&action=reply&fid={fid}&tid={tid}&extra=page%3D1&replysubmit=yes&infloat=yes&handlekey=fastpost&inajax=1"
        reply_msg = random.choice(self.auto_reply_msg)
        payload = f'select={reply_msg}&message={reply_msg}&formhash={form_hash}&usesig=1&subject='
        headers = {
            'authority': self.url_info.hostname,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': f'{self.base_url}',
            'pragma': 'no-cache',
            'referer': target,
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
        }
        response = self.session.post(url, headers=headers, data=payload)
        result_selector = Selector(response=response)
        jump_src = result_selector.re(r"succeedhandle_fastpost\('(.*?)'")
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_\((.*?),')
            if len(result) == 0:
                self.pwl(f'回复失败:{response.text}')
                return False
            self.pwl(result[0])
            return False
        else:
            self.pwl('回复成功')
        return True


if __name__ == "__main__":
    s = MiaoSign()
    s.run()
