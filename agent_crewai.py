import base64
import email
import faulthandler
import imaplib
import logging
import os
import quopri
import re
import time
from datetime import datetime, timedelta
from email import policy
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qs, unquote

import backoff
import requests
from bs4 import BeautifulSoup
from crewai.telemetry import Telemetry
from dotenv import load_dotenv

from feishu.feishu import file_upload, create_file
from feishu.feishu_webhook import send_feishu_message
from utils import process_paper, sanitize_file_name

os.environ["OTEL_SDK_DISABLED"] = "true"
faulthandler.enable()


# import threading
# def print_tracebacks():
#     threading.Timer(120, print_tracebacks).start()  # 每5秒打印一次
#     faulthandler.dump_traceback()
#
# print_tracebacks()


def noop(*args, **kwargs):
    print("Telemetry method called and noop'd\n")
    pass


for attr in dir(Telemetry):
    if callable(getattr(Telemetry, attr)) and not attr.startswith("__"):
        setattr(Telemetry, attr, noop)

# def cleanup_processes():
#     # Get all active threads
#     for thread in threading.enumerate():
#         if thread != threading.current_thread():
#             try:
#                 thread.join(timeout=1.0)  # Give threads 1 second to cleanup
#             except:
#                 pass
#
#
#
# # Register cleanup on program exit
# def signal_handler(signum, frame):
#     cleanup_processes()
#     sys.exit(0)
#
# signal.signal(signal.SIGINT, signal_handler)
# signal.signal(signal.SIGTERM, signal_handler)




os.environ['CREWAI_TELEMETRY_OPT_OUT'] = 'FALSE'
# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# QQ email IMAP settings----
# IMAP_SERVER = 'imap.qq.com'
# EMAIL_ACCOUNT = '2353050774@qq.com'
# # 授权码
# PASSWORD = 'ftiqtavrpghddjeg'
IMAP_SERVER = 'imap.qq.com'
EMAIL_ACCOUNT = '105150326@qq.com'
# 授权码
PASSWORD = 'smoevzzqpdmkcadd'

# IMAP_SERVER = 'imap.163.com'
# EMAIL_ACCOUNT = 'shilu_46@163.com'
# PASSWORD = 'XBdsr38YKHhDAZNh'

# Firecrawl API settings
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
FIRECRAWL_API_URL = 'http://140.143.139.183:3002/v1'

# 监控发件人邮箱地址
SENDER_EMAIL = 'cshljnls-mailer@alerts.highwire.org'
DAYS_RECENT = 7



os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'












@backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=5)
def get_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, PASSWORD)
        mail.select("inbox")  # Select inbox
        result, data = mail.search(None, 'FROM', SENDER_EMAIL)
        email_ids = data[0].split()
        return mail, email_ids
    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
        return None, []

def decode_content(part):
    charset = part.get_content_charset() or 'utf-8'
    payload = part.get_payload(decode=True)

    # Handle different encoding methods
    if part['Content-Transfer-Encoding'] == 'quoted-printable':
        decoded_content = quopri.decodestring(payload).decode(charset, errors='ignore')
    elif part['Content-Transfer-Encoding'] == 'base64':
        decoded_content = base64.b64decode(payload).decode(charset, errors='ignore')
    else:
        decoded_content = payload.decode(charset, errors='ignore')
    
    return decoded_content
    

@backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=5)
def fetch_email_content(mail, email_id):
    try:
        logging.info(f"Fetching email ID: {email_id}")
        print(f"Fetching email ID: {email_id}")
        result, data = mail.fetch(email_id, "(RFC822)")
        if result != 'OK':
            logging.error(f"Failed to fetch email ID: {email_id}, result: {result}")
            return None

        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email, policy=policy.default)

        # Check the sender
        if email_message['From'] and SENDER_EMAIL not in email_message['From']:
            logging.info(f"Email ID {email_id} is not from the expected sender.")
            return None
        subject = email_message['Subject']
        # 无法根据主题判断
        # if "新的" not in subject:
        #     logging.info(f"Email ID {email_id} subject does not contain '新的'.")
        #     return None

        # Check the date
        email_date = parsedate_to_datetime(email_message['Date'])
        now = datetime.now(email_date.tzinfo)
        if email_date < now - timedelta(days=DAYS_RECENT):
            logging.info(f"Email ID {email_id} is older than the specified range.")
            print(f"Email ID {email_id} is older than the specified range.")
            return None

        # Extract content from the email
        content = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() in ["text/plain", "text/html"]:
                    content += decode_content(part)
        else:
            content = decode_content(email_message)

        return content, subject, email_date

    except Exception as e:
        logging.error(f"Error getting email content for email ID: {email_id}: {e}")
        return None


