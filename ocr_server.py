import base64
import time
from io import BytesIO
from urllib.parse import unquote

import lark_oapi as lark
from PIL import Image as PILImage
from lark_oapi.api.optical_char_recognition.v1 import *

AK = 'cli_a7fd8b0155bad00e'
SK = 'SS0tzsmOWEIh4K12kRgRWerBCboX0Nys'


# 下载文件
def download_file(url: str) -> bytes:
    """
    下载文件，支持bioRxiv等学术网站的反爬虫机制

    Args:
        url (str): 文件下载URL

    Returns:
        bytes: 文件内容，失败时返回空字节
    """
    try:
        # 清理URL编码问题
        clean_url = unquote(url)
        print(f"📥 正在下载: {clean_url}")

        # 设置请求头，模拟真实浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'max-age=0'
        }

        # 创建会话
        session = requests.Session()
        session.headers.update(headers)

        # 先访问主页建立会话（对bioRxiv很重要）
        base_url = 'https://www.biorxiv.org/'
        try:
            session.get(base_url, timeout=10)
            time.sleep(1)  # 短暂等待
        except:
            pass  # 如果主页访问失败，继续尝试直接下载

        # 下载文件
        response = session.get(clean_url, timeout=30)
        response.raise_for_status()

        # 检查响应内容类型
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' in content_type or len(response.content) > 1000:
            print(f"✅ 下载成功，文件大小: {len(response.content)} 字节")
            return response.content
        else:
            print(f"⚠️ 可能不是PDF文件，内容类型: {content_type}")
            return response.content

    except requests.RequestException as e:
        print(f"❌ 下载文件失败: {e}")
        return b''
    except Exception as e:
        print(f"❌ 未知错误: {e}")
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
