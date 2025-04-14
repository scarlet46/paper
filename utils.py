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
        role="生物计算与数据科学文献领域分类专家",
        goal="""根据文献内容进行三个维度分类：
                【算法维度】根据文献用到的核心算法，进行三级分类：
                一级分类：给出传统机器学习/统计模型+规则设计 vs 深度学习/深度神经网络
                二级分类：给出算法类型，例如：回归/分类/聚类/其他传统算法/卷积神经网络CNN、循环神经网络RNN、生成对抗网络GAN、深度强化学习（DRL）、深度变分自编码器（VAE）、扩散模型（Diffusion Models）和Transformer大模型架构等
                三级分类：给出具体算法架构，例如：回归算法包括线性回归/回归树/岭回归（Ridge Regression）/Lasso回归等；分类算法包括逻辑回归/支持向量机（SVM）/决策树（Decision Tree）/随机森林（Random Forest）等；聚类算法包括仿射传播（Affinity Propagation）/K均值（K-Means）/层次聚类（Hierarchical Clustering）等；其他传统算法--贝叶斯网络（Bayesian Networks）或隐马尔可夫模型（HMM）等；卷积神经网络（CNN）包括ResNet/VGG等；循环神经网络（RNN）包括LSTM/GRU等；生成对抗网络（GAN）包括DCGAN/StyleGAN等；深度变分自编码器（VAE）包括cVAE等；扩散模型（Diffusion Models）包括Stable Diffusion/DiT等；深度强化学习（DRL）包括DQN/PPO等；Transformer大模型架构包括BERT/GPT系列，或者ViT/DiT系列等；多模态模型包括DALL-E/CLIP等
                【数据类型维度】据文献用到的数据类型，进行二级分类：
                一级分类：给出主要数据类型，例如：基因组数据/转录组数据/蛋白质组数据/代谢组数据/表观组数据/影像数据/临床数据/文本数据/多模态数据等
                二级分类：给出具体数据子类型，例如：
                    - 基因组数据：全基因组测序(WGS)/外显子组测序(WES)/靶向测序/SNP芯片等
                    - 转录组数据：批量RNA-seq/单细胞RNA-seq/空间转录组/微阵列等
                    - 蛋白质组数据：质谱(MS)/蛋白芯片/蛋白质结构数据等
                    - 表观组数据：ChIP-seq/ATAC-seq/Hi-C/甲基化测序等
                    - 影像数据：显微镜图像/医学影像(CT/MRI/超声等)/组织病理切片等
                    - 临床数据：电子健康记录(EHR)/患者报告结局(PRO)/生物标志物等
                    - 文本数据：医学文献/临床笔记/病历等
                    - 多模态数据：多组学整合/影像组学/临床组学等
                【关注维度】根据文献内容，将文章分为三类：
                第一类（重点关注）：同时满足以下所有条件的文章：
                    - 预测各种干扰后表达谱变化的研究
                    - 使用深度学习方法（如CNN、RNN、GAN、DRL、VAE、扩散模型、Transformer架构）
                    - 处理关键数据类型（基因组、转录组、表观组、蛋白质组或多模态数据）的研究
                    - 研究对象为人类或小鼠 
                第二类（一般关注）：满足以下条件之一的文章：
                    - 单细胞算法开发（包括工具开发、单细胞多组学分析，多组学整合等）
                    - 基于深度学习和大模型框架的数据处理
                    - 实验数据挖掘研究
                    - 基因调控网络数学建模/计算模拟/网络分析
                    - 生物物理建模研究
                    - 跨领域研究（如同时涉及结构预测和表达谱分析）
                    - 使用传统机器学习方法但研究对象为人类或小鼠的表达谱分析
                    - 不属于第一类或第三类的文章
                第三类（无需关注）：满足以下条件之一的文章：
                    - 植物相关研究
                    - 蛋白质/小分子结构预测研究
                    - 研究对象不是人类或小鼠的文章
                【应用领域分类】对于第一类和第二类文章，进一步按应用领域分类：
                    - 癌症研究
                    - 衰老相关
                    - 免疫学
                    - 神经科学
                    - 发育生物学
                    - 代谢疾病
                    - 传染病
                    - 药物研发
                    - 其他应用领域""",
        backstory="""作为生物计算与数据科学领域的资深专家，你拥有计算生物学和生物信息学双博士学位，
                  精通从传统统计模型到前沿深度学习的算法谱系，能够准确识别文献中的算法创新点和技术路线。
                  你熟悉各类生物医学数据的特征、产生方式和分析流程，包括高通量测序数据、蛋白质组学数据、医学影像和临床记录等。
                  你曾参与多个跨学科项目，涵盖单细胞多组学分析、蛋白质结构预测、药物设计和精准医疗等前沿领域，
                  你对不同数据类型与算法的最佳匹配组合有深入理解。
                  你能从方法章节的技术描述中提取关键信息，区分相似算法间的细微差别，如传统随机森林与深度森林、常规SVM与深度核机器等易混淆的方法。
                  你还擅长识别生物医学领域特有的数据处理技术，如单细胞数据的批次效应校正、多组学数据整合方法等专业技术细节。""",
        allow_delegation=False,
        verbose=True,
        llm=llm,
    )


