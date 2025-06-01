import io
import numpy as np
import cv2
import ddddocr
from PIL import Image



def split_captcha_image(response_content, num_splits=3) -> list:
    """
    将验证码图片分割为指定数量的图片（默认3张）
    """
    # 下载图片
    try:
        img_data = io.BytesIO(response_content)
        img = Image.open(img_data)

        # 确保图片格式为WebP并转换为RGB（如果需要）
        if img.format == 'WEBP':
            img = img.convert('RGB')
    except Exception as e:
        print(f"无法下载或打开图片: {e}")
        return []

    # 获取图片尺寸
    width, height = img.size

    # 计算每张子图的高度（竖向平均分割）
    split_height = height // num_splits
    background = list()

    # 竖向分割图片
    for i in range(num_splits):
        # 计算裁剪区域（左上右下）
        top = i * split_height
        bottom = (i + 1) * split_height if i < num_splits - 1 else height
        box = (0, top, width, bottom)
        # 裁剪图片
        split_img = img.crop(box)
        background.append(split_img)
        # 保存分割后的图片
        # output_path = os.path.join("./", f'split_{i + 1}.png')
        # split_img.save(output_path)
        # print(f"已保存分割图片: {output_path}")
    return background

def slide(target_pil_image: Image.Image, background_bytes: bytes):
    """
    スライドパズルのピース（ターゲット画像）と背景画像を比較します。
    ターゲット画像はPIL Imageオブジェクトとして、背景画像はバイト列として受け取ります。
    """
    det = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)

    # PIL Imageオブジェクト (RGB) を OpenCV の BGR 形式の numpy 配列に変換
    try:
        # PIL ImageがRGBAの場合、RGBに変換してから処理する
        if target_pil_image.mode == 'RGBA':
            target_pil_image = target_pil_image.convert('RGB')
        elif target_pil_image.mode != 'RGB':  # RGB以外(L, Pなど)の場合もRGBに変換
            target_pil_image = target_pil_image.convert('RGB')

        t_cv_bgr = cv2.cvtColor(np.array(target_pil_image), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"Error converting PIL Image to OpenCV format: {e}")
        return None

    if t_cv_bgr is None:
        print("Error: Could not convert target PIL Image to OpenCV format (resulted in None).")
        return None
    # t_cv_bgr = cv2.imread("split_22.png")

    tmp = cv2.cvtColor(t_cv_bgr, cv2.COLOR_BGR2GRAY)

    # --- Key change for black residue ---
    transparency_threshold = 10
    _, alpha = cv2.threshold(tmp, transparency_threshold, 255, cv2.THRESH_BINARY)

    b, g, r = cv2.split(t_cv_bgr)

    rgba = [b, g, r, alpha]
    dst = cv2.merge(rgba)
    # 查看透明化处理
    # cv2.imwrite("test_transparent_from_pil.png", dst)

    # --- Key change for target_bytes ---
    is_success, buffer = cv2.imencode(".png", dst)
    if not is_success:
        print("Error: Could not encode image to PNG format.")
        return None
    target_bytes_generated = buffer.tobytes()

    res = None
    try:
        res = det.slide_match(target_bytes_generated, background_bytes)
    except Exception as e:
        print(f"Error during ddddocr slide_match: {e}")
    return res


def crop_by_tile_width(img: Image.Image):
    """
    将一个包含长方形滑块的图片，按照第一个滑块的宽度进行裁剪。
    """
    try:
        target_pil_image = img.convert('RGB')

        t_cv_bgr = cv2.cvtColor(np.array(target_pil_image), cv2.COLOR_RGB2BGR)
        edges = cv2.Canny(t_cv_bgr, 100, 200)

        # 找到所有边缘点的坐标
        y_coords, x_coords = np.where(edges > 0)

        if len(x_coords) > 0:
            # min_x, min_y = np.min(x_coords), np.min(y_coords)
            # max_x, max_y = np.max(x_coords), np.max(y_coords)
            tile_width = np.max(x_coords) + 2
        else:
            tile_width = 50
        w, h = img.size
        # 定义裁剪区域
        left = 0
        upper = 0
        right = tile_width
        lower = h

        # 裁剪图片
        cropped_img = img.crop((left, upper, right, lower))
        return cropped_img
    except Exception as e:
        print(f"发生错误：{e}")


def get_slide_width(image_content_bytes) -> int:
    pil_images = split_captcha_image(image_content_bytes, num_splits=3)
    if pil_images and len(pil_images) >= 2:
        target_pil_for_slide = pil_images[1]  # 滑块
        background_pil_for_slide = pil_images[0]  # 带缺口背景图
        background_bytes_io = io.BytesIO()
        try:
            if background_pil_for_slide.mode != 'RGB':
                background_pil_for_slide = background_pil_for_slide.convert('RGB')
            background_pil_for_slide.save(background_bytes_io, format='PNG')
            background_bytes_for_slide_func = background_bytes_io.getvalue()
            # 识别
            result = slide(crop_by_tile_width(target_pil_for_slide), background_bytes_for_slide_func)

            if result and len(result["target"]) == 4:
                return result["target"][0]
            else:
                print("⚠️ Slide function did not return a result or an error occurred.")

        except Exception as e:
            print(f"Error processing images for slide function: {e}")
    else:
        if not pil_images:
            print("❌ Image splitting failed, no images returned.")
        else:
            print(
                f"❌ Image splitting returned only {len(pil_images)} image(s). Need at least 2 for target and background.")

if __name__ == "__main__":
    # --- 準備: ダミーの画像コンテンツを作成 ---
    # 実際には、これはWebリクエストなどから得られるバイトデータです。
    # 例: response = requests.get(captcha_image_url)
    #     image_content_bytes = response.content
    try:
        # テスト用にローカルの画像ファイルを読むか、なければダミー画像を生成
        # 例として 'sample_captcha.webp' というファイルがあることを期待
        captcha_file_path = 'tncode.webp'  # 縦長の画像が良いでしょう
        with open(captcha_file_path, "rb") as f:
            image_content_bytes = f.read()
        print(f"Loaded image content (size: {len(image_content_bytes)} bytes).")

    except Exception as e:
        print(f"Error preparing image content: {e}")
        image_content_bytes = None
    # --- 準備ここまで ---

    if image_content_bytes:
        get_slide_width(image_content_bytes)
    else:
        print("❌ No image content to process.")