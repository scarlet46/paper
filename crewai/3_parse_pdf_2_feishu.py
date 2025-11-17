import faulthandler
import logging
import os
from datetime import datetime

from crewai.telemetry import Telemetry
from dotenv import load_dotenv

from feishu.feishu import file_upload, create_file
from feishu.feishu_webhook import send_feishu_message
from utils import process_paper, sanitize_file_name

ERROR_CONTENT = '无法解码的Base64内容'

os.environ["OTEL_SDK_DISABLED"] = "true"
faulthandler.enable()


def noop(*args, **kwargs):
    print("Telemetry method called and noop'd\n")
    pass


for attr in dir(Telemetry):
    if callable(getattr(Telemetry, attr)) and not attr.startswith("__"):
        setattr(Telemetry, attr, noop)

os.environ['CREWAI_TELEMETRY_OPT_OUT'] = 'FALSE'
# Load environment variables
load_dotenv()

# 创建logs目录
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 生成日志文件名（按日期）
now = datetime.now()
log_filename = now.strftime("%Y%m%d") + "_paper_processing.log"
log_filepath = os.path.join(log_dir, log_filename)

# Set up logging - 同时输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filepath, encoding='utf-8'),  # 文件输出
        logging.StreamHandler()  # 控制台输出
    ]
)

# 创建专门的错误日志记录器
error_log_filename = now.strftime("%Y%m%d") + "_errors.log"
error_log_filepath = os.path.join(log_dir, error_log_filename)

error_logger = logging.getLogger('error_logger')
error_handler = logging.FileHandler(error_log_filepath, encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.ERROR)

# 其余代码保持不变...
IMAP_SERVER = 'imap.qq.com'
EMAIL_ACCOUNT = '105150326@qq.com'
PASSWORD = 'smoevzzqpdmkcadd'

FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
FIRECRAWL_API_URL = 'http://140.143.139.183:3002/v1'

SENDER_EMAIL = 'openRxiv-mailer@alerts.highwire.org'
DAYS_RECENT = 7

os.environ['CREWAI_DISABLE_TELEMETRY'] = 'true'


def process_size(str):
    now = datetime.now()
    now_str = now.strftime("%Y%m%d")
    with open(f"{now_str}_size.txt", 'w', encoding='utf-8') as f:
        f.write(f"{str}\n")


def parse_directory_for_pdfs(directory_path):
    """
    解析指定目录，获取其中的文件夹以及对应文件夹下的所有PDF文件
    """
    result = []

    try:
        if not os.path.exists(directory_path):
            logging.error(f"目录不存在: {directory_path}")
            return result

        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)

            if os.path.isdir(item_path):
                folder_info = {
                    "目录名称": item,
                    "files": []
                }

                try:
                    for file in os.listdir(item_path):
                        file_path = os.path.join(item_path, file)

                        if os.path.isfile(file_path) and file.lower().endswith('.pdf'):
                            folder_info["files"].append({
                                "file_path": file_path,
                                "file_name": file
                            })

                    if folder_info["files"]:
                        result.append(folder_info)

                except PermissionError as e:
                    logging.error(f"无权限访问文件夹: {item_path}, 错误: {e}")
                    error_logger.error(f"权限错误 - 文件夹: {item_path}, 错误: {e}")
                    continue

    except Exception as e:
        logging.error(f"解析目录时出错: {e}")
        error_logger.error(f"目录解析异常 - 目录: {directory_path}, 错误: {e}")

    return result


