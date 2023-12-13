# -*- coding:utf-8 -*-
"""
cron: 0 0 8 * * *
new Env('hostloc签到');
"""
import random
import re
import textwrap
import time

import requests

from base import BaseSign
from pyaes import AESModeOfOperationCBC


class HostlocSign(BaseSign):
    def __init__(self):
        super(HostlocSign, self).__init__("https://hostloc.com", app_name="hostloc", app_key="HOSTLOC")
        # 登录配置
        self.login_type = "login"
        # 支持的方法
        self.exec_method = ["get_info"]

    # 抓取并打印输出帐户当前积分
    def print_current_points(self):
        res = self.session.get(f"{self.base_url}/forum.php")
        res.raise_for_status()
        res.encoding = "utf-8"
        points = re.findall("积分: (\d+)", res.text)

        if len(points) != 0:  # 确保正则匹配到了内容，防止出现数组索引越界的情况
            self.pwl("帐户当前积分：" + points[0])
        else:
            self.pwl("无法获取帐户积分，可能页面存在错误或者未登录！")
        time.sleep(5)

    def get_info(self):
        self.print_current_points()  # 打印帐户当前积分
        url_list = self.randomly_gen_uspace_url()
        # 依次访问用户空间链接获取积分，出现错误时不中断程序继续尝试访问下一个链接
        success = 0
        for i in range(len(url_list)):
            url = url_list[i]
            try:
                res = self.session.get(url)
                res.raise_for_status()
                time.sleep(5)  # 每访问一个链接后休眠5秒，以避免触发论坛的防CC机制
                success += 1
            except Exception as e:
                self.pwl("链接访问异常：" + str(e))
            continue
        self.pwl(f"用户空间链接访问成功数:{success}")
        self.print_current_points()  # 再次打印帐户当前积分

    # 随机生成用户空间链接
    def randomly_gen_uspace_url(self) -> list:
        url_list = []
        # 访问小黑屋用户空间不会获得积分、生成的随机数可能会重复，这里多生成两个链接用作冗余
        for i in range(12):
            uid = random.randint(20000, 60000)
            url = f"{self.base_url}/space-uid-{str(uid)}.html"
            url_list.append(url)
        return url_list

    # 使用Python实现防CC验证页面中JS写的的toNumbers函数
    def toNumbers(self, secret: str) -> list:
        text = []
        for value in textwrap.wrap(secret, 2):
            text.append(int(value, 16))
        return text

    # 不带Cookies访问论坛首页，检查是否开启了防CC机制，将开启状态、AES计算所需的参数全部放在一个字典中返回
    def check_anti_cc(self) -> dict:
        result_dict = {}
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
        }
        home_page = f"{self.base_url}/forum.php"
        res = requests.get(home_page, headers=headers)
        aes_keys = re.findall('toNumbers\("(.*?)"\)', res.text)
        cookie_name = re.findall('cookie="(.*?)="', res.text)

        if len(aes_keys) != 0:  # 开启了防CC机制
            self.pwl("检测到防 CC 机制开启！")
            if len(aes_keys) != 3 or len(cookie_name) != 1:  # 正则表达式匹配到了参数，但是参数个数不对（不正常的情况）
                result_dict["ok"] = 0
            else:  # 匹配正常时将参数存到result_dict中
                result_dict["ok"] = 1
                result_dict["cookie_name"] = cookie_name[0]
                result_dict["a"] = aes_keys[0]
                result_dict["b"] = aes_keys[1]
                result_dict["c"] = aes_keys[2]
        else:
            pass

        return result_dict

    # 在开启了防CC机制时使用获取到的数据进行AES解密计算生成一条Cookie（未开启防CC机制时返回空Cookies）
    def pre(self):
        cookies = {}
        anti_cc_status = self.check_anti_cc()

        if anti_cc_status:  # 不为空，代表开启了防CC机制
            if anti_cc_status["ok"] == 0:
                self.pwl("防 CC 验证过程所需参数不符合要求，页面可能存在错误！")

            else:  # 使用获取到的三个值进行AES Cipher-Block Chaining解密计算以生成特定的Cookie值用于通过防CC验证
                self.pwl("自动模拟计尝试通过防 CC 验证")
                a = bytes(self.toNumbers(anti_cc_status["a"]))
                b = bytes(self.toNumbers(anti_cc_status["b"]))
                c = bytes(self.toNumbers(anti_cc_status["c"]))
                cbc_mode = AESModeOfOperationCBC(a, b)
                result = cbc_mode.decrypt(c)

                name = anti_cc_status["cookie_name"]
                cookies[name] = result.hex()
        else:
            pass

        self.session.cookies.update(cookies)


if __name__ == "__main__":
    s = HostlocSign()
    s.run()