def create_paper_type_task(content):
    content = truncate_content(content)
     # 截断内容
    return Task(
        description=(
            "结构化分类结果（JSON格式）：\n"
            "{\n"
            '  "算法维度": {\n'
            '    "一级分类": "深度学习/传统机器学习",\n'
            '    "二级分类": "算法类型",\n'
            '    "三级分类": "具体架构"\n'
            "  },\n"
            '  "数据维度": {\n'
            '    "一级分类": "主要数据类型",\n'
            '    "二级分类": "数据子类型"\n'
            "  },\n"
            '  "关注级别": "第一类/第二类/第三类",\n'
            '  "应用领域": ["领域1", "领域2"]\n'
            "}\n\n"
            "示例：\n"
            "{\n"
            '  "算法维度": {\n'
            '    "一级分类": "深度学习",\n'
            '    "二级分类": "Transformer架构",\n'
            '    "三级分类": "BERT系列"\n'
            "  },\n"
            '  "数据维度": {\n'
            '    "一级分类": "转录组数据",\n'
            '    "二级分类": "单细胞RNA-seq"\n'
            "  },\n"
            '  "关注级别": "第一类",\n'
            '  "应用领域": ["癌症研究", "免疫学"]\n'
            "}"
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
            f"请按以下维度进行文献分类：\n"
            f"1. 算法维度：传统机器学习/深度学习 -> 算法类型 -> 具体架构\n"
            f"2. 数据维度：主要数据类型 -> 数据子类型\n"
            f"3. 关注级别：第一类（重点关注）/第二类（一般关注）/第三类（无需关注）\n"
            f"4. 应用领域：癌症研究/衰老相关/免疫学等\n\n"
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
            "### 文献分类结果\n"
            "**算法维度**  \n"
            "- 一级分类：传统机器学习 | 深度学习  \n"
            "- 二级分类：算法类型（如CNN/RNN/回归/分类）  \n"
            "- 三级分类：具体架构（如ResNet/BERT）\n\n"
            "**数据维度**  \n"
            "- 一级分类：基因组 | 转录组 | 蛋白质组等  \n"
            "- 二级分类：数据子类型（如单细胞RNA-seq）\n\n"
            "**关注级别**  \n"
            "- 第一类（深度学习+关键数据） | 第二类（传统方法+一般数据） | 第三类\n\n"
            "**应用领域**  \n"
            "- 癌症研究 | 衰老相关 | 免疫学 | 神经科学...\n\n"
            "研究内容补充 研究背景 关键技术 额外实验结果"
            "扩展应用"
            "结论"
            "总结"
        )
    )


def process_agent():
    return Agent(
        role="生物计算与数据科学文献翻译和整理总结专家",
        goal="读取并整理PDF文件内容，将其翻译成中文，并总结主要内容，重点包括标题、关键词、研究问题、方法、使用的数据类型（包括多组学数据，如基因组、转录组、蛋白质组、代谢组、表观组等）、创新点和结论。",
        backstory="你是一名资深的生物计算与数据科学领域的文献处理专家，你专注于微观生物学与人工智能的交叉领域研究。精通微观生物学，生物信息学、计算生物学和统计学领域的专业术语，能够高效地清理、翻译和总结学术论文，并确保技术术语的准确性和学术严谨性。你擅长处理单细胞多组学（转录组/表观组/蛋白组）数据整合分析，基因和药物筛选数据解析，生物分子动力学模拟和基因调控网络（GRN）分析等领域的复杂文献。熟悉Transformer架构，自回归模型和扩散模型等AI for Science领域的最新进展。你能将技术细节转化为易于理解的中文表述。你拥有5年以上Nature/Science/Cell和其子刊论文，以及bioRxiv预印本平台的核心论文的翻译经验，熟悉生物医学数据预处理、知识图谱构建，多组学整合分析和机器学习模型构建等技术的中文表达。",
        allow_delegation=False,
        verbose=True,
        llm=llm
    )


