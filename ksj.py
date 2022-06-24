import logging
import os
import sys
import traceback

import requests
from scrapy import Selector

logger = logging.getLogger(name=None)  # 创建一个日志对象
logging.Formatter("%(message)s")  # 日志内容格式化
logger.setLevel(logging.INFO)  # 设置日志等级
logger.addHandler(logging.StreamHandler())  # 添加控制台日志


class BaseSign:
    session: requests.Session
    base_url: str
    username: str
    password: str

    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = requests.session()
        logger.info(f"自助脚本初始化完成：{base_url}")

    def login(self) -> bool:
        logger.info("需要实现")
        return False

    def sign(self) -> bool:
        qd_response = self.session.get(f"{self.base_url}/qiandao/")
        sign_selector = Selector(response=qd_response)
        sign_info = sign_selector.xpath('//*[@id="wp"]/div[2]/div[1]/div[1]/div/div[1]/text()').extract_first()
        if sign_info is None:
            sign_info = sign_selector.xpath('//*[@id="wp"]/div[3]/div[1]/div[1]/div/div[1]/text()').extract_first()
        logger.info(sign_info.strip())
        if sign_info and sign_info.strip() == "您今天还没有签到":
            logger.info("进行签到中...")
            form_hash = sign_selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first()
            if form_hash == "":
                logger.info("获取签到表单验证失败")
                return False
            response = self.session.get(
                f"{self.base_url}/qiandao/?mod=sign&operation=qiandao&formhash={form_hash}&format=empty")
            result_selector = Selector(response=response)
            result = result_selector.xpath("/root/text()").extract_first()
            if result:
                logger.info(f'签到失败：{result}')
                return False
            else:
                logger.info('签到成功')
                return True
        # TODO:获取签到积分信息
        return True


class KsjSign(BaseSign):
    def __init__(self, username, password):
        super(KsjSign, self).__init__("https://www.4ksj.com", username, password)

    def login(self) -> bool:
        logger.info(f"进行 {self.username} 登录")
        response = self.session.get(f"{self.base_url}/member.php?mod=logging&action=login")
        selector = Selector(response=response)
        form_hash = selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first()
        url = f"{self.base_url}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash=LocOL&inajax=1"
        payload = f'formhash={form_hash}&referer=https%3A%2F%2Fwww.4ksj.com%2Fportal.php&username={self.username}&password={self.password}&questionid=0&answer=&cookietime=2592000'
        headers = {
            'authority': self.base_url[8:],
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,'
                      '*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'pragma': 'no-cache',
            'referer': f'{self.base_url}/member.php?mod=logging&action=login',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102", "Google Chrome";v="102"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/102.0.0.0 Safari/537.36 '
        }
        response = self.session.post(url, headers=headers, data=payload)
        result_selector = Selector(response=response)
        jump_src = result_selector.re(r'src="(.*?)"')
        if len(jump_src) == 0:
            result = result_selector.re(r'errorhandle_\((.*?),')
            logger.info(result[0])
            return False
        else:
            self.session.get(jump_src[0])
        logger.info(f'登录成功')
        return True


def load_send() -> None:
    logger.info("加载推送功能中...")
    global send
    send = None
    cur_path = os.path.abspath(os.path.dirname(__file__))
    sys.path.append(cur_path)
    if os.path.exists(cur_path + "/notify.py"):
        try:
            from notify import send
        except Exception:
            send = None
            logger.info(f"❌加载通知服务失败!!!\n{traceback.format_exc()}")


if __name__ == "__main__":
    load_send()
    username = os.getenv('SIGN_USERNAME')
    password = os.getenv('SIGN_PASSWORD')
    if username and password:
        ksj = KsjSign(username, password)
        if ksj.login():
            send(f"签到结果：{ksj.sign()}")
    else:
        logger.info("请设置账号")
