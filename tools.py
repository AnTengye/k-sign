import re

# 表单元素-js
FORM_HASH = re.compile(r'formhash:\'([a-zA-Z0-9]+)\'')
DISCODE = re.compile(r"discode:.*?\'(\d+)\'")

# 图片验证码所需元素
# misc.php?mod=seccode&update=78244&idhash=SLk7J
UPDATE = re.compile(r'update=(\d+)')
IDHASH = re.compile(r'idhash=([a-zA-Z0-9]+)')


def re_handler(reobj: re.Pattern, text: str) -> (str, str):
    result = reobj.search(text)
    if result is not None:
        return result.group(1)
    return ""
