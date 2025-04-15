import requests

# 使用与成功的 curl 请求完全相同的头信息
headers = {
    'User-Agent': 'curl/7.68.0',  # 使用您系统上 curl 的实际 User-Agent
    'Accept': '*/*',  # curl 默认的 Accept 头
    # 添加 curl 请求中的其他头信息
}

response = requests.get('https://www.biorxiv.org/content/10.1101/2023.11.27.568912v2', headers=headers)
print(f"Status code: {response.status_code}")
print(f"Status code: {response.url}")
