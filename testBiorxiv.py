import requests
import re
import sys
import time
from urllib.parse import urlparse, parse_qs


def extract_paper_id_from_url(url):
    """从 bioRxiv URL 中提取论文 ID 和版本"""
    # 匹配多种可能的 URL 格式
    patterns = [
        r'biorxiv\.org/cgi/reprint/(\d+\.\d+\.\d+\.\d+)(v\d+)?',
        r'biorxiv\.org/content/10\.1101/(\d+\.\d+\.\d+\.\d+)(v\d+)?',
        r'10\.1101/(\d+\.\d+\.\d+\.\d+)(v\d+)?'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            paper_id = match.group(1)
            version = match.group(2)[1:] if match.group(2) else "1"
            return paper_id, version

    return None, None


def get_paper_info_from_api(paper_id):
    """使用 bioRxiv API 获取论文信息"""
    doi = f"10.1101/{paper_id}"

    # 尝试两种不同的 API 端点
    api_endpoints = [
        f"https://api.biorxiv.org/details/biorxiv/{doi}/na/json",  # 新的 API 端点
        f"https://api.biorxiv.org/lookup/doi/{doi}"  # 旧的 API 端点
    ]

    for url in api_endpoints:
        try:
            print(f"尝试 API 端点: {url}")
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # 检查不同的 API 响应格式
                if "collection" in data and len(data["collection"]) > 0:
                    return data["collection"][0]
                elif "messages" in data and data["messages"][0]["status"] == "ok" and len(data["collection"]) > 0:
                    return data["collection"][0]
                elif "results" in data and len(data["results"]) > 0:
                    return data["results"][0]
            else:
                print(f"API 请求失败: {response.status_code}")
        except Exception as e:
            print(f"API 请求错误: {str(e)}")

    return None


def get_paper_info_from_webpage(paper_id, version="1"):
    """从网页直接抓取论文信息"""
    url = f"https://www.biorxiv.org/content/10.1101/{paper_id}v{version}"

    try:
        print(f"尝试从网页获取信息: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9"
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            html = response.text

            # 使用正则表达式提取信息
            title_match = re.search(r'<meta name="DC.Title" content="([^"]+)"', html)
            authors_match = re.search(r'<meta name="DC.Creator" content="([^"]+)"', html)
            abstract_match = re.search(r'<meta name="DC.Description" content="([^"]+)"', html)

            paper_info = {}
            if title_match:
                paper_info["title"] = title_match.group(1)
            if authors_match:
                paper_info["authors"] = authors_match.group(1)
            if abstract_match:
                paper_info["abstract"] = abstract_match.group(1)

            paper_info["doi"] = f"10.1101/{paper_id}"
            paper_info["version"] = version
            paper_info["pdf_url"] = f"https://www.biorxiv.org/content/10.1101/{paper_id}v{version}.full.pdf"

            return paper_info
        else:
            print(f"网页请求失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"网页请求错误: {str(e)}")
        return None


def display_paper_info(paper):
    """显示论文信息"""
    if not paper:
        print("未能获取论文信息")
        return False

    print("\n=== 论文信息 ===")
    print(f"标题: {paper.get('title', 'N/A')}")
    print(f"作者: {paper.get('authors', 'N/A')}")
    print(f"DOI: {paper.get('doi', 'N/A')}")
    print(f"版本: {paper.get('version', 'N/A')}")

    if 'abstract' in paper:
        print(f"\n摘要: {paper['abstract']}")

    # 构建 PDF 链接
    paper_id = paper.get('doi', '').replace('10.1101/', '')
    version = paper.get('version', '1')
    pdf_url = paper.get('pdf_url', f'https://www.biorxiv.org/content/10.1101/{paper_id}v{version}.full.pdf')
    print(f"\nPDF链接: {pdf_url}")

    # 提供备选链接
    print("\n备选访问链接:")
    print(f"1. 直接链接: https://www.biorxiv.org/content/10.1101/{paper_id}v{version}")
    print(f"2. DOI链接: https://doi.org/10.1101/{paper_id}")
    print(
        f"3. 备用PDF: https://www.biorxiv.org/content/biorxiv/early/{paper_id.split('.')[0]}/{paper_id.split('.')[1]}/{paper_id.split('.')[2]}/{paper_id.split('.')[3]}/10.1101.{paper_id}.full.pdf")

    return True


def main(url):
    """主函数，接受 URL 作为输入参数"""
    print(f"正在处理 URL: {url}")

    # 从 URL 提取论文 ID 和版本
    paper_id, version = extract_paper_id_from_url(url)

    if not paper_id:
        print(f"无法从 URL 中提取论文 ID: {url}")
        print("请确保提供的是有效的 bioRxiv 论文链接")
        return False

    print(f"提取到论文 ID: {paper_id}, 版本: {version}")

    # 尝试方法 1: 使用 API 获取信息
    print("\n方法 1: 尝试使用 bioRxiv API 获取信息...")
    paper_info = get_paper_info_from_api(paper_id)

    # 如果 API 失败，尝试方法 2: 从网页抓取信息
    if not paper_info:
        print("\n方法 2: API 请求失败，尝试从网页直接抓取信息...")
        paper_info = get_paper_info_from_webpage(paper_id, version)

    # 显示获取到的信息
    return display_paper_info(paper_info)


if __name__ == "__main__":
    # 如果从命令行运行，获取第一个参数作为 URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        # 默认使用您提供的 URL
        url = "https://www.biorxiv.org/cgi/reprint/2023.11.27.568912v2??collection"

    success = main(url)
    print(f"\n处理{'成功' if success else '失败'}")
