"""
天蛙配置示例文件
复制此文件为 config.py 并填入你的配置
"""

# DashScope API Key
# 获取方式：https://dashscope.console.aliyun.com/
DASHSCOPE_API_KEY = "sk-your-api-key-here"

# 模型配置
LLM_MODEL = "qwen-max"  # 可选: qwen-max, qwen-plus, qwen-turbo

# 对话配置
MAX_HISTORY_ROUNDS = 5  # 历史对话轮数限制
ENABLE_STREAMING = False  # 是否启用流式输出

# 系统提示词（可自定义）
SYSTEM_PROMPT = (
    "你是天蛙（TianWa），一个友好、专业的AI助手。"
    "请用简洁、清晰的语言回答用户的问题。"
)

