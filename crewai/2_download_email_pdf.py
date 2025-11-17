import atexit
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

import undetected_chromedriver as uc

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BatchPDFDownloader:
    """
    批量PDF下载器，基于test.py的PDFDownloader改进
    支持批量下载，复用session，避免重复触发五秒盾
    """

    def __init__(self, base_download_dir: str = "email_download", headless: bool = False):
        """
        初始化批量下载器

        Args:
            base_download_dir (str): 基础下载目录
            headless (bool): 是否无头模式运行
        """
        self.base_download_dir = os.path.abspath(base_download_dir)
        os.makedirs(self.base_download_dir, exist_ok=True)

        self.driver = None
        self.is_initialized = False
        self.current_domain = None
        
        # 线程锁，保护浏览器操作
        self.driver_lock = Lock()

        # 注册退出时清理
        atexit.register(self.cleanup)

        # 配置选项
        self.options = uc.ChromeOptions()
        self.options.add_experimental_option('prefs', {
            'download.prompt_for_download': False,
            'plugins.always_open_pdf_externally': True,
        })

        if headless:
            self.options.add_argument('--headless')

        # 添加稳定性选项
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')

    def _init_driver(self):
        """初始化浏览器驱动"""
        if not self.is_initialized:
            logging.info("🚀 初始化浏览器...")
            self.driver = uc.Chrome(options=self.options, version_main=141)
            self.is_initialized = True
            logging.info("✅ 浏览器初始化完成")

    def _ensure_domain_session(self, url: str):
        """确保与目标域名建立了session"""
        domain = url.split('/')[2]

        if self.current_domain != domain:
            logging.info(f"🌐 建立与 {domain} 的session...")
            home_url = f"https://{domain}/"

            self.driver.get(home_url)
            logging.info(f"✅ 成功访问 {domain} 主页")

            # 等待页面加载并建立session
            time.sleep(5)
            self.current_domain = domain
            logging.info(f"🔗 Session已建立，当前域名: {self.current_domain}")

    def sanitize_file_name(self, filename: str, max_length: int = 100) -> str:
        """
        清理文件名，移除不合法字符并限制长度
        
        Args:
            filename: 原始文件名
            max_length: 最大文件名长度（不包括扩展名）
        
        Returns:
            str: 清理后的文件名
        """
        # 移除或替换不合法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除多余的空格和点
        filename = re.sub(r'\s+', '_', filename)
        filename = filename.strip('.')
        
        # 限制文件名长度（考虑.pdf扩展名）
        if len(filename) > max_length:
            # 如果有.pdf扩展名，先移除
            if filename.lower().endswith('.pdf'):
                name_part = filename[:-4]
                filename = name_part[:max_length] + '.pdf'
            else:
                filename = filename[:max_length]
        
        return filename

    def format_email_date(self, email_date: str) -> str:
        """
        将邮件日期转换为正常的年月日时分秒格式
        
        Args:
            email_date: 原始邮件日期字符串
            
        Returns:
            str: 格式化后的日期字符串 (YYYY-MM-DD_HH-MM-SS)
        """
        try:
            # 尝试解析常见的邮件日期格式
            # 如果已经是标准格式，直接返回
            if re.match(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}', email_date):
                return email_date

            # 尝试解析RFC2822格式 (如: Mon, 13 Oct 2025 10:30:45 +0800)
            try:
                dt = datetime.strptime(email_date.split(' +')[0], '%a, %d %b %Y %H:%M:%S')
                return dt.strftime('%Y-%m-%d_%H-%M-%S')
            except:
                pass

            # 尝试解析ISO格式 (如: 2025-10-13T10:30:45)
            try:
                if 'T' in email_date:
                    dt = datetime.fromisoformat(email_date.replace('T', ' ').split('.')[0])
                    return dt.strftime('%Y-%m-%d_%H-%M-%S')
            except:
                pass

            # 尝试解析其他常见格式
            formats_to_try = [
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%d/%m/%Y %H:%M:%S',
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%d/%m/%Y'
            ]

            for fmt in formats_to_try:
                try:
                    dt = datetime.strptime(email_date, fmt)
                    return dt.strftime('%Y-%m-%d_%H-%M-%S')
                except:
                    continue

            # 如果都无法解析，使用当前时间
            logging.warning(f"⚠️ 无法解析邮件日期格式: {email_date}，使用当前时间")
            return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

        except Exception as e:
            logging.error(f"❌ 日期格式化出错: {e}，使用当前时间")
            return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    def create_download_directory(self, date_str: str, subject: str, email_date: str) -> str:
        """
        创建下载目录：email_download/日期/邮件主题&&time&&时间

        Args:
            date_str: 处理日期字符串 (YYYYMMDD)
            subject: 邮件主题
            email_date: 邮件日期

        Returns:
            str: 创建的目录路径
        """
        # 创建日期目录
        date_dir = os.path.join(self.base_download_dir, date_str)
        os.makedirs(date_dir, exist_ok=True)

        # 格式化邮件日期为标准格式
        formatted_date = self.format_email_date(email_date)

        # 创建邮件主题&&time&&时间目录
        subject_clean = self.sanitize_file_name(subject)
        folder_name = f"{subject_clean}&&time&&{formatted_date}"

        download_dir = os.path.join(date_dir, folder_name)
        os.makedirs(download_dir, exist_ok=True)

        logging.info(f"📁 创建下载目录: {download_dir}")
        return download_dir

    def download_single_pdf(self, pdf_url: str, download_dir: str, title: str, wait_time: int = 15, use_lock: bool = True) -> Optional[str]:
        """
        下载单个PDF文件（线程安全）

        Args:
            pdf_url (str): PDF文件的URL
            download_dir (str): 下载目录
            title (str): PDF标题
            wait_time (int): 下载等待时间（秒）
            use_lock (bool): 是否使用线程锁（并发下载时需要）

        Returns:
            Optional[str]: 成功时返回下载的文件完整路径，失败时返回None
        """
        try:
            logging.info(f"🔄 开始下载PDF: {title}")
            logging.info(f"🔗 URL: {pdf_url}")

            # 使用线程锁保护浏览器操作
            if use_lock:
                self.driver_lock.acquire()
            
            try:
                # 设置当前下载目录
                self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                    'behavior': 'allow',
                    'downloadPath': download_dir
                })

                # 记录下载前的文件数量
                files_before = len([f for f in os.listdir(download_dir) if f.endswith('.pdf')])

                # 确保与目标域名建立session
                self._ensure_domain_session(pdf_url)

                # 访问PDF链接
                logging.info("📄 访问PDF下载链接...")
                self.driver.get(pdf_url)
                logging.info("✅ 成功访问PDF链接")
            finally:
                if use_lock:
                    self.driver_lock.release()

            # 等待下载完成
            logging.info(f"⏳ 等待下载完成 ({wait_time}秒)...")
            time.sleep(wait_time)

            # 检查是否有新的PDF文件
            current_pdf_files = [f for f in os.listdir(download_dir) if f.endswith('.pdf')]
            files_after = len(current_pdf_files)

            if files_after > files_before:
                # 获取最新的PDF文件（按修改时间排序）
                pdf_files_with_time = []
                for filename in current_pdf_files:
                    filepath = os.path.join(download_dir, filename)
                    mtime = os.path.getmtime(filepath)
                    pdf_files_with_time.append((filename, mtime))

                # 按修改时间降序排序，取最新的
                latest_file = sorted(pdf_files_with_time, key=lambda x: x[1], reverse=True)[0][0]
                original_path = os.path.join(download_dir, latest_file)

                # 使用PDF title重命名文件
                clean_title = self.sanitize_file_name(title, max_length=80)  # 限制为80字符
                if not clean_title:
                    clean_title = "Unknown_PDF"

                # 确保文件名以.pdf结尾
                if not clean_title.lower().endswith('.pdf'):
                    clean_title += '.pdf'

                new_filename = clean_title
                new_path = os.path.join(download_dir, new_filename)

                # 检查路径长度，Windows有260字符限制
                if len(new_path) > 250:  # 留一些余量
                    # 进一步缩短文件名
                    max_name_length = 250 - len(download_dir) - 5  # 5 for .pdf and separator
                    clean_title = self.sanitize_file_name(title, max_length=max_name_length)
                    if not clean_title.lower().endswith('.pdf'):
                        clean_title += '.pdf'
                    new_filename = clean_title
                    new_path = os.path.join(download_dir, new_filename)

                # 如果目标文件名已存在，添加序号
                counter = 1
                while os.path.exists(new_path):
                    name_without_ext = clean_title[:-4] if clean_title.lower().endswith('.pdf') else clean_title
                    new_filename = f"{name_without_ext}_{counter}.pdf"
                    new_path = os.path.join(download_dir, new_filename)
                    counter += 1
                    
                    # 再次检查路径长度
                    if len(new_path) > 250:
                        # 如果加序号后路径过长，缩短基础名称
                        name_without_ext = name_without_ext[:max(10, len(name_without_ext) - 10)]
                        new_filename = f"{name_without_ext}_{counter}.pdf"
                        new_path = os.path.join(download_dir, new_filename)

                # 重命名文件
                try:
                    # 确保原文件存在
                    if not os.path.exists(original_path):
                        logging.warning(f"⚠️ 原文件不存在: {original_path}，保持原文件名")
                        new_path = original_path
                        new_filename = latest_file
                    # 确保目标目录存在
                    elif not os.path.exists(download_dir):
                        logging.warning(f"⚠️ 目标目录不存在: {download_dir}，保持原文件名")
                        new_path = original_path
                        new_filename = latest_file
                    else:
                        os.rename(original_path, new_path)
                        logging.info(f"📝 文件重命名: {latest_file} -> {new_filename}")
                except Exception as rename_error:
                    logging.warning(f"⚠️ 文件重命名失败: {rename_error}，保持原文件名")
                    new_path = original_path
                    new_filename = latest_file

                file_size = os.path.getsize(new_path)

                logging.info(f"✅ PDF下载成功!")
                logging.info(f"📄 文件名: {new_filename}")
                logging.info(f"📁 完整路径: {new_path}")
                logging.info(f"📊 文件大小: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")

                return new_path
            else:
                logging.warning("❌ 未检测到新的PDF文件下载")
                return None

        except Exception as e:
            logging.error(f"❌ 下载出错: {e}")
            return None

    def read_json_files(self, date_folder: str) -> List[Dict]:
        """
        读取指定日期文件夹下的所有JSON文件

        Args:
            date_folder (str): 日期文件夹路径

        Returns:
            List[Dict]: JSON文件内容列表
        """
        json_files_data = []

        if not os.path.exists(date_folder):
            logging.error(f"❌ 日期文件夹不存在: {date_folder}")
            return json_files_data

        for filename in os.listdir(date_folder):
            if filename.endswith('.json'):
                filepath = os.path.join(date_folder, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data['source_file'] = filename
                        json_files_data.append(data)
                        logging.info(f"📄 读取JSON文件: {filename}")
                except Exception as e:
                    logging.error(f"❌ 读取JSON文件失败 {filename}: {e}")

        logging.info(f"📊 总共读取到 {len(json_files_data)} 个JSON文件")
        return json_files_data

    def batch_download_from_date_folder(self, date_folder: str, wait_time: int = 15) -> Dict[str, Dict]:
        """
        从指定日期文件夹批量下载PDF

        Args:
            date_folder (str): 日期文件夹路径 (如: email_address/20251013)
            wait_time (int): 每个文件的下载等待时间

        Returns:
            Dict[str, Dict]: 下载结果统计
        """
        # 确保驱动已初始化
        self._init_driver()

        # 读取所有JSON文件
        json_files_data = self.read_json_files(date_folder)

        if not json_files_data:
            logging.warning("❌ 没有找到JSON文件")
            return {}

        # 获取日期字符串
        date_str = os.path.basename(date_folder)

        results = {}
        total_files = 0
        success_count = 0

        logging.info(f"📦 开始批量下载，共 {len(json_files_data)} 个邮件")

        for i, email_data in enumerate(json_files_data, 1):
            logging.info(f"\n{'=' * 60}")
            logging.info(f"📧 处理邮件 {i}/{len(json_files_data)}")

            email_info = email_data.get('email_info', {})
            pdf_links = email_data.get('pdf_links', [])

            subject = email_info.get('subject', 'Unknown')
            email_date = email_info.get('email_date', 'Unknown')

            logging.info(f"📧 邮件主题: {subject}")
            logging.info(f"📅 邮件日期: {email_date}")
            logging.info(f"📄 PDF数量: {len(pdf_links)}")

            if not pdf_links:
                logging.info("⚠️ 该邮件没有PDF链接，跳过")
                continue

            # 创建下载目录
            download_dir = self.create_download_directory(date_str, subject, email_date)

            # 下载该邮件的所有PDF
            email_results = {}
            for j, pdf_info in enumerate(pdf_links, 1):
                logging.info(f"\n📄 下载PDF {j}/{len(pdf_links)}")

                title = pdf_info.get('title', f'PDF_{j}')
                url = pdf_info.get('url', '')

                if not url:
                    logging.warning(f"⚠️ PDF链接为空，跳过: {title}")
                    continue

                total_files += 1
                file_path = self.download_single_pdf(url, download_dir, title, wait_time)

                if file_path:
                    success_count += 1
                    email_results[url] = {
                        'status': 'success',
                        'file_path': file_path,
                        'title': title
                    }
                else:
                    email_results[url] = {
                        'status': 'failed',
                        'file_path': None,
                        'title': title
                    }

                # 下载间隔，避免过于频繁
                if j < len(pdf_links):
                    logging.info("⏳ 等待3秒后下载下一个文件...")
                    time.sleep(3)

            results[email_data['source_file']] = {
                'email_info': email_info,
                'download_dir': download_dir,
                'results': email_results
            }

        # 输出总结果
        logging.info(f"\n{'=' * 60}")
        logging.info("📊 批量下载完成!")
        logging.info(f"✅ 成功下载: {success_count}/{total_files}")
        logging.info(f"❌ 下载失败: {total_files - success_count}/{total_files}")

        return results

    def batch_download_concurrent(self, date_folder: str, wait_time: int = 15, max_workers: int = 3) -> Dict[str, Dict]:
        """
        从指定日期文件夹并发批量下载PDF
        
        注意：由于使用单个浏览器实例，并发度受限于线程锁。
        建议max_workers设置为2-3，避免过多线程等待。
        
        Args:
            date_folder (str): 日期文件夹路径 (如: email_address/20251013)
            wait_time (int): 每个文件的下载等待时间
            max_workers (int): 最大并发线程数（建议2-3）
            
        Returns:
            Dict[str, Dict]: 下载结果统计
        """
        # 确保驱动已初始化
        self._init_driver()
        
        # 读取所有JSON文件
        json_files_data = self.read_json_files(date_folder)
        
        if not json_files_data:
            logging.warning("❌ 没有找到JSON文件")
            return {}
        
        # 获取日期字符串
        date_str = os.path.basename(date_folder)
        
        # 准备所有下载任务
        download_tasks = []
        for email_data in json_files_data:
            email_info = email_data.get('email_info', {})
            pdf_links = email_data.get('pdf_links', [])
            
            subject = email_info.get('subject', 'Unknown')
            email_date = email_info.get('email_date', 'Unknown')
            
            if not pdf_links:
                continue
            
            # 创建下载目录
            download_dir = self.create_download_directory(date_str, subject, email_date)
            
            for pdf_info in pdf_links:
                title = pdf_info.get('title', 'Unknown')
                url = pdf_info.get('url', '')
                
                if url:
                    download_tasks.append({
                        'url': url,
                        'title': title,
                        'download_dir': download_dir,
                        'email_info': email_info,
                        'source_file': email_data['source_file']
                    })
        
        total_files = len(download_tasks)
        logging.info(f"📦 开始并发下载，共 {total_files} 个PDF文件，并发数: {max_workers}")
        
        results = {}
        success_count = 0
        
        # 使用线程池并发下载
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(
                    self.download_single_pdf,
                    task['url'],
                    task['download_dir'],
                    task['title'],
                    wait_time,
                    True  # use_lock=True
                ): task
                for task in download_tasks
            }
            
            # 处理完成的任务
            completed = 0
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                completed += 1
                
                try:
                    file_path = future.result()
                    
                    # 组织结果
                    source_file = task['source_file']
                    if source_file not in results:
                        results[source_file] = {
                            'email_info': task['email_info'],
                            'download_dir': task['download_dir'],
                            'results': {}
                        }
                    
                    if file_path:
                        success_count += 1
                        results[source_file]['results'][task['url']] = {
                            'status': 'success',
                            'file_path': file_path,
                            'title': task['title']
                        }
                        logging.info(f"✅ [{completed}/{total_files}] 下载成功: {task['title']}")
                    else:
                        results[source_file]['results'][task['url']] = {
                            'status': 'failed',
                            'file_path': None,
                            'title': task['title']
                        }
                        logging.warning(f"❌ [{completed}/{total_files}] 下载失败: {task['title']}")
                        
                except Exception as e:
                    logging.error(f"❌ [{completed}/{total_files}] 下载出错: {task['title']} - {e}")
                    
                    source_file = task['source_file']
                    if source_file not in results:
                        results[source_file] = {
                            'email_info': task['email_info'],
                            'download_dir': task['download_dir'],
                            'results': {}
                        }
                    
                    results[source_file]['results'][task['url']] = {
                        'status': 'error',
                        'file_path': None,
                        'title': task['title'],
                        'error': str(e)
                    }
        
        # 输出总结果
        logging.info(f"\n{'=' * 60}")
        logging.info("📊 并发批量下载完成!")
        logging.info(f"✅ 成功下载: {success_count}/{total_files}")
        logging.info(f"❌ 下载失败: {total_files - success_count}/{total_files}")
        
        return results

    def cleanup(self):
        """清理资源"""
        if self.driver:
            logging.info("🔄 关闭浏览器...")
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.is_initialized = False
            self.current_domain = None
            logging.info("✅ 浏览器已关闭")

    def __enter__(self):
        """支持 with 语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句"""
        self.cleanup()


