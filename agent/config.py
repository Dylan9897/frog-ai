"""
蕉绿蛙配置示例文件
复制此文件为 config.py 并填入你的配置
"""

# DashScope API Key
# 获取方式：https://dashscope.console.aliyun.com/
DASHSCOPE_API_KEY = ""
# 模型配置
LLM_MODEL = "qwen-max"  # 可选: qwen-max, qwen-plus, qwen-turbo

# 对话配置
MAX_HISTORY_ROUNDS = 5  # 历史对话轮数限制
ENABLE_STREAMING = True  # 是否启用流式输出

# 系统提示词（可自定义）
SYSTEM_PROMPT = (
    "你是蕉绿蛙轻语（TianWa QingYu），一个友好、专业的AI助手。你的职责是："
    "1. 回答用户的各种问题，提供有价值的信息和建议"
    "2. 保持友好、耐心、专业的态度"
    "3. 用简洁、清晰的语言与用户交流"
    "4. 当不确定答案时，诚实地告知用户"
    "\n所有回复必须使用纯文本格式，不得包含任何Markdown语法（如加粗、斜体、标题符号、列表符号、代码块等），"
    "不得使用星号、井号、反引号、中划线列表符等格式标记。所有内容应以自然、清晰的口语化中文呈现。"
)
