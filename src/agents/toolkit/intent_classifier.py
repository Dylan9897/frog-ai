# encoding : utf-8 -*-
# @author  : 冬瓜
# @mail    : dylan_han@126.com
# @Time    : 2025/11/19 16:31
"""
意图分类器
使用大模型判断用户指令属于：打开文件、打开软件、发送微信消息、闲聊、其他
"""

import dashscope
from dashscope import Generation


def classify_user_intent(user_text: str, api_key: str = None, model: str = 'qwen-turbo') -> str:
    """
    使用大模型对用户指令进行分类

    Args:
        user_text: 用户输入的指令文本
        api_key: DashScope API Key
        model: 使用的模型名称，默认 qwen-turbo

    Returns:
        分类结果: '打开文件' | '打开软件' | '发送微信消息' | '闲聊' | '其他'
    """
    if not user_text or not user_text.strip():
        return '其他'

    # 设置API Key
    if api_key:
        dashscope.api_key = api_key

    # === 第一阶段：主分类 ===
    system_prompt = """你是一个意图分类助手。请将用户的指令精确分类为以下四类之一：
1. 打开文件 - 用户想要查找或打开文档、表格、PDF、图片、视频等文件，或打开网页链接
2. 打开软件 - 用户想要启动/运行某个应用程序或软件
3. 发送微信消息 - 用户想要通过微信发送消息给某人，例如"微信通知张三"、"给李四发微信"等
4. 其他 - 其他类型的指令或问题

请仅输出分类结果，不要包含任何解释或多余内容。"""

    user_prompt = f"请对以下用户指令进行分类：\n\n{user_text}"

    try:
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]

        response = Generation.call(
            model=model,
            messages=messages,
            result_format='message',
            temperature=0.1,
            max_tokens=50
        )

        if response.status_code == 200:
            result = response.output.choices[0].message.content.strip()

            # 解析主分类结果
            if '打开文件' in result:
                return '打开文件'
            elif '打开软件' in result:
                return '打开软件'
            elif '发送微信消息' in result or '微信消息' in result:
                return '发送微信消息'
            elif '其他' in result:
                # === 第二阶段：闲聊 vs 其他 ===
                return _classify_chitchat_or_other(user_text, model)
            else:
                # 安全兜底：不确定时也走二分类
                return _classify_chitchat_or_other(user_text, model)
        else:
            print(f"[意图分类] 模型调用失败: {response.status_code} - {response.message}")
            return '其他'

    except Exception as e:
        print(f"[意图分类] 异常: {str(e)}")
        return '其他'


def _classify_chitchat_or_other(user_text: str, model: str = 'qwen-turbo') -> str:
    """
    二分类：判断“其他”类意图是否属于闲聊（需调用知识库）

    Returns:
        '闲聊' 或 '其他'
    """
    system_prompt = """你是一个语义判断助手。请判断用户的输入是否属于闲聊、问候、情感表达或常识性问答（例如“你好吗？”、“今天天气怎么样？”、“讲个笑话”等）。
- 如果是，请输出：闲聊
- 如果是具体任务、查询、指令、问题求解（即使模糊），请输出：其他

仅输出“闲聊”或“其他”，不要任何解释。"""

    user_prompt = f"用户输入：{user_text}"

    try:
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]

        response = Generation.call(
            model=model,
            messages=messages,
            result_format='message',
            temperature=0.1,
            max_tokens=20  # 更短输出
        )

        if response.status_code == 200:
            result = response.output.choices[0].message.content.strip()
            if '闲聊' in result:
                return '闲聊'
            else:
                return '其他'
        else:
            print(f"[闲聊二分类] 模型调用失败: {response.status_code} - {response.message}")
            return '其他'

    except Exception as e:
        print(f"[闲聊二分类] 异常: {str(e)}")
        return '其他'


# === 辅助函数更新 ===
def is_open_file_intent(user_text: str, api_key: str = None) -> bool:
    return classify_user_intent(user_text, api_key) == '打开文件'


def is_open_software_intent(user_text: str, api_key: str = None) -> bool:
    return classify_user_intent(user_text, api_key) == '打开软件'


def is_chitchat_intent(user_text: str, api_key: str = None) -> bool:
    """判断是否为闲聊意图（可用于决定是否调用知识库）"""
    return classify_user_intent(user_text, api_key) == '闲聊'