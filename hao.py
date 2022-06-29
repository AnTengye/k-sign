import os

from sign.hao import HaoSign
from notify import send

if __name__ == "__main__":
    username = os.getenv('SIGN_USERNAME')
    password = os.getenv('SIGN_PASSWORD')
    if username and password:
        hao = HaoSign(username, password)
        sign = False
        if hao.login():
            sign = hao.sign()
        send(title="hao签到", content=f"签到结果：{sign}")
    else:
        print("请设置账号")
