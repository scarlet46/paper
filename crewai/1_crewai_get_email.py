import base64
import email
import imaplib
import json
import logging
import os
import quopri
from datetime import datetime, timedelta
from email import policy
from email.utils import parsedate_to_datetime

import backoff
from bs4 import BeautifulSoup
from dotenv import load_dotenv

ERROR_CONTENT = '无法解码的Base64内容'

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# QQ email IMAP settings
IMAP_SERVER = 'imap.qq.com'
EMAIL_ACCOUNT = '105150326@qq.com'
# 授权码
PASSWORD = 'smoevzzqpdmkcadd'

# 监控发件人邮箱地址列表
SENDER_EMAILS = [
    'openRxiv-mailer@alerts.highwire.org',
    'cshljnls-mailer@alerts.highwire.org'
]
DAYS_RECENT = 1


@backoff.on_exception(backoff.expo, imaplib.IMAP4.error, max_tries=5)
def get_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, PASSWORD)
        mail.select("inbox")  # Select inbox

        # 搜索多个发件人的邮件
        all_email_ids = []
        for sender_email in SENDER_EMAILS:
            result, data = mail.search(None, 'FROM', sender_email)
            if result == 'OK' and data[0]:
                email_ids = data[0].split()
                all_email_ids.extend(email_ids)
                logging.info(f"找到来自 {sender_email} 的 {len(email_ids)} 封邮件")

        # 去重并返回
        unique_email_ids = list(set(all_email_ids))
        logging.info(f"总共找到 {len(unique_email_ids)} 封唯一邮件")
        return mail, unique_email_ids
    except Exception as e:
        logging.error(f"Error fetching emails: {e}")
        return None, []


