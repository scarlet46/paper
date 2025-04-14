import json
import logging
import os
from datetime import datetime

import lark_oapi as lark
from lark_oapi.api.drive.v1 import *

# 生产
APP_ID = 'cli_a7fd8b0155bad00e'
APP_SECRET = 'SS0tzsmOWEIh4K12kRgRWerBCboX0Nys'
FOLDER_TOEKN = 'SUChfJH4dly4p6d7o7Mc3gB9nlc'


# 测试
# APP_ID = 'cli_a67f394dc6f85013'
# APP_SECRET = '8qXvbS9s2pvOmcqnHG6wdduTkNpR1Vi4'
# FOLDER_TOEKN = 'O0sfflWz3lySj0dDTugcpif2nDA'


def create_file(subject, email_date):
    # 创建client
    client = lark.Client.builder() \
        .app_id(APP_ID) \
        .app_secret(APP_SECRET) \
        .log_level(lark.LogLevel.DEBUG) \
        .build()

    # 构造请求对象
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    output_file = f"{email_date}_{subject}"
    request: CreateFolderFileRequest = CreateFolderFileRequest.builder() \
        .request_body(CreateFolderFileRequestBody.builder()
                      .name(output_file)
                      .folder_token(FOLDER_TOEKN)
                      .build()) \
        .build()

    # 发起请求
    response: CreateFolderFileResponse = client.drive.v1.file.create_folder(request)

    # 处理失败返回
    if not response.success():
        logging.error(
            f"client.drive.v1.file.create_folder failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
        return None

    # 处理业务结果
    return response.data.token


def file_upload(file_token, file_path):
    # 创建client
    client = lark.Client.builder() \
        .app_id(APP_ID) \
        .app_secret(APP_SECRET) \
        .log_level(lark.LogLevel.DEBUG) \
        .build()

    # 获取文件实际大小
    file_size = int(os.path.getsize(file_path))

    # 构造请求对象
    file = open(file_path, "rb")
    request: UploadAllFileRequest = UploadAllFileRequest.builder() \
        .request_body(UploadAllFileRequestBody.builder()
                      .file_name(file_path)
                      .parent_type("explorer")
                      .parent_node(file_token)
                      .size(file_size)
                      .file(file)
                      .build()) \
        .build()

    try:
        # 发起请求
        response: UploadAllFileResponse = client.drive.v1.file.upload_all(request)

        # 处理失败返回
        if not response.success():
            lark.logger.error(
                f"client.drive.v1.file.upload_all failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}")
            return

        # 处理业务结果
        lark.logger.info(lark.JSON.marshal(response.data, indent=4))

    finally:
        # 确保文件被关闭
        file.close()


# if __name__ == "__main__":
#     file_path = "../20250220_生物信息学算法.md"
#     file_upload(file_path)
