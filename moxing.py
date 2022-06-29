import os

from notify import send
from sign.moxing import MoxingSign

if __name__ == "__main__":
    username = os.getenv('SIGN_USERNAME')
    password = os.getenv('SIGN_PASSWORD')
    if username and password:
        s = MoxingSign(username, password)
        sign = False
        if s.login():
            sign = s.sign()
        send(title="hao签到", content=f"签到结果：{sign}")
    else:
        print("请设置账号")
