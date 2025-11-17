#!/usr/bin/env python3
"""
基于成功测试代码的 bioRxiv Selenium 下载器
使用与 biorxiv_url_test.py 相同的配置来确保成功下载
"""

import os
import re
import time
import random
import logging
import glob
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BioRxivSeleniumDownloader:
    def __init__(self, download_dir=None):
        if download_dir is None:
            self.download_dir = os.path.abspath("./temp_biorxiv_downloads")
        else:
            self.download_dir = os.path.abspath(download_dir)

        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)
        self.driver = None
        self.cookie_string = None  # 添加 cookie_string 变量

    def parse_cookie_string(self, cookie_string, domain):
        """解析Cookie字符串为Selenium格式"""
        cookies = []
        for item in cookie_string.split(';'):
            if '=' in item:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "secure": False
                })
        return cookies

    def set_cookie_string(self, cookie_string):
        """设置 cookie 字符串"""
        self.cookie_string = cookie_string

    def setup_driver(self):
        """设置 Chrome WebDriver - 使用与测试代码相同的配置"""
        try:
            # 配置Chrome选项 - 完全复制成功的配置
            options = webdriver.ChromeOptions()

            # 添加无头模式配置
            options.add_argument("--headless=new")  # 新的无头模式（Chrome 112+推荐）
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")

            # 禁用自动化特征检测 - 增强版
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-blink-features=AutomationControlled")

            # 随机User-Agent，避免被识别为爬虫
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ]
            options.add_argument(f"user-agent={random.choice(user_agents)}")

            # PDF下载配置
            prefs = {
                "download.default_directory": self.download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "plugins.always_open_pdf_externally": True,
                "profile.default_content_setting_values.automatic_downloads": 1
            }
            options.add_experimental_option('prefs', prefs)

            # 自动下载和初始化WebDriver
            logging.info("正在初始化 ChromeDriver...")
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )

            # 进一步隐藏自动化特征
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })

            return True

        except Exception as e:
            logging.error(f"设置 WebDriver 失败: {e}")
            return False

    def close_driver(self):
        """关闭 WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def is_biorxiv_url(self, url):
        """检查是否为 bioRxiv URL"""
        return 'biorxiv.org' in url.lower()

    def extract_paper_id(self, url):
        """从 URL 中提取论文 ID"""
        patterns = [
            r'(\d{4}\.\d{2}\.\d{2}\.\d{6})',  # 标准格式：2025.09.10.675446
            r'/([^/]+)v\d+',  # 版本号格式
            r'/([^/]+)$'  # 最后一段
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                paper_id = match.group(1)
                # 验证是否为标准日期格式
                if re.match(r'\d{4}\.\d{2}\.\d{2}\.\d{6}', paper_id):
                    return paper_id

        return None

    def wait_for_download(self, timeout=30):
        """等待下载完成"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # 检查是否有新的 PDF 文件
            pdf_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))

            # 检查是否有正在下载的文件（.crdownload）
            downloading_files = glob.glob(os.path.join(self.download_dir, "*.crdownload"))

            if pdf_files and not downloading_files:
                # 找到 PDF 文件且没有正在下载的文件
                latest_file = max(pdf_files, key=os.path.getctime)
                logging.info(f"下载完成: {latest_file}")
                return latest_file

            time.sleep(1)

        logging.warning("下载超时")
        return None

    def download_biorxiv_pdf(self, url):
        """
        下载 bioRxiv PDF

        Args:
            url: bioRxiv 论文 URL

        Returns:
            tuple: (success, file_path, message)
        """
        if not self.is_biorxiv_url(url):
            return False, None, "不是 bioRxiv URL"

        if not self.setup_driver():
            return False, None, "WebDriver 设置失败"

        try:
            # 清理下载目录中的旧文件
            old_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))
            for old_file in old_files:
                try:
                    os.remove(old_file)
                except:
                    pass

            # 设置 Cookie（如果提供了 cookie_string）
            if self.cookie_string:
                logging.info("正在设置Cookie...")

                # 先访问主域名以设置Cookie上下文
                self.driver.get("https://www.biorxiv.org")
                time.sleep(2)

                # 解析并添加Cookie
                cookies = self.parse_cookie_string(self.cookie_string, ".biorxiv.org")

                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                        logging.info(f"✅ 已添加Cookie: {cookie['name']}")
                    except Exception as e:
                        logging.warning(f"⚠️  添加Cookie失败 {cookie['name']}: {e}")

                logging.info(f"📊 总共尝试添加 {len(cookies)} 个Cookie")

                # 验证Cookie是否设置成功
                current_cookies = self.driver.get_cookies()
                logging.info(f"🔍 当前浏览器中有 {len(current_cookies)} 个Cookie")

            logging.info(f"正在访问: {url}")
            self.driver.get(url)

            # 等待页面加载 - 使用与测试代码相同的随机延时
            time.sleep(random.uniform(2, 4))
            logging.info("页面加载完成")

            # 等待下载完成
            downloaded_file = self.wait_for_download()

            if downloaded_file and os.path.exists(downloaded_file):
                return True, downloaded_file, f"下载成功: {os.path.basename(downloaded_file)}"
            else:
                return False, None, "下载失败或文件不存在"

        except Exception as e:
            logging.error(f"下载过程中发生错误: {e}")
            return False, None, f"下载异常: {e}"
        finally:
            self.close_driver()

    def cleanup_file(self, file_path):
        """清理临时文件"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"已清理临时文件: {file_path}")
                return True
        except Exception as e:
            logging.warning(f"清理文件失败: {e}")
            return False
        return False

def download_biorxiv_with_selenium(url):
    """
    使用 Selenium 下载 bioRxiv PDF 的便捷函数

    Args:
        url: bioRxiv 论文 URL

    Returns:
        tuple: (success, file_path, message)
    """
    downloader = BioRxivSeleniumDownloader()
    return downloader.download_biorxiv_pdf(url)

if __name__ == "__main__":
    # 测试
    test_url = "https://www.biorxiv.org/cgi/reprint/2025.10.09.681381v1??collection"

    # 创建下载器实例
    downloader = BioRxivSeleniumDownloader()

    # 设置 cookie（可选）
    cookie_string = "_ga=GA1.1.286901066.1739618871; dsq__u=8tb657p8ldllr; dsq__s=8tb657p8ldllr; _lc2_fpi=28e3293678dc--01jm4nv7gvkp4j5sas17qt968v; cookie-agreed=2; _li_ss=CgA; cf_clearance=JNEmmRvDMaV4eE2T6BlzBjPmx4erKDMM9zOUFJe.aEY-1758710449-1.2.1.1-OCdlkdqtrMbjknFIGT8P7lrqdW8oqCnbgnr4AtXpAaEoydIJ0ihOgIh5USnDU62DirFyRartBHOADHDkUXa3iH7xzAI_IbPCJ_8cg6O1cXH9r1d.mpX6Cdw5qATyFlqZBmOzoTYa3deq0pFwZK2NYK9i8DP9pVvFqZxHECdBiy_e9vyMjWxP_2VHXxq0pQsrzjAl7uKhV8DJkjgcv99zkrtOttvXtQ96savnPYOlqOo; _ga_RZD586MC3Q=GS2.1.s1758793902$o7$g1$t1758794165$j60$l0$h0; _cfuvid=.tjpF4QGjNS.bYKaTJXEaXdtKgMs2EZS1vmwUJvrfxQ-1760244202528-0.0.1.1-604800000; __cf_bm=R2T2yj1BvWtCpWv_k7haN_RuhRrurnBt9Jjn.i7ssxQ-1760322277-1.0.1.1-fXNIfjavwLYg8OtnlQF6QG0aiZ4zVoTYby.9MUNb_TNWWb7yEf8iR9VhHTqGIvfJseyIQTdmlvTNZRcDAOH.ygQdNTqRYY5YU9UJf.1MCIc; SSESS1dd6867f1a1b90340f573dcdef3076bc=ILHNE1wvpfWHqye7T7VzggfTUjfqih5r3virV3nl3UQ"
    downloader.set_cookie_string(cookie_string)

    success, file_path, message = downloader.download_biorxiv_pdf(test_url)

    print(f"下载结果: {success}")
    print(f"文件路径: {file_path}")
    print(f"消息: {message}")

    if success and file_path:
        print(f"文件大小: {os.path.getsize(file_path)} bytes")

        # 测试清理
        downloader.cleanup_file(file_path)