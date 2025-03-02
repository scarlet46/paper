import logging
from datetime import datetime

from crewai import Crew, Agent, LLM, Task

from pdf_server import process_pdf

# 设置 Ollama API 环境变量
# Model = "gpt-4o-mini"
# os.environ["OPENAI_API_KEY"] = "sk-tA4X88vrZDn2RV5GDe54Ec3743744d7eBaB8F8Ae8a73F1Cf"
# llm = LLM(model=Model, base_url="https://api.fast-tunnel.one/v1",
#           api_key="sk-tA4X88vrZDn2RV5GDe54Ec3743744d7eBaB8F8Ae8a73F1Cf")

# Model = "deepseek-chat"
# llm = LLM(model=Model, base_url="https://api.deepseek.com/v1",
#           api_key="sk-5346b4837c81477592d7503a3de034ec")
# os.environ["OPENAI_API_KEY"] = "sk-tA4X88vrZDn2RV5GDe54Ec3743744d7eBaB8F8Ae8a73F1Cf"

Model = "volcengine/deepseek-v3-241226"
llm = LLM(
    model=Model,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="74cfeb2a-831e-477d-91cd-9d60fd18405d"
)


def truncate_content(content, max_length=65500):
    """
    截断内容至最大允许长度。

    :param content: 输入内容 (str)
    :param max_length: 最大允许长度 (int)，默认为 65500
    :return: 截断后的内容 (str)
    """
    if len(content) > max_length:
        print(f"输入内容长度为 {len(content)}，超过最大长度 {max_length}，将进行截断。")
        content = content[:max_length]
    return content


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
    content = truncate_content(content)
     # 截断内容
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


def create_process_task(markdown_content, url):
    markdown_content = truncate_content(markdown_content)
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


def process_agent():
    return Agent(
        role="学术内容处理专家",
        goal="清理网页内容，将其翻译成中文，并总结主要内容，重点包括标题、关键词、研究问题、方法、创新点和结论。",
        backstory="你是一名专业的学术内容处理专家，能够高效地清理、翻译和总结学术论文，确保技术术语的准确性和学术严谨性。",
        allow_delegation=False,
        verbose=True,
        llm=llm
    )


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
        if "忽略" in paper_type:
            logging.info(f"Ignoring paper from URL: {url}")
            print(f"Ignoring paper from URL: {url}")
            return None

        # 根据类型设置文件名称
        now = datetime.now()
        now_str = now.strftime("%Y%m%d")
        output_file = f"{now_str}_"
        # Format the final output
        formatted_output = f"""{result} \n\n## 原文链接\n{url} \n\n"""
        return output_file, formatted_output
    return None


import re


def sanitize_file_name(name, max_length=100):
    """
    清理文件名，替换非法字符和空格，限制最大长度。

    :param name: 原始文件名
    :param max_length: 文件名最大长度
    :return: 清理后的文件名
    """
    # 替换非法字符和空格为下划线
    sanitized = re.sub(r'[\/\\\:\*\?\"\<\>\|\s]', '_', name)
    # 去掉首尾多余的下划线
    sanitized = sanitized.strip('_')
    # 限制文件名长度
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized
