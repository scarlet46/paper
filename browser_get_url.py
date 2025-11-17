from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import time


def get_real_url_with_visual_browser(url, wait_time=15):
    """
    使用可视化浏览器获取最终跳转的真实URL地址

    Args:
        url (str): 目标URL地址
        wait_time (int): 等待页面加载的时间（秒），默认15秒

    Returns:
        str: 最终跳转后的真实URL地址，如果失败返回None
    """
    driver = None
    try:
        # 配置Chrome选项（可视化模式）
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1200,800')

        # 启动浏览器
        print(f"🚀 正在启动Chrome浏览器...")
        driver = webdriver.Chrome(options=chrome_options)

        print(f"🔍 正在访问: {url}")

        # 访问URL
        driver.get(url)

        # 等待页面加载
        print(f"⏳ 等待页面加载 ({wait_time}秒)...")
        time.sleep(wait_time)

        # 等待页面完全加载
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            print("✅ 页面加载完成")
        except:
            print("⚠️ 页面可能仍在加载中，但继续获取URL")

        # 获取最终URL
        final_url = driver.current_url

        print(f"🎯 最终URL: {final_url}")

        return final_url

    except Exception as e:
        print(f"❌ 获取URL失败: {str(e)}")
        return None

    finally:
        # 关闭浏览器
        if driver:
            print("🔚 正在关闭浏览器...")
            driver.quit()
#
#
# # 使用示例
# if __name__ == "__main__":
#     test_url = "https://www.biorxiv.org/cgi/reprint/2025.02.17.638732v2??collection"
#     real_url = get_real_url_with_visual_browser(test_url)
#
#     if real_url:
#         print(f"✅ 成功获取真实URL: {real_url}")
#     else:
#         print("❌ 获取URL失败")
