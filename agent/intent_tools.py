"""
意图识别与智能打开文件工具

从 temp 工程中裁剪了意图分类与关键词抽取的核心逻辑，
简化后用于当前 Web 沙盒项目：
 - 基于 DashScope 识别意图（打开文件 / 闲聊 / 其他）
 - 从用户指令中抽取用于匹配沙盒文件名的关键词
 - 在 uploads 目录中寻找最匹配的文件并在本机打开
"""

from __future__ import annotations

import os
from typing import List, Dict, Any, Optional

import dashscope
from dashscope import Generation

from agent.chat import _load_dashscope_api_key, LLM_MODEL


def _ensure_api_key() -> Optional[str]:
    """确保 dashscope.api_key 已设置，返回当前使用的 key（可能为 None）。"""
    api_key = _load_dashscope_api_key()
    if api_key:
        dashscope.api_key = api_key
    return api_key


def classify_user_intent(user_text: str, model: str = "qwen-turbo") -> str:
    """
    使用大模型对用户指令进行粗分类。

    返回：
        '打开文件' | '打开软件' | '发送微信消息' | '闲聊' | '其他'
    """
    if not user_text or not user_text.strip():
        return "其他"

    _ensure_api_key()

    system_prompt = """你是一个意图分类助手。请将用户的指令精确分类为以下四类之一：
1. 打开文件 - 用户想要查找或打开文档、表格、PDF、图片、视频等文件，或打开网页链接
2. 打开软件 - 用户想要启动/运行某个应用程序或软件
3. 发送微信消息 - 用户想要通过微信发送消息给某人，例如"微信通知张三"、"给李四发微信"等
4. 其他 - 其他类型的指令或问题

请仅输出分类结果，不要包含任何解释或多余内容。"""

    user_prompt = f"请对以下用户指令进行分类：\n\n{user_text}"

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = Generation.call(
            model=model,
            messages=messages,
            result_format="message",
            temperature=0.1,
            max_tokens=50,
        )

        if response.status_code == 200:
            result = response.output.choices[0].message.content.strip()

            if "打开文件" in result:
                return "打开文件"
            elif "打开软件" in result:
                return "打开软件"
            elif "发送微信消息" in result or "微信消息" in result:
                return "发送微信消息"
            elif "其他" in result:
                return _classify_chitchat_or_other(user_text, model)
            else:
                # 安全兜底：不确定时也做二分类
                return _classify_chitchat_or_other(user_text, model)
        else:
            print(f"[意图分类] 模型调用失败: {response.status_code} - {response.message}")
            return "其他"

    except Exception as e:
        print(f"[意图分类] 异常: {str(e)}")
        return "其他"


def _classify_chitchat_or_other(user_text: str, model: str = "qwen-turbo") -> str:
    """
    二分类：判断“其他”类意图是否属于闲聊。

    返回：
        '闲聊' 或 '其他'
    """
    _ensure_api_key()

    system_prompt = """你是一个语义判断助手。请判断用户的输入是否属于闲聊、问候、情感表达或常识性问答（例如“你好吗？”、“今天天气怎么样？”、“讲个笑话”等）。
- 如果是，请输出：闲聊
- 如果是具体任务、查询、指令、问题求解（即使模糊），请输出：其他

仅输出“闲聊”或“其他”，不要任何解释。"""

    user_prompt = f"用户输入：{user_text}"

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = Generation.call(
            model=model,
            messages=messages,
            result_format="message",
            temperature=0.1,
            max_tokens=20,
        )

        if response.status_code == 200:
            result = response.output.choices[0].message.content.strip()
            return "闲聊" if "闲聊" in result else "其他"
        else:
            print(f"[闲聊二分类] 模型调用失败: {response.status_code} - {response.message}")
            return "其他"

    except Exception as e:
        print(f"[闲聊二分类] 异常: {str(e)}")
        return "其他"


def extract_keywords_with_llm(
    user_text: str,
    available_files: List[Dict[str, Any]],
    model: str = "qwen-turbo",
) -> List[str]:
    """
    使用大模型从用户输入中提取用于文件匹配的关键词。

    available_files: [{'file_title': '2021.xxx.pdf'}, ...]
    """
    api_key = _ensure_api_key()

    # 如果没有可用的 LLM，降级为简单分词过滤
    if not api_key:
        return _simple_keywords(user_text)

    # 构建可用文件列表的描述，帮助模型理解上下文
    file_list_text = "\n".join(
        [f"- {file.get('file_title', '未知文件')}" for file in available_files[:20]]
    )

    system_prompt = """你是一个关键词提取助手。用户想要打开某个文件，请从用户输入中提取用于匹配文件名的关键词。

要求：
1. 提取2-5个最相关的关键词，这些关键词应该能帮助识别用户想要打开的文件
2. 忽略常见的动词和停用词（如"打开"、"运行"、"文件"、"软件"等）
3. 关键词应该简洁、准确，能够匹配文件名中的关键信息
4. 如果用户提到了具体的文件名或文件名的一部分，优先提取这些信息

请仅输出关键词，用逗号分隔，不要包含任何解释或其他内容。"""

    user_prompt = f"""用户输入：{user_text}

可用文件列表：
{file_list_text}

请提取用于匹配文件名的关键词："""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = Generation.call(
            model=model,
            messages=messages,
            result_format="message",
            temperature=0.1,
            max_tokens=100,
        )

        if response.status_code == 200:
            result = response.output.choices[0].message.content.strip()
            # 解析关键词（去除可能的标点符号和多余空格）
            keywords = [
                kw.strip() for kw in result.replace("，", ",").split(",") if kw.strip()
            ]
            print(f"[智能体] 大模型提取的关键词: {keywords}")
            return keywords
        else:
            print(f"[智能体] 关键词提取失败: {response.status_code} - {response.message}")
            return _simple_keywords(user_text)

    except Exception as e:
        print(f"[智能体] 关键词提取异常: {str(e)}")
        return _simple_keywords(user_text)


