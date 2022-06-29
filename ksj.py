import os

from notify import send
from sign.ksj import KsjSign

if __name__ == "__main__":
    username = os.getenv('SIGN_USERNAME')
    password = os.getenv('SIGN_PASSWORD')
    if username and password:
        ksj = KsjSign(username, password)
        if ksj.login():
            send(title="ksj签到", content=f"签到结果：{ksj.sign()}")
    else:
        print("请设置账号")