def process_paper(url):
    # markdown_content = firecrawl_crawl(url)
    markdown_content = process_pdf(url)
    logging.info(f"Processing paper markdown_content: {markdown_content}")
    if markdown_content is not None and markdown_content.strip():
        # 内容处理
        process_crew = Crew(
            agents=[process_agent()],
            tasks=[create_process_task(markdown_content, url)],
            verbose=True
        )
        processed_content = process_crew.kickoff().raw

        # 分类处理
        classify_crew = Crew(
            agents=[paper_type_agent()],
            tasks=[create_paper_type_task(processed_content)],
            verbose=True
        )
        classification = classify_crew.kickoff().raw

        try:
            # 解析分类结果
            class_dict = json.loads(classification)
            if class_dict.get("关注级别") == "第三类":
                logging.info(f"无需关注的文章，URL: {url}")
                return None

            # 生成文件名
            now_str = datetime.now().strftime("%Y%m%d")
            prefix = "重点_" if class_dict["关注级别"] == "第一类" else "一般_"
            output_file = f"{now_str}{prefix}{hash(url)}.md"

            # 整合分类结果到最终输出
            final_output = f"## 文献分类\n{json.dumps(class_dict, indent=2, ensure_ascii=False)}\n\n{processed_content}\n\n## 原文链接\n{url}"

            return output_file, final_output

        except json.JSONDecodeError:
            # 兼容旧版文本分类结果
            if "第三类" in classification or "忽略" in classification:
                logging.info(f"Ignoring paper from URL: {url}")
                return None
            # 其他情况继续处理
            return f"error_{hash(url)}.md", processed_content
        # # 添加类型判断
        # crew = Crew(
        #     agents=[process_agent()],
        #     tasks=[create_process_task(markdown_content, url)],
        #     share_crew=False,
        #     verbose=True
        # )
        #
        # result = crew.kickoff().raw
        #
        # # 判断类型
        # paper_type_crew = Crew(
        #     agents=[paper_type_agent()],
        #     tasks=[create_paper_type_task(result)],
        #     share_crew=False,
        #     verbose=True
        # )
        # paper_type = paper_type_crew.kickoff().raw
        # logging.info(f"Paper type: {paper_type}")
        # print(f"Paper type: {paper_type}")
        # if "忽略" in paper_type:
        #     logging.info(f"Ignoring paper from URL: {url}")
        #     print(f"Ignoring paper from URL: {url}")
        #     return None
        #
        # # 根据类型设置文件名称
        # now = datetime.now()
        # now_str = now.strftime("%Y%m%d")
        # output_file = f"{now_str}_"
        # # Format the final output
        # formatted_output = f"""{result} \n\n## 原文链接\n{url} \n\n"""
        # return output_file, formatted_output
    return None


import re
import os


def sanitize_file_name(name, max_length=200):
    """
    清理文件名，替换非法字符和空格，限制最大长度，同时保留文件扩展名。

    :param name: 原始文件名
    :param max_length: 文件名最大长度
    :return: 清理后的文件名
    """
    # 分离文件名和扩展名
    base_name, ext = os.path.splitext(name)

    # 替换非法字符和空格为下划线
    sanitized_base = re.sub(r'[\/\\\:\*\?\"\<\>\|\s]', '_', base_name)
    sanitized_base = sanitized_base.strip('_')  # 去掉首尾多余的下划线

    # 计算允许的文件名主体长度（减去扩展名长度）
    max_base_length = max_length - len(ext)

    # 截断文件名主体部分
    if len(sanitized_base) > max_base_length:
        sanitized_base = sanitized_base[:max_base_length]

    # 拼接截断后的文件名和扩展名
    sanitized_name = sanitized_base + ext
    return sanitized_name