def main(pdf_address):
    logging.info(f"开始处理PDF目录: {pdf_address}")

    email_subject = parse_directory_for_pdfs(pdf_address)
    logging.info(f"找到 {len(email_subject)} 个文件夹")
    print(email_subject)
    count = 0

    for item in email_subject:
        all_paper_files = item.get('files')
        if len(all_paper_files) == 0:
            continue

        subject = item.get('目录名称')
        subject_parts = subject.split('&&time&&')
        email_date = subject_parts[1].strip()
        email_date = sanitize_file_name(email_date)

        logging.info(f"开始处理主题: {subject}, 文件数量: {len(all_paper_files)}")

        file_token = create_file(subject_parts[0], email_date)
        send_feishu_message(
            f"开始执行主题为:{subject}的邮件,总共{len(all_paper_files)}条数据,获取到文件夹token:{file_token}")

        for file_item in all_paper_files:
            file_path = file_item.get('file_path')
            file_name = file_item.get('file_name')

            logging.info(f"处理文件: {file_path}")

            try:
                result = process_paper(file_path, is_local_file=True)
            except Exception as e:
                import traceback

                # 获取详细异常信息
                error_msg = str(e) or repr(e) or f"{type(e).__name__}异常"
                full_traceback = traceback.format_exc()

                # 发送飞书消息
                send_feishu_message(f"❌异常: 解析PDF文件失败\n文件: {file_path}\n错误: {error_msg}")

                # 记录到普通日志
                logging.error(f"Error processing PDF file: {file_path}: {error_msg}")

                # 记录到专门的错误日志
                error_logger.error("=" * 80)
                error_logger.error(f"PDF处理异常详情:")
                error_logger.error(f"文件路径: {file_path}")
                error_logger.error(f"文件名: {file_name}")
                error_logger.error(f"异常类型: {type(e).__name__}")
                error_logger.error(f"异常信息: {error_msg}")
                error_logger.error(f"完整堆栈跟踪:\n{full_traceback}")
                error_logger.error("=" * 80)

                continue

            if result:
                try:
                    output_file, formatted_output = result
                    md_file_name = file_name + ".md"
                    md_file_name = sanitize_file_name(md_file_name)

                    if not os.path.exists(md_file_name):
                        with open(md_file_name, 'w', encoding='utf-8') as f:
                            f.write(f"\n")

                    with open(md_file_name, 'a', encoding='utf-8') as f:
                        f.write(f"{formatted_output}\n\n")

                    logging.info(f"Processed and wrote result for PDF file: {file_path}")

                    if result:
                        file_upload(file_token, md_file_name)
                        os.remove(md_file_name)

                except Exception as e:
                    import traceback

                    error_msg = str(e) or repr(e) or f"{type(e).__name__}异常"
                    full_traceback = traceback.format_exc()

                    send_feishu_message(f"❌异常: 处理文件结果上传飞书失败\n文件: {file_path}\n错误: {error_msg}")

                    logging.error(f"Error uploading PDF file: {file_path}: {error_msg}")

                    # 记录到错误日志
                    error_logger.error("=" * 80)
                    error_logger.error(f"文件上传异常详情:")
                    error_logger.error(f"文件路径: {file_path}")
                    error_logger.error(f"处理结果: {result}")
                    error_logger.error(f"异常信息: {error_msg}")
                    error_logger.error(f"完整堆栈跟踪:\n{full_traceback}")
                    error_logger.error("=" * 80)
            else:
                warning_msg = f"Failed to process PDF file: {file_path} - 获取PDF内容失败"
                send_feishu_message(f"⚠️ 执行异常,获取PDF内容失败: {file_path}")
                logging.warning(warning_msg)
                error_logger.warning(warning_msg)

            count += 1
            progress_msg = f'all size: {len(all_paper_files)} ;current size: {count}'
            print(f'-----------{progress_msg}------------------')
            logging.info(f"进度: {progress_msg}")
            process_size(progress_msg)

        send_feishu_message(
            f"结束执行主题为:{subject}的邮件,总共{len(all_paper_files)}条数据,获取到文件夹token:{file_token}")
        logging.info(f"完成处理主题: {subject}")

    logging.info("All papers processed.")


if __name__ == "__main__":
    main("D:\\PycharmProjects\\paper-summarizer\\paper-summarizer\\crewai\\email_download\\20251117")
