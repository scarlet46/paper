from pdf_server import process_pdf

try:
    print(
        process_pdf("https://www.biorxiv.org/content/10.1101/2023.11.27.568912v1.full.pdf"))
except Exception as e:
    print("第一次解析失败")

try:
    print(
        process_pdf("https://www.biorxiv.org/cgi/reprint/2023.11.27.568912v2??collection"))
except Exception as e:
    print("第二次解析失败")
