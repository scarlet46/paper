import json
import os

import lark_oapi as lark
from lark_oapi.api.drive.v1 import *


def file_upload(file_name, file_path):
    # 创建client
    client = lark.Client.builder() \
        .app_id("cli_a7fd8b0155bad00e") \
        .app_secret("SS0tzsmOWEIh4K12kRgRWerBCboX0Nys") \
        .log_level(lark.LogLevel.DEBUG) \
        .build()

    # 获取文件实际大小
    file_size = int(os.path.getsize(file_path))

    # 构造请求对象
    file = open(file_path, "rb")
    request: UploadAllFileRequest = UploadAllFileRequest.builder() \
        .request_body(UploadAllFileRequestBody.builder()
                      .file_name(file_name)
                      .parent_type("explorer")
                      .parent_node("NJEtfX33llsCttdETMCcbjWUnHf")
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
