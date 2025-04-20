import requests
import os
import json
from urllib.parse import urlparse, unquote


class FeishuFileDownloader:
    """飞书文件下载器"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self.access_token = self._get_tenant_access_token()

    def _get_tenant_access_token(self) -> str:
        """获取tenant_access_token"""
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        response = requests.post(url, headers=headers, data=json.dumps(data))
        response_json = response.json()

        if response_json.get("code") == 0:
            return response_json.get("tenant_access_token")
        else:
            raise Exception(f"获取tenant_access_token失败: {response_json}")

    def extract_file_token(self, file_url: str) -> str:
        """从URL中提取文件token"""
        # 解析URL路径
        path = urlparse(file_url).path
        # 获取最后一个部分作为token
        file_token = path.split('/')[-1]
        return file_token

    def download_file(self, file_url: str, save_dir: str = "./downloads") -> str:
        """
        下载飞书文件

        Args:
            file_url: 文件URL，如https://cre-life.feishu.cn/file/LKlLbuxvMojTQhxXDoXcvDiTneh
            save_dir: 保存目录

        Returns:
            保存的文件路径
        """
        # 从URL中提取文件token
        file_token = self.extract_file_token(file_url)
        print(f"文件token: {file_token}")

        # 1. 尝试获取文件元数据以获取文件名
        meta_url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        # 尝试从元数据获取文件名
        file_name = None
        file_type = None
        try:
            print(f"获取文件元数据...")
            meta_response = requests.get(meta_url, headers=headers)

            if meta_response.status_code == 200:
                meta_json = meta_response.json()
                if meta_json.get("code") == 0:
                    file_name = meta_json.get("data", {}).get("name")
                    file_type = meta_json.get("data", {}).get("type")
                    print(f"获取到文件名: {file_name}")
                    print(f"文件类型: {file_type}")
        except Exception as e:
            print(f"获取文件元数据失败: {str(e)}")

        # 如果无法获取文件名，使用默认名称
        if not file_name:
            print(f"无法获取文件名，使用默认名称")
            file_name = f"file_{file_token}.pdf"  # 默认添加PDF后缀
        else:
            # 检查文件名是否已有后缀
            if not file_name.lower().endswith('.pdf') and (file_type == 'pdf' or 'pdf' in file_url.lower()):
                file_name = f"{file_name}.pdf"
                print(f"添加PDF后缀，新文件名: {file_name}")

        # 2. 直接下载文件
        down_url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}/download"
        print(f"开始下载文件...")

        # 使用 stream=True 进行流式下载
        file_response = requests.get(down_url, headers=headers, stream=True)

        # 检查响应状态码
        if file_response.status_code != 200:
            print(f"下载文件失败，状态码: {file_response.status_code}")
            try:
                print(f"错误响应: {file_response.text[:200]}...")
            except:
                pass
            raise Exception(f"下载文件失败，状态码: {file_response.status_code}")

        # 检查响应内容类型
        content_type = file_response.headers.get('Content-Type', '')
        print(f"文件内容类型: {content_type}")

        # 根据内容类型添加适当的后缀
        if 'application/pdf' in content_type.lower() and not file_name.lower().endswith('.pdf'):
            file_name = f"{file_name}.pdf"
            print(f"根据内容类型添加PDF后缀，新文件名: {file_name}")
        elif 'json' in content_type.lower():
            # 如果返回的是JSON，可能是错误信息
            try:
                error_json = file_response.json()
                print(f"API返回错误: {error_json}")
                raise Exception(f"下载文件失败，API返回错误: {error_json.get('msg', '未知错误')}")
            except json.JSONDecodeError:
                # 不是有效的JSON，继续当作二进制处理
                pass

        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)

        # 保存文件
        save_path = os.path.join(save_dir, file_name)

        # 获取文件大小（如果响应头中包含）
        total_size = int(file_response.headers.get('content-length', 0))
        if total_size:
            print(f"文件大小: {total_size / (1024 * 1024):.2f} MB")

        # 写入文件
        downloaded_size = 0
        with open(save_path, 'wb') as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                if chunk:  # 过滤掉保持连接活跃的空字节
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    # 打印下载进度
                    if total_size > 0 and downloaded_size % (1024 * 1024) < 8192:  # 每下载约1MB打印一次进度
                        progress = (downloaded_size / total_size) * 100
                        print(f"下载进度: {progress:.1f}%")

        print(f"文件已成功下载并保存到: {save_path}")
        return save_path


# def main():
#     # 替换为你的应用凭证
#     APP_ID = 'cli_a7fd8b0155bad00e'
#     APP_SECRET = 'SS0tzsmOWEIh4K12kRgRWerBCboX0Nys'
#
#     # 文件URL
#     FILE_URL = 'https://cre-life.feishu.cn/file/LKlLbuxvMojTQhxXDoXcvDiTneh'
#
#     # 保存目录
#     SAVE_DIR = "./downloaded_files"
#
#     downloader = FeishuFileDownloader(APP_ID, APP_SECRET)
#
#     try:
#         # 下载文件
#         saved_path = downloader.download_file(FILE_URL, SAVE_DIR)
#         print(f"文件已成功下载到: {saved_path}")
#
#     except Exception as e:
#         print(f"下载文件失败: {e}")
#
#
# if __name__ == "__main__":
#     main()