def normalize_biorxiv_url(url):
    try:
         # 修正参数分隔符（将双问号替换为单问号）
        url = re.sub(r'\?+', '?', url)
        # 移除collection参数
        url = re.sub(r'[\?&]collection', '', url)

        # 检查是否是旧格式的 URL (cgi/content/abstract)
        if 'cgi/content/abstract' in url:
            # 提取文章ID
            match = re.search(r'abstract/(\d{4}\.\d{2}\.\d{2}\.\d+v\d+)', url)
            if match:
                article_id = match.group(1)
                # 构造新格式的 URL
                new_url = f"https://www.biorxiv.org/content/10.1101/{article_id}.abstract"
                logging.info(f"Converted bioRxiv URL from {url} to {new_url}")
                return new_url

        return url
    except Exception as e:
        logging.error(f"Error normalizing bioRxiv URL {url}: {e}")
        return url


def get_final_url(input_url):
    try:
        # 提取并解码url参数
        parsed_url = urlparse(input_url)
        query_params = parse_qs(parsed_url.query)
        encoded_url = query_params.get('url', [None])[0]
        
        if not encoded_url:
            logging.error(f"No 'url' parameter found in {input_url}")
            return None

        final_url = unquote(encoded_url)
        logging.info(f"Decoded URL: {final_url}")
        return final_url
    except requests.RequestException as e:
        logging.error(f"Error resolving final URL for {input_url}: {e}")
        return None

def extract_urls(content):
    logging.info('Extracting URLs from content')
    soup = BeautifulSoup(content, 'html.parser')
    # 新增URL规范化处理
    pdf_urls = [
        normalize_biorxiv_url(a['href'])  # 清理URL格式
        for div in soup.find_all('div', class_='view_list')
        for a in div.find_all('a', href=True)
        if a['href'].startswith('http') and a.get_text() == '[PDF]'
    ]

    # 提取标题
    titles = [div.get_text().strip()
              for div in soup.find_all('div', class_='citation_title')]

    # 将标题和URL组合成字典列表
    return [{"title": title, "url": url} for title, url in zip(titles, pdf_urls)]