def _simple_keywords(user_text: str) -> List[str]:
    """不依赖 LLM 的简单关键词提取回退策略。"""
    user_text_lower = user_text.lower()
    stop_words = ["打开", "运行", "启动", "找", "查找", "文件", "软件", "应用", "程序", "的", "了", "吗", "呢"]
    # 这里简单用空格切分，已经能覆盖“2021”、“acl”、“报告”等关键词
    return [
        word
        for word in user_text_lower.replace("，", " ").replace("。", " ").split()
        if word and word not in stop_words
    ]


def smart_open_file_from_text(
    user_text: str, uploads_dir: str
) -> Dict[str, Any]:
    """
    根据用户自然语言指令，在 uploads 目录中寻找最匹配的文件并尝试在本机打开。

    返回字典：
        {
            'intent': str,
            'opened': bool,
            'target_name': Optional[str],
            'target_path': Optional[str],
            'error': Optional[str]
        }
    """
    intent = classify_user_intent(user_text)

    if intent != "打开文件":
        return {
            "intent": intent,
            "opened": False,
            "target_name": None,
            "target_path": None,
            "error": "意图不是打开文件",
        }

    try:
        if not os.path.isdir(uploads_dir):
            return {
                "intent": intent,
                "opened": False,
                "target_name": None,
                "target_path": None,
                "error": f"uploads 目录不存在: {uploads_dir}",
            }

        filenames = [
            f for f in os.listdir(uploads_dir) if f and not f.startswith(".")
        ]
        if not filenames:
            return {
                "intent": intent,
                "opened": False,
                "target_name": None,
                "target_path": None,
                "error": "沙盒中还没有文件，请先上传文件。",
            }

        available_files = [
            {"file_title": name, "file_path": os.path.join(uploads_dir, name)}
            for name in filenames
        ]

        keywords = extract_keywords_with_llm(user_text, available_files)
        keyword_list = [kw.lower() for kw in keywords if kw.strip()]

        matching: List[tuple[int, Dict[str, Any]]] = []
        for record in available_files:
            title = record["file_title"].lower()
            if keyword_list:
                hit_count = sum(1 for kw in keyword_list if kw in title)
                if hit_count > 0:
                    matching.append((hit_count, record))
            else:
                # 关键词为空时，简单用用户原文拆分做匹配
                user_words = [
                    w
                    for w in user_text.lower().replace("，", " ").replace("。", " ").split()
                    if len(w) > 1
                ]
                if any(w in title for w in user_words):
                    matching.append((1, record))

        if not matching:
            return {
                "intent": intent,
                "opened": False,
                "target_name": None,
                "target_path": None,
                "error": "没有找到匹配的沙盒文件，请检查文件名是否与描述相符。",
            }

        # 选择命中关键词最多的记录
        matching.sort(key=lambda x: x[0], reverse=True)
        target = matching[0][1]
        target_path = os.path.abspath(target["file_path"])
        target_name = target["file_title"]

        if not os.path.exists(target_path):
            return {
                "intent": intent,
                "opened": False,
                "target_name": target_name,
                "target_path": target_path,
                "error": "目标文件不存在或已被移动。",
            }

        # 在本机尝试打开文件
        try:
            if os.name == "nt":
                os.startfile(target_path)
            elif sys.platform == "darwin":  # type: ignore[name-defined]
                os.system(f'open "{target_path}"')
            else:
                os.system(f'xdg-open "{target_path}"')
            opened = True
            error_msg = None
        except Exception as e:  # pragma: no cover - OS 相关难以单测
            print(f"[智能体] 打开文件失败: {e}")
            opened = False
            error_msg = f"尝试打开文件失败: {e}"

        return {
            "intent": intent,
            "opened": opened,
            "target_name": target_name,
            "target_path": target_path,
            "error": error_msg,
        }

    except Exception as e:
        print(f"[智能体] smart_open_file_from_text 异常: {e}")
        return {
            "intent": intent,
            "opened": False,
            "target_name": None,
            "target_path": None,
            "error": f"解析或打开文件时发生错误: {e}",
        }


