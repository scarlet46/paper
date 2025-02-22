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
from crewai import Agent, Task, Crew, LLM
from crewai.telemetry import Telemetry
from dotenv import load_dotenv

from feishu.feishu import file_upload, create_file
from pdf_server import process_pdf

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


# 设置 Ollama API 环境变量
# os.environ["OLLAMA_API_KEY"] = "your_ollama_api_key"
Model = "gpt-4o-mini"
os.environ["OPENAI_API_KEY"] = "sk-tA4X88vrZDn2RV5GDe54Ec3743744d7eBaB8F8Ae8a73F1Cf"
llm = LLM(model=Model, base_url="https://api.fast-tunnel.one/v1",
          api_key="sk-tA4X88vrZDn2RV5GDe54Ec3743744d7eBaB8F8Ae8a73F1Cf")

# Model = "deepseek-chat"
# llm = LLM(model=Model, base_url="https://api.deepseek.com/v1",
#           api_key="sk-5346b4837c81477592d7503a3de034ec")
# os.environ["OPENAI_API_KEY"] = "sk-tA4X88vrZDn2RV5GDe54Ec3743744d7eBaB8F8Ae8a73F1Cf"

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
DAYS_RECENT = 3



os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'


def process_agent():
    return Agent(
        role="学术内容处理专家",
        goal="清理网页内容，将其翻译成中文，并总结主要内容，重点包括标题、关键词、研究问题、方法、创新点和结论。",
        backstory="你是一名专业的学术内容处理专家，能够高效地清理、翻译和总结学术论文，确保技术术语的准确性和学术严谨性。",
        allow_delegation=False,
        verbose=True,
        llm=llm
    )


def create_process_task(markdown_content, url):
    return Task(
        description=(
            # f"请清理以下网页内容，将其转换为学术论文的格式，然后将清理后的内容翻译成中文，并总结主要内容。"
            # f"请确保输出的格式中，论文标题使用一级标题（#），其他部分（研究问题、关键词、方法、创新点和结论）使用二级标题（##）。"
            f"请清理以下 PDF 文件内容，并将其转换为学术论文的格式，同时翻译成中文。\n"
            f"确保输出的格式如下：\n"
            f" 【bioRxiv链接】：{url}\n"
            f"【精读地址】从 PDF 中提取的 DOI 链接或官方发布地址  \n"
            f"【代码地址】从 PDF 中提取的代码仓库地址，如 GitHub/Zenodo 等，若无则填写“文中未提供”  \n"
            f"- 论文标题使用一级标题（#）\n"
            f"- 其他部分（研究问题、关键词、方法、创新点和结论）使用二级标题（##）\n"
            f"- 删除冗余信息，如广告、非学术内容、页眉页脚等\n"
            f"- 仅保留正文内容，并优化语言表达，使其符合学术论文风格\n"
            f"- 从 PDF 文件中提取论文标题、作者、DOI、arXiv/bioRxiv 链接（如果有）\n"
            f"- 提取代码地址（如果存在），若无则标注为“文中未提供”\n"
            f"- 生成论文首页的截图（PNG 格式）\n\n"
            f"- '生物信息学算法'、'生物数据分析'还是'计算生物学建模' 为文献领域分类的 一级分类 \n\n"
            f"- 机器学习、序列分析、基因比对、结构预测、算法开发、深度学习、大模型、数据处理、单细胞数据注释工具、单细胞多组学分析、空间转录组数据分析、统计分析、多组学整合（基因组、转录组、蛋白质组、代谢组、表观组等）、实验数据挖掘、数学建模、系统生物学、计算模拟、网络分析和生物物理建模 为二级分类, \n\n"
            f"请确保最终输出格式如下（请使用 Markdown 格式）：\n\n"
            f"\n\n内容如下：\n\n{markdown_content}"
        ),
        agent=process_agent(),
        expected_output=(
            f"请严格按照格式整理 PDF 内容，不要输出无关信息，参考文献可忽略。\n"
            f"研究问题、方法、创新点和结论均需输出中文。"
            f"文章首页（带标题）截图（PNG格式)"
            "输出翻译后的论文内容（中文），最终返回的格式参考如下大纲格式如下：\n\n"
            f"【bioRxiv链接】：{url}\n"
            f"【精读地址】\n"
            f"【代码地址】\n"
            "论文中文标题"
            "论文英文标题"
            "关键词"
            "期刊"
            "作者和作者单位"
            "研究问题"
            "方法"
            "创新点"
            "文献领域分类 一级分类 二级分类"
            "研究内容补充 研究背景 关键技术 额外实验结果"
            "扩展应用"
            "结论"
            "总结"
        )
    )



def paper_type_agent():
    return Agent(
        role="生物计算与数据科学文献分类专家",
        goal="根据文献的研究内容，判断其属于'生物信息学算法'、'生物数据分析'还是'计算生物学建模'领域，并进一步细化到具体研究方向，"
             "如机器学习、序列分析、基因比对、结构预测、算法开发、深度学习、大模型、数据处理、单细胞数据注释工具、单细胞多组学分析、"
             "空间转录组数据分析、统计分析、多组学整合（基因组、转录组、蛋白质组、代谢组、表观组等）、实验数据挖掘、数学建模、系统生物学、"
             "计算模拟、网络分析和生物物理建模。",
        backstory="你是一名精通生物学与计算机算法交叉领域的专家，擅长分析文献的研究问题、数据类型、计算方法和生物学背景，"
                  "从而准确判断其所属的学术领域。你不仅能区分生物信息学算法、生物数据分析和计算生物学建模，还能根据具体研究内容，将文献分类到更具体的方向。",
        allow_delegation=False,
        verbose=True,
        llm=llm,
    )

