import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

import requests

from feishu.down_load import FeishuFileDownloader
from feishu.feishu import create_file, file_upload
from feishu.feishu_webhook import send_feishu_message
from utils import sanitize_file_name, process_paper, process_paper_local

APP_ID = 'cli_a7fd8b0155bad00e'
APP_SECRET = 'SS0tzsmOWEIh4K12kRgRWerBCboX0Nys'
SAVE_DIR = "./downloaded_files"

class FeishuDriveClient:
    """飞书云文档API客户端"""

    def __init__(self, app_id: str, app_secret: str):
        """
        初始化飞书云文档客户端

        Args:
            app_id: 飞书应用的App ID
            app_secret: 飞书应用的App Secret
        """
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

    def list_files(self, folder_token: str, page_size: int = 100) -> List[Dict[str, Any]]:
        """
        获取指定文件夹下的所有文件

        Args:
            folder_token: 文件夹的token
            page_size: 每页返回的文件数量

        Returns:
            文件列表
        """
        all_files = []
        page_token = None

        while True:
            url = f"{self.base_url}/drive/v1/files"
            params = {
                "folder_token": folder_token,
                "page_size": page_size
            }

            if page_token:
                params["page_token"] = page_token

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            response = requests.get(url, headers=headers, params=params)
            response_json = response.json()

            if response_json.get("code") != 0:
                raise Exception(f"获取文件列表失败: {response_json}")

            files = response_json.get("data", {}).get("files", [])
            all_files.extend(files)

            page_token = response_json.get("data", {}).get("page_token")
            if not page_token:
                break

        return all_files

    def get_all_files_recursive(self, folder_token: str) -> List[Dict[str, Any]]:
        """
        递归获取文件夹下所有文件（包括子文件夹中的文件）

        Args:
            folder_token: 文件夹的token

        Returns:
            所有文件的列表
        """
        all_files = []
        files = self.list_files(folder_token)

        for file in files:
            if file.get("type") == "folder":
                # 如果是文件夹，递归获取其中的文件
                subfolder_files = self.get_all_files_recursive(file.get("token"))
                all_files.extend(subfolder_files)
            else:
                # 如果是文件，直接添加到结果列表
                all_files.append(file.get("url"))

        return all_files


def process(urls):
    if len(urls) == 0:
        logging.error("文件地址获取地址为空!")
        exit()
    now = datetime.now()
    file_token = create_file("飞书文件夹读取", now)
    send_feishu_message(
        f"开始执行飞书文件夹补充,总共{len(urls)}条数据,获取到文件夹token:{file_token}")
    if urls:
        print("提取的URL如下：")
        for url in urls:
            print(url)
            # 下载文件到本地
            downloader = FeishuFileDownloader(APP_ID, APP_SECRET)
            saved_path = downloader.download_file(url, SAVE_DIR)
            try:
                result = process_paper_local(saved_path)
            except Exception as e:
                send_feishu_message(
                    f":异常:解析URL解析失败: {url}: {e}")
                logging.error(f"Error processing URL: {url}: {e}")
                continue
            if result:
                try:
                    output_file, formatted_output = result
                    file_name = output_file + "_" + url + ".md"
                    file_name = sanitize_file_name(file_name)
                    # 判断文件是否存在，如果不存在创建文件增加metadata
                    if not os.path.exists(file_name):
                        with open(file_name, 'w', encoding='utf-8') as f:
                            f.write(f"\n")
                    with open(file_name, 'a', encoding='utf-8') as f:
                        f.write(f"{formatted_output}\n\n")
                    logging.info(f"Processed and wrote result for URL: {url}")
                    # 写入飞书
                    if result:
                        file_upload(file_token, file_name)
                        # 删除本地文件
                        os.remove(file_name)
                except Exception as e:
                    send_feishu_message(
                        f":异常:处理文件结果={result}上传飞书异常: {url}: {e}")
                    logging.error(f"Error uploading URL: {url}: {e}")

            else:
                send_feishu_message(
                    f":Failed to process 执行异常,获取PDF内容失败: {url}")
                logging.warning(f"Failed to process URL: {url}")
        send_feishu_message(
            f"开始执行飞书文件夹,总共{len(urls)}条数据,获取到文件夹token:{file_token}")
    else:
        print("未提取到任何URL。")
        send_feishu_message(
            f"开始执行飞书文件夹,总共{len(urls)}条数据,未提取到任何URL")


def main():
    # 替换为你要获取的文件夹token
    FOLDER_TOKEN = "SUChfJH4dly4p6d7o7Mc3gB9nlc"

    client = FeishuDriveClient(APP_ID, APP_SECRET)

    try:
        # 获取所有文件
        all_files = client.get_all_files_recursive(FOLDER_TOKEN)

        print(f"共找到 {len(all_files)} 个文件:")
        process(all_files)

    except Exception as e:
        print(f"获取文件失败: {e}")


if __name__ == "__main__":
    main()
