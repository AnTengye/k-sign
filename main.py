import os

from sign.hao import HaoSign
from sign.ksj import KsjSign

if __name__ == "__main__":
    username = os.getenv('SIGN_USERNAME')
    password = os.getenv('SIGN_PASSWORD')
    if username and password:
        ksj = KsjSign(username, password)
        if ksj.login():
            ksj.sign()
        hao = HaoSign(username, password)
        if hao.login():
            hao.sign()
    else:
        print("请设置账号")