def decode_content(part):
    charset = part.get_content_charset() or 'utf-8'
    payload = part.get_payload(decode=True)

    # 如果payload为None，返回空字符串
    if payload is None:
        return ""

    # 处理不同的编码方法
    content_transfer_encoding = part.get('Content-Transfer-Encoding', '').lower()

    try:
        if content_transfer_encoding == 'quoted-printable':
            decoded_content = quopri.decodestring(payload).decode(charset, errors='ignore')
        elif content_transfer_encoding == 'base64':
            # 修复Base64填充问题
            try:
                # 尝试直接解码
                decoded_content = base64.b64decode(payload).decode(charset, errors='ignore')
            except Exception as e:
                # 如果失败，尝试修复填充
                padding_fixed_payload = payload
                missing_padding = len(payload) % 4
                if missing_padding:
                    padding_fixed_payload = payload + b'=' * (4 - missing_padding)

                try:
                    decoded_content = base64.b64decode(padding_fixed_payload).decode(charset, errors='ignore')
                except:
                    # 如果仍然失败，尝试使用更宽松的解码方式
                    try:
                        import binascii
                        # 移除所有非base64字符
                        clean_payload = b''.join(c for c in payload if
                                                 c in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
                        decoded_content = binascii.a2b_base64(clean_payload).decode(charset, errors='ignore')
                    except:
                        # 如果所有尝试都失败，返回原始内容的字符串表示
                        decoded_content = f"[{ERROR_CONTENT}: {str(payload)}]"
        else:
            # 对于其他编码或无编码的情况
            if isinstance(payload, bytes):
                decoded_content = payload.decode(charset, errors='ignore')
            else:
                decoded_content = str(payload)
    except Exception as e:
        # 捕获所有异常，确保函数不会崩溃
        decoded_content = f"[解码错误: {str(e)}]"

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
        sender_found = False
        if email_message['From']:
            for sender_email in SENDER_EMAILS:
                if sender_email in email_message['From']:
                    sender_found = True
                    break

        if not sender_found:
            logging.info(f"Email ID {email_id} is not from any expected sender.")
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


# 解析内容的url 目前遇到两种,一种html 一种纯文本
def extract_urls(content):
    # 普通文本解析
    if ERROR_CONTENT in content:
        # 使用http://分割文本
        parts = content.split("http://")
        # 创建一个列表存储结果
        results = []
        # 对于每个http://部分(除了第一部分)
        for i in range(1, len(parts)):
            url = "http://" + parts[i].split()[0]
            # 向前查找最近的标题
            # 标题通常是以多个空格开头的行
            previous_text = parts[i - 1]
            lines = previous_text.split('\\r\\n')
            # 从后向前查找
            for line in reversed(lines):
                if line.strip() and line.startswith("       "):  # 7个空格是标题的特征
                    title = line.strip()
                    results.append({"title": title, "url": url})
                    break
        return results
    else:
        logging.info('Extracting URLs from content')
        soup = BeautifulSoup(content, 'html.parser')

        # 提取标题
        titles = [div.get_text().strip()
                  for div in soup.find_all('div', class_='citation_title')]

        # 提取链接 - 兼容两种格式
        pdf_urls = []
        view_list_divs = soup.find_all('div', class_='view_list')

        for div in view_list_divs:
            links = div.find_all('a', href=True)
            pdf_found = False

            for a in links:
                # 优先查找 [PDF] 链接
                if a['href'].startswith('http') and a.get_text().strip() == '[PDF]':
                    pdf_urls.append(a['href'])
                    pdf_found = True
                    break

            # 如果没有找到 [PDF] 链接，使用文章链接并转换为PDF格式
            if not pdf_found:
                for a in links:
                    if a['href'].startswith('http'):
                        # 移除查询参数并添加 .full.pdf 后缀
                        article_url = a['href'].split('?')[0]
                        pdf_url = article_url + '.full.pdf'
                        pdf_urls.append(pdf_url)
                        break

        # 将标题和URL组合成字典列表
        return [{"title": sanitize_file_name(title), "url": url}
                for title, url in zip(titles, pdf_urls)]


def sanitize_file_name(filename):
    """清理文件名，移除不合法字符"""
    import re
    # 移除或替换不合法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除多余的空格和点
    filename = re.sub(r'\s+', '_', filename)
    filename = filename.strip('.')
    return filename


def save_urls_to_file(subject, email_date, urls):
    """将URL保存到email_address文件夹下对应的目录中"""
    # 创建基础目录
    base_dir = "email_address"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    # 创建日期目录
    date_str = datetime.now().strftime("%Y%m%d")
    date_dir = os.path.join(base_dir, date_str)
    if not os.path.exists(date_dir):
        os.makedirs(date_dir)

    # 创建文件名：主题 + 邮件日期，防止重复
    subject_clean = sanitize_file_name(subject)
    email_date_str = email_date.strftime("%Y%m%d_%H%M%S") if isinstance(email_date, datetime) else str(email_date)
    email_date_clean = sanitize_file_name(email_date_str)
    filename = f"{subject_clean}_{email_date_clean}.json"
    filepath = os.path.join(date_dir, filename)

    # 准备JSON数据
    data = {
        "email_info": {
            "subject": subject,
            "email_date": email_date.isoformat() if isinstance(email_date, datetime) else str(email_date),
            "processed_date": datetime.now().isoformat(),
            "pdf_count": len(urls)
        },
        "pdf_links": []
    }

    # 添加PDF链接信息
    for i, url_item in enumerate(urls, 1):
        data["pdf_links"].append({
            "index": i,
            "title": url_item['title'],
            "url": url_item['url']
        })

    # 写入JSON文件
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logging.info(f"已保存 {len(urls)} 个PDF链接到文件: {filepath}")
    return filepath


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

    logging.info(f'获取到 {len(email_subject)} 封邮件')

    # 处理每封邮件的PDF链接
    for item in email_subject:
        urls = item.get('urls', [])
        if len(urls) == 0:
            logging.info(f"邮件 '{item.get('subject')}' 中没有找到PDF链接")
            continue

        subject = item.get('subject')
        email_date = item.get('email_date')

        # 保存PDF链接到文件
        saved_file = save_urls_to_file(subject, email_date, urls)
        logging.info(f"邮件 '{subject}' 包含 {len(urls)} 个PDF链接，已保存到: {saved_file}")

    logging.info("所有邮件处理完成")
    mail.close()
    mail.logout()


if __name__ == "__main__":
    main()