def firecrawl_submit_crawl(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Referer": "https://www.biorxiv.org/",
        'Content-Type': 'application/json'
    }
    logging.info(f"Submitting crawl job for URL: {url}")
    print(f"Submitting crawl job for URL: {url}")
    try:
        response = requests.post(
            f'{FIRECRAWL_API_URL}/crawl',
           headers=headers,  # 使用合并后的请求头
            json={
                'url': url,
                'limit': 1,
                'scrapeOptions': {
                    'formats': ['markdown']
                },
                "maxDepth": 0,
                "limit": 1,
            },
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        if data.get('success'):
            return data['id']
        else:
            logging.error(f"Crawl job submission failed for URL: {url}")
            return None
    except requests.RequestException as e:
        logging.error(f"Error submitting crawl job: {e}")
    return None

def firecrawl_check_crawl(job_id):
    logging.info(f"Checking crawl job: {job_id}")
    print(f"Checking crawl job: {job_id}")
    try:
        response = requests.get(
            f'{FIRECRAWL_API_URL}/crawl/{job_id}',
            headers={
                'Content-Type': 'application/json',
            }
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error checking crawl job: {e}")
    return None

def firecrawl_crawl(url):
    logging.info(f"Processing URL: {url}")
    print(f"Processing URL: {url}")
    job_id = firecrawl_submit_crawl(url)
    if not job_id:
        return None

    max_attempts = 120  # 1 minute total waiting time
    for _ in range(max_attempts):
        result = firecrawl_check_crawl(job_id)
        logging.info(f"Crawl job result: {result}") 
        print(f"Crawl job result: {result}") 
        if result and result['status'] == 'completed':
            return {"markdown":result['data'][0]['markdown'] ,"metadata":result['data'][0]['metadata']} # Assuming we want the first page's markdown
        elif result and result['status'] == 'failed':
            logging.error(f"Crawl job failed for URL: {url}")
            return None
        time.sleep(10)  # Wait for 5 seconds before checking again
    
    logging.error(f"Crawl job timed out for URL: {url}")
    return None


def process_size(str):
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    with open(f"{now_str}_size.txt", 'w', encoding='utf-8') as f:
        f.write(f"{str}\n")


def main():
    mail, email_ids = get_emails()
    if not mail or len(email_ids) == 0:
        logging.info("No emails found or connection failed.")
        return

    email_subject = []
    for email_id in email_ids:
        result = fetch_email_content(mail, email_id)
        if result:
            content, subject, email_date = result
            url_title = extract_urls(content)
            email_subject.append({"subject": subject, "email_date": email_date, "urls": url_title})

    print(f'-----------all size: {len(email_subject)}')
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    # email_subject 写入文件
    for item in email_subject:
        urls = [entry['url'] for entry in item.get('urls', [])]
        urls = list(set(urls))
        with open(f"{now_str}_all_urls.txt", 'w', encoding='utf-8') as f:
            f.write(f"{item.get('subject')}\n")
            for url in urls:
                f.write(f"{url}\n")

    # 根据今天的日期获取对应的文件，读取文件内容，返回一个数组 对应元素是Url
    # 读取文件内容
    sucess_urls = []
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    if  os.path.exists(f"{now_str}_urls.txt"):
        with open(f"{now_str}_urls.txt", 'r', encoding='utf-8') as f:
            for line in f.readlines():
                sucess_urls.append(line.strip())

    count = 0

    # 处理逻辑
    for item in email_subject:
        # 创建文件夹
        all_paper_urls = item.get('urls')
        if len(all_paper_urls) == 0:
            continue
        subject = item.get('subject')
        email_date = item.get('email_date')
        email_date = email_date.strftime("%Y-%m-%d_%H-%M-%S")  # 转换为字符串
        email_date = sanitize_file_name(email_date)
        file_token = create_file(subject, email_date)
        send_feishu_message(
            f"开始执行主题为:{subject}的邮件,总共{len(all_paper_urls)}条数据,获取到文件夹token:{file_token}")
        for url_item in all_paper_urls:
            url = url_item['url']
            file_title = url_item['title']
            if file_token is None:
                logging.error("No file token found. Exiting.")
                send_feishu_message(
                    f"No file token found. Exiting.")
                break
            # if count == 3:
            #     logging.info("强制结束.")
            #     break
            if url in sucess_urls:
                logging.info(f"URL: {url} has been processed before.")
                count += 1
                print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')
                process_size(f'all size: {len(all_paper_urls)} ;current size: {count}')
                send_feishu_message(
                    f"URL: {url} has been processed before.")
                continue
            try:
                result = process_paper(url)
            except Exception as e:
                send_feishu_message(
                    f":异常:解析URL解析失败: {url}: {e}")
                logging.error(f"Error processing URL: {url}: {e}")
                continue
            if result:
                try:
                    output_file, formatted_output = result
                    file_name = email_date + "_" + file_title + ".md"
                    file_name = sanitize_file_name(file_name)
                    # 判断文件是否存在，如果不存在创建文件增加metadata
                    if not os.path.exists(file_name):
                        with open(file_name, 'w', encoding='utf-8') as f:
                            f.write(f"\n")
                    with open(file_name, 'a', encoding='utf-8') as f:
                        f.write(f"{formatted_output}\n\n")
                    logging.info(f"Processed and wrote result for URL: {url}")
                    # 写入成功的url
                    with open(f"{now_str}_urls.txt", 'a', encoding='utf-8') as f:
                        f.write(f"{url}\n")
                    # 写入飞书
                    if result:
                        file_upload(file_token, file_name)
                        # 删除本地文件
                        os.remove(file_name)
                except Exception as e:
                    send_feishu_message(
                        f":异常:处理文件结果={result}上传飞书异常: {url}: {e}")
                    logging.error(f"Error uploading URL: {url}: {e}")

            else:
                send_feishu_message(
                    f":Failed to process 执行异常,获取PDF内容失败: {url}")
                logging.warning(f"Failed to process URL: {url}")
            count += 1
            # print all and current count
            print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')
            process_size(f'all size: {len(all_paper_urls)} ;current size: {count}')
        send_feishu_message(
            f"结束执行主题为:{subject}的邮件,总共{len(all_paper_urls)}条数据,获取到文件夹token:{file_token}")

    logging.info("All papers processed. ")
            

if __name__ == "__main__":
    main()
