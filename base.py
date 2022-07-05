from urllib.parse import urlparse, ParseResult

import requests
from scrapy import Selector
import requests.packages.urllib3

requests.packages.urllib3.disable_warnings()


class BaseSign:
    session: requests.Session
    base_url: str
    url_info: ParseResult
    username: str
    password: str
    content: list

    def __init__(self, base_url, username, password):
        self.url_info = urlparse(base_url)
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session = requests.session()
        self.session.verify = False
        self.content = list()
        print(f"自助脚本初始化完成：{base_url}")

    def login(self) -> bool:
        print("需要实现")
        return False

    def sign(self) -> bool:
        qd_response = self.session.get(f"{self.base_url}/qiandao/")
        sign_selector = Selector(response=qd_response)
        sign_info = sign_selector.xpath('//*[@id="wp"]/div[2]/div[1]/div[1]/div/div[1]/text()').extract_first()
        if sign_info is None:
            sign_info = sign_selector.xpath('//*[@id="wp"]/div[3]/div[1]/div[1]/div/div[1]/text()').extract_first()
        self.pwl(sign_info.strip())
        if sign_info and sign_info.strip() == "您今天还没有签到":
            print("进行签到中...")
            form_hash = sign_selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first()
            if form_hash == "":
                print("获取签到表单验证失败")
                return False
            response = self.session.get(
                f"{self.base_url}/qiandao/?mod=sign&operation=qiandao&formhash={form_hash}&format=empty")
            result_selector = Selector(response=response)
            result = result_selector.xpath("/root/text()").extract_first()
            self.pwl(result)
            if result:
                print(f'签到失败：{result}')
                return False
            else:
                print('签到成功')
                return True
        # TODO:获取签到积分信息
        return True

    def pwl(self, c: str):
        print(c)
        if c:
            self.content.append(c)

    def log(self) -> str:
        return "\n".join(self.content)
