def debug_redirects(url):
    import requests
    import logging
    from requests.packages.urllib3.util.retry import Retry
    from requests.adapters import HTTPAdapter

    # 设置详细日志
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("urllib3")
    logger.setLevel(logging.DEBUG)

    # 创建会话对象
    session = requests.Session()

    # 配置重试策略
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"]
    )

    # 添加重试适配器
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))

    # 更完整的请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.biorxiv.org/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'DNT': '1',  # Do Not Track
    }

    # 首先访问主页获取必要的 cookies
    try:
        session.get('https://www.biorxiv.org/', headers=headers)

        # 添加延迟，模拟人类行为
        import time
        time.sleep(2)

        # 然后访问目标 URL
        response = session.get(url, allow_redirects=True, headers=headers)
        print(f"Final URL: {response.url}")
        print(f"Status code: {response.status_code}")
        print(f"Redirect history: {[r.url for r in response.history]}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Cookies: {dict(session.cookies)}")
        return response.url
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    url = 'https://www.biorxiv.org/cgi/reprint/2023.11.27.568912v2??collection'
    print(debug_redirects(url))