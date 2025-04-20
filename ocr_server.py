import base64
from io import BytesIO

import lark_oapi as lark
import requests
from PIL import Image as PILImage
from lark_oapi.api.optical_char_recognition.v1 import *

AK = 'cli_a7fd8b0155bad00e'
SK = 'SS0tzsmOWEIh4K12kRgRWerBCboX0Nys'


# 下载文件
def download_file(url: str) -> bytes:
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"下载文件失败: {e}")
        return b''


import requests


def download_feishu_file(access_token, file_token, save_path):
    """下载飞书普通文件"""
    # 1. 获取下载链接
    url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}/download"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    download_info = response.json()

    if download_info.get("code") != 0:
        raise Exception(f"获取下载链接失败: {download_info}")

    download_url = download_info.get("data", {}).get("download_url")

    if not download_url:
        raise Exception("未找到下载链接")

    # 2. 下载文件
    file_response = requests.get(download_url)

    with open(save_path, 'wb') as f:
        f.write(file_response.content)

    return save_path


# 下载图像
def download_image(url: str) -> PILImage:
    response = requests.get(url)
    response.raise_for_status()  # 检查请求是否成功
    img_bytes = BytesIO(response.content)
    return PILImage.open(img_bytes)


# 图片转换base64流
def image_to_base64(image_pdf: PILImage.Image) -> str:
    buffered = BytesIO()
    image_pdf.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


# 清洗结果
def clean_text(text_list: list) -> str:
    cleaned = []
    for page_text in text_list:
        lines = page_text.split('\n')
        cleaned_page = [line for line in lines if not is_page_number(line)]
        cleaned.append("\n".join(cleaned_page))
    return "\n".join(cleaned)


# 判断是否包含页码
def is_page_number(line: str) -> bool:
    return line.isdigit() or "Page" in line or "页" in line


# OCR解析
def ocr(base64_img: str) -> str:
    try:
        client = lark.Client.builder() \
            .app_id(AK) \
            .app_secret(SK) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()
        request = BasicRecognizeImageRequest.builder() \
            .request_body(BasicRecognizeImageRequestBody.builder()
                          .image(base64_img)
                          .build()) \
            .build()
        response = client.optical_char_recognition.v1.image.basic_recognize(request)
        if not response.success():
            lark.logger.error(
                f"client.optical_char_recognition.v1.image.basic_recognize failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}")
            return ""
        merged_text = "\n".join(response.data.text_list)
        formatted_json = lark.JSON.marshal(merged_text, indent=4)
        return formatted_json
    except Exception as e:
        print(f"OCR解析失败: {e}")
        return ""
