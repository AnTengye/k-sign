import base64
import traceback

import ddddocr
import requests
import time
import json
from PIL import Image
from io import BytesIO


def recogition(yzm_data):
    """
    验证码识别
    :param yzm_data:
    :return:
    """
    base64_str = base64.b64encode(yzm_data)
    url = "http://127.0.0.1:15831/ai/ocr"
    payload = json.dumps({
        "image": base64_str.decode("utf-8")
    })
    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    json_obj = json.loads(response.text)
    yzm_text = json_obj.get("data", "")
    return yzm_text


def recogition2(yzm_data, char="", onnx="", debug=False):
    """
    验证码识别
    :param debug:
    :param onnx: 自定义训练模型
    :param char: 自定义字符集
    :param yzm_data:
    :return:
    """
    ocr = ddddocr.DdddOcr(show_ad=False, import_onnx_path=onnx,
                          charsets_path=char)
    try:
        res = ocr.classification(yzm_data)
        if debug:
            base64_str = base64.b64encode(yzm_data)
            print(base64_str.decode("utf-8"))
            with open(f"debug/{res}.jpg", "wb") as fp:
                fp.write(yzm_data)
    except Exception as e:
        traceback.print_exc()
        return ""
    return res


def gif_to_png(length, image) -> (int, bytes):
    """
    gif抽帧
    :param length:
    :param image:
    :return:
    """
    max_frame = length
    try:
        max_dura = 0
        max_img = b''
        for i in range(1, length):
            try:
                image.seek(i)
            except Exception as e:
                print(f"该图片最多:{i}")
                max_frame = i
                break
            dura = image.info.get("duration", 0)
            if dura > max_dura:
                print(f"找到新延迟：{dura}")
                max_dura = dura
                stream = BytesIO()
                image.save(stream, 'PNG')
                max_img = stream.getvalue()
        return max_frame, max_img
    except Exception as e:
        print(e)
    return max_frame, None


def handle_yzm(img_data, char="", onnx="", t="gif", debug=False) -> str:
    """
    处理验证码
    :return:
    """
    # 抽帧长度
    length = 50
    print("验证码识别中...")
    result = ""
    start = time.time()
    if img_data and t == "gif":
        data = BytesIO(img_data)
        try:
            image = Image.open(data)
        except Exception as e:
            traceback.print_exc()
            return ""
        _, png_info = gif_to_png(length, image)
        if png_info:
            result = recogition2(png_info, char, onnx, debug)
    elif t == "img":
        result = recogition2(img_data, char, onnx, debug)
    end = time.time()
    print(f"验证码结果：{result}-花费时间：{end - start}")
    return result


if __name__ == '__main__':
    data = b''
    gif = base64.b64decode(data)
    # 识别图片个数
    handle_yzm(gif, t="img")