def main(email_address, concurrent: bool = False, max_workers: int = 3):
    """
    主函数
    
    Args:
        email_address (str): 邮件地址文件夹路径
        concurrent (bool): 是否使用并发下载
        max_workers (int): 并发线程数（仅在concurrent=True时有效）
    """
    date_folder = email_address

    if not os.path.exists(date_folder):
        print(f"❌ 错误: 文件夹不存在 {date_folder}")
        return

    mode = "并发" if concurrent else "顺序"
    logging.info(f"🚀 开始{mode}批量下载PDF，目标文件夹: {date_folder}")
    if concurrent:
        logging.info(f"⚡ 并发线程数: {max_workers}")

    with BatchPDFDownloader() as downloader:
        if concurrent:
            results = downloader.batch_download_concurrent(date_folder, max_workers=max_workers)
        else:
            results = downloader.batch_download_from_date_folder(date_folder)

        if results:
            logging.info("🎉 批量下载任务完成!")
        else:
            logging.info("😞 没有文件被下载")


if __name__ == "__main__":
    # 使用并发下载，设置3个并发线程
    main(
        "D:\\PycharmProjects\\paper-summarizer\\paper-summarizer\\crewai\\email_address\\20251117",
        concurrent=True,  # 改为True启用并发下载
        max_workers=1     # 并发线程数
    )
