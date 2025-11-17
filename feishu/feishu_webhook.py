import json

import requests


def send_feishu_message(message):
    # webhook URL
    # webhook_url_v1 = "https://open.feishu.cn/open-apis/bot/v2/hook/44f3fbf1-60ad-4664-9fac-b99670c28117"
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/3f1cd2cb-09ea-497c-bb9a-4a193c035648"

    # 构建消息内容
    data = {
        "msg_type": "text",
        "content": {
            "text": f"{message}"
        }
    }

    # 发送 POST 请求
    headers = {'Content-Type': 'application/json'}
    # response = requests.post(webhook_url_v1, headers=headers, data=json.dumps(data))
    response = requests.post(webhook_url, headers=headers, data=json.dumps(data))

    # 打印响应结果
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text}")

# # # 执行发送消息
# if __name__ == "__main__":
#     file_name = "asdadasd"
#     send_feishu_message(f"文件={file_name}执行成功")
