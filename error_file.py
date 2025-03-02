import logging
import os
import re
from datetime import datetime

from feishu.feishu import create_file, file_upload
from feishu.feishu_webhook import send_feishu_message
from utils import process_paper, sanitize_file_name


def extract_urls_from_file(file_path):
    """
    从本地文件中读取内容并提取所有URL。

    :param file_path: 文件路径
    :return: 提取的URL列表
    """
    urls = []
    try:
        # 1. 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        # 2. 使用正则表达式提取URL
        url_pattern = re.compile(
            r'(https?://[^\s]+)'  # 匹配以 http:// 或 https:// 开头的URL
        )
        for line in lines:
            # 在每一行中查找URL
            matches = url_pattern.findall(line)
            if matches:
                urls.extend(matches)

        return urls
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
        return []
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return []


# 示例用法
if __name__ == "__main__":
    file_path = "error_file.txt"  # 本地文件路径
    urls = extract_urls_from_file(file_path)
    if len(urls) == 0:
        logging.error("文件地址获取地址为空!")
        exit()
    now = datetime.now()
    file_token = create_file("异常文件补充", now)
    send_feishu_message(
        f"开始执行异常补充,总共{len(urls)}条数据,获取到文件夹token:{file_token}")
    if urls:
        print("提取的URL如下：")
        for url in urls:
            print(url)
            try:
                result = process_paper(url)
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
            f"开始执行异常补充,总共{len(urls)}条数据,获取到文件夹token:{file_token}")
    else:
        print("未提取到任何URL。")
        send_feishu_message(
            f"开始执行异常补充,总共{len(urls)}条数据,未提取到任何URL")
