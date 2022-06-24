import logging

import requests
from scrapy import Selector


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
        self.logger = logging.getLogger(name=None)  # 创建一个日志对象
        logging.Formatter("%(message)s")  # 日志内容格式化
        self.logger.setLevel(logging.INFO)  # 设置日志等级
        self.logger.addHandler(logging.StreamHandler())  # 添加控制台日志
        self.logger.info(f"自助脚本初始化完成：{base_url}")

    def login(self) -> bool:
        self.logger.info("需要实现")
        return False

    def sign(self) -> bool:
        qd_response = self.session.get(f"{self.base_url}/qiandao/")
        sign_selector = Selector(response=qd_response)
        sign_info = sign_selector.xpath('//*[@id="wp"]/div[2]/div[1]/div[1]/div/div[1]/text()').extract_first()
        if sign_info is None:
            sign_info = sign_selector.xpath('//*[@id="wp"]/div[3]/div[1]/div[1]/div/div[1]/text()').extract_first()
        self.logger.info(sign_info.strip())
        if sign_info and sign_info.strip() == "您今天还没有签到":
            self.logger.info("进行签到中...")
            form_hash = sign_selector.xpath('//*[@id="scbar_form"]/input[2]/@value').extract_first()
            if form_hash == "":
                self.logger.info("获取签到表单验证失败")
                return False
            response = self.session.get(
                f"{self.base_url}/qiandao/?mod=sign&operation=qiandao&formhash={form_hash}&format=empty")
            result_selector = Selector(response=response)
            result = result_selector.xpath("/root/text()").extract_first()
            if result:
                self.logger.info(f'签到失败：{result}')
                return False
            else:
                self.logger.info('签到成功')
                return True
        # TODO:获取签到积分信息
        return True
