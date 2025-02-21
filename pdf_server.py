from io import BytesIO

import fitz
from PIL import Image as PILImage

from ocr.ocr_server import download_file, image_to_base64, ocr, download_image
from ocr.oss import upload_to_oss_img


def process_pdf(url: str, num_pages: int = 10000) -> str:
    pdf_content = download_file(url)
    document = fitz.open(stream=pdf_content, filetype="pdf")
    full_text = []

    # 确保不超过文档的总页数
    num_pages = min(num_pages, len(document))

    for page_num in range(num_pages):
        # if len("".join(full_text)) >= 30000:
        #     break  # 如果已达到字符限制，停止处理

        page = document.load_page(page_num)
        text = page.get_text("text")

        # 检查页面是否包含图片
        images = page.get_images(full=True)

        if text.strip() and not images:
            # 如果有文本且没有图片
            full_text.append(text)
        elif images:
            # 如果有图片，进行 OCR 处理
            # if len("".join(full_text)) < 30000:  # 再次检查字符长度
            # 将页面转换为pixmap
            pix = page.get_pixmap()
            # 将pixmap转换为BytesIO对象
            img_bytes = BytesIO(pix.tobytes())
            # 使用PIL打开图像
            img = PILImage.open(img_bytes)
            # 将图像转换为Base64
            base64_image = image_to_base64(img)
            # OCR解析文本
            ocr_text = ocr(base64_image)
            full_text.append(ocr_text)

    # 返回拼接后的文本，确保不超过30000字符
    # return "".join(full_text)[:30000]
    return "".join(full_text)


def process_pdf_local(file_path: str, num_pages: int = 10000) -> str:
    """
    处理本地PDF文件

    Args:
        file_path: PDF文件的本地路径
        num_pages: 要处理的最大页数

    Returns:
        str: 提取的文本内容
    """
    try:
        # 直接打开本地PDF文件
        document = fitz.open(file_path)
        full_text = []

        # 确保不超过文档的总页数
        num_pages = min(num_pages, len(document))

        for page_num in range(num_pages):
            page = document.load_page(page_num)
            text = page.get_text("text")

            # 检查页面是否包含图片
            images = page.get_images(full=True)

            if text.strip() and not images:
                # 如果有文本且没有图片
                full_text.append(text)
            elif images:
                # 如果有图片，进行 OCR 处理
                # 将页面转换为pixmap
                pix = page.get_pixmap()
                # 将pixmap转换为BytesIO对象
                img_bytes = BytesIO(pix.tobytes())
                # 使用PIL打开图像
                img = PILImage.open(img_bytes)
                # 将图像转换为Base64
                base64_image = image_to_base64(img)
                # OCR解析文本
                ocr_text = ocr(base64_image)
                full_text.append(ocr_text)

        document.close()  # 记得关闭文档
        return "".join(full_text)

    except Exception as e:
        print(f"处理PDF文件 {file_path} 时发生错误: {str(e)}")
        return ""


class PdfProcessingResult:
    def __init__(self, num_pages: int, urls):
        self.num_pages = num_pages
        self.urls = urls

    def to_dict(self):
        return {
            'num_pages': self.num_pages,
            'urls': self.urls
        }


def process_get_pdf_others(url: str) -> PdfProcessingResult:
    try:
        pdf_content = download_file(url)
        document = fitz.open(stream=pdf_content, filetype="pdf")

        # 确保不超过文档的总页数
        num_pages = len(document)
        image_urls = []
        # 将第一页上传OSS 生成新的图片地址
        if num_pages == 1:
            page = document[0]
            # 提取页面中的所有图片
            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):
                xref = img[0]  # 图片的xref
                base_image = document.extract_image(xref)  # 提取图片
                image_data = base_image["image"]  # 图片数据
                image_name = f'extracted_page_0_img_{img_index + 1}.png'

                # 上传到OSS并获取地址
                image_url = upload_to_oss_img(image_data, image_name)
                image_urls.append(image_url)
                print(f"上传成功，图片地址: {image_url}")

        return PdfProcessingResult(num_pages, image_urls)
    except Exception as e:
        return PdfProcessingResult(0, [])


def process_img(url: str) -> str:
    full_text = []
    img_bytes = download_image(url)
    # 将图像转换为Base64
    base64_image = image_to_base64(img_bytes)
    # OCR解析文本
    ocr_text = ocr(base64_image)
    full_text.append(ocr_text)
    return "\n".join(full_text)

# if __name__ == '__main__':
#     print(process_pdf(
#         'https://graph-rag.oss-cn-beijing.aliyuncs.com/%E8%AE%BA%E6%96%87%E7%9F%A5%E8%AF%86%E5%BA%93/CHNB00854024%20%281%29.pdf',
#         1))
