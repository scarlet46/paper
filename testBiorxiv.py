def debug_redirects(url):
    import requests
    import logging

    # 设置详细日志
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("urllib3")
    logger.setLevel(logging.DEBUG)

    try:
        response = requests.get(url, allow_redirects=True)
        print(f"Final URL: {response.url}")
        print(f"Status code: {response.status_code}")
        print(f"Redirect history: {[r.url for r in response.history]}")
        print(f"Response headers: {dict(response.headers)}")
        return response.url
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    url = 'https://www.biorxiv.org/cgi/reprint/2023.11.27.568912v2??collection'
    print(debug_redirects(url))