def create_paper_type_task(content):
    return Task(
        description=(
            f"请阅读以下论文内容，分析其研究问题、方法和结论，判断该论文属于'生物信息学算法'、'生物数据分析'还是'计算生物学建模'领域"
            f"请基于论文的核心研究内容和技术领域进行判断，而不是仅仅依赖于关键词。"
            f"如果不属于上述两个领域，请返回'忽略'。"
            f"\n\n论文内容如下：\n\n{content}"
        ),
        agent=paper_type_agent(),
        expected_output=(
            "请只输出文献类型：'生物信息学算法'、'生物数据分析'还是'计算生物学建模'"
            "如果不属于这两种类型，返回 '忽略'。不要输出任何其他内容。"
        )
    )



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

        return content, subject

    except Exception as e:
        logging.error(f"Error getting email content for email ID: {email_id}: {e}")
        return None


def normalize_biorxiv_url(url):
    try:
        # 移除多余的问号和collection参数
        url = re.sub(r'\?+collection$', '', url)

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
    # 先找到 class 为 view_list 的 div，然后在其中找所有的链接
    urls = [a['href'] for div in soup.find_all('div', class_='view_list')
            for a in div.find_all('a', href=True)
            if a['href'].startswith('http') and a.get_text() == '[PDF]']

    # Resolve final URLs for any redirects
    # final_urls = []
    # for url in urls:
    #     # final_url = get_final_url(url)
    #     final_url = normalize_biorxiv_url(url)
    #     if final_url:
    #         final_urls.append(final_url)

    return urls


def firecrawl_submit_crawl(url):
    logging.info(f"Submitting crawl job for URL: {url}")
    print(f"Submitting crawl job for URL: {url}")
    try:
        response = requests.post(
            f'{FIRECRAWL_API_URL}/crawl',
            headers={
                'Content-Type': 'application/json',
            },
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




def process_paper(url):
    # markdown_content = firecrawl_crawl(url)
    markdown_content = process_pdf(url)
    logging.info(f"Processing paper markdown_content: {markdown_content}")
    if markdown_content is not None and markdown_content.strip():
        
        # 添加类型判断
        crew = Crew(
                agents=[process_agent()],
            tasks=[create_process_task(markdown_content, url)],
                share_crew=False,
                verbose=True
            )

        result = crew.kickoff().raw
        
        # 判断类型
        paper_type_crew = Crew(
            agents=[paper_type_agent()],
            tasks=[create_paper_type_task(result)],
            share_crew=False,
            verbose=True
        )
        paper_type = paper_type_crew.kickoff().raw
        logging.info(f"Paper type: {paper_type}")
        print(f"Paper type: {paper_type}")
        if "忽略" in paper_type :
            logging.info(f"Ignoring paper from URL: {url}")
            print(f"Ignoring paper from URL: {url}")
            return None

        # 根据类型设置文件名称
        now = datetime.now()
        now_str = now.strftime("%Y%m%d")
        output_file = f"{now_str}_{paper_type}"
        # Format the final output
        formatted_output = f"""{result} \n\n## 原文链接\n{url} \n\n"""
        return output_file, formatted_output
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
            content, subject = result
            urls = extract_urls(content)
            email_subject.append({"subject": subject, "urls": urls})

    print(f'-----------all size: {len(email_subject)}')
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    # email_subject 写入文件
    for item in email_subject:
        urls = list(set(item.get('urls')))
        with open(f"{now_str}_all_urls.txt", 'w', encoding='utf-8') as f:
            f.write(f"{item.get('subject')}\n")
            for url in urls:
                f.write(f"{url}\n")

    # # 根据今天的日期获取对应的文件，读取文件内容，返回一个数组 对应元素是Url
    # # 读取文件内容
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
        subject = item.get('subject')
        file_token = create_file(subject)
        for url in all_paper_urls:
            if file_token is None:
                logging.error("No file token found. Exiting.")
                break
            if count == 3:
                logging.info("强制结束.")
                break
            if url in sucess_urls:
                logging.info(f"URL: {url} has been processed before.")
                count += 1
                print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')
                process_size(f'all size: {len(all_paper_urls)} ;current size: {count}')
                continue
            try:
                result = process_paper(url)
            except Exception as e:
                logging.error(f"Error processing URL: {url}: {e}")
                continue
            if result:
                output_file, formatted_output = result
                # 判断文件是否存在，如果不存在创建文件增加metadata
                if not os.path.exists(output_file + ".md"):
                    with open(output_file + ".md", 'w', encoding='utf-8') as f:
                        f.write(f"\n")
                with open(output_file + ".md", 'a', encoding='utf-8') as f:
                    f.write(f"{formatted_output}\n\n")
                logging.info(f"Processed and wrote result for URL: {url}")
                # 写入成功的url
                with open(f"{now_str}_urls.txt", 'a', encoding='utf-8') as f:
                    f.write(f"{url}\n")
                # 写入飞书
                if result:
                    file_upload(file_token, output_file + ".md")
            else:
                logging.warning(f"Failed to process URL: {url}")
            count += 1
            # print all and current count
            print(f'-----------all size: {len(all_paper_urls)} ;current size: {count}------------------')
            process_size(f'all size: {len(all_paper_urls)} ;current size: {count}')

    logging.info("All papers processed.")
            

if __name__ == "__main__":
    main()
