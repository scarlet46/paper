import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置重试策略
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)

# 添加请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}

# 发送请求并在请求间添加延时
try:
    response = session.get('https://www.biorxiv.org/content/10.1101/2023.11.27.568912v2', headers=headers)
    print(f"Status code: {response.status_code}")
    print(f"Status code: {response.url}")
    time.sleep(2)  # 等待2秒再发送下一个请求
except Exception as e:
    print(f"Error: {e}")
