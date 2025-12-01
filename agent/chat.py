"""
大模型对话服务
基于 DashScope API 实现 LLM 对话
"""
import os
import dashscope
from typing import Optional
from dashscope import Generation
from dashscope.api_entities.dashscope_response import Role


def _load_dashscope_api_key() -> Optional[str]:
    """按优先级加载 DashScope API Key。

    优先级：
    1) 环境变量 DASHSCOPE_API_KEY
    2) agent/config.py 中的 DASHSCOPE_API_KEY
    3) 环境变量 DASHSCOPE_API_KEY_FILE_PATH 指向的文件
    4) 默认文件路径 ~/.dashscope/api_key
    """
    # 1. 环境变量
    env_key = os.environ.get('DASHSCOPE_API_KEY')
    if env_key:
        return env_key.strip()

    # 2. 配置文件
    try:
        from agent.config import DASHSCOPE_API_KEY
        if DASHSCOPE_API_KEY:
            return str(DASHSCOPE_API_KEY).strip()
    except (ImportError, AttributeError):
        pass

    # 3. 指定文件路径
    key_file_path = os.environ.get('DASHSCOPE_API_KEY_FILE_PATH')
    if key_file_path and os.path.exists(key_file_path):
        try:
            with open(key_file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass

    # 4. 默认文件路径
    default_path = os.path.expanduser('~/.dashscope/api_key')
    if os.path.exists(default_path):
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass

    return None


# 配置（可从 agent/config.py 或环境变量读取）
try:
    from agent.config import LLM_MODEL as CFG_LLM_MODEL, MAX_HISTORY_ROUNDS as CFG_MAX_HISTORY_ROUNDS
    LLM_MODEL = os.environ.get('LLM_MODEL', CFG_LLM_MODEL or 'qwen-max')
    MAX_HISTORY_ROUNDS = int(os.environ.get('MAX_HISTORY_ROUNDS', CFG_MAX_HISTORY_ROUNDS or '5'))
except (ImportError, AttributeError):
    LLM_MODEL = os.environ.get('LLM_MODEL', 'qwen-max')
    MAX_HISTORY_ROUNDS = int(os.environ.get('MAX_HISTORY_ROUNDS', '5'))

# 系统提示词
SYSTEM_PROMPT = (
    "你是蕉绿蛙轻语（TianWa QingYu），一个友好、专业的AI助手。你的职责是："
    "1. 回答用户的各种问题，提供有价值的信息和建议"
    "2. 保持友好、耐心、专业的态度"
    "3. 用简洁、清晰的语言与用户交流"
    "4. 当不确定答案时，诚实地告知用户"
    "\n所有回复必须使用纯文本格式，不得包含任何Markdown语法（如加粗、斜体、标题符号、列表符号、代码块等），"
    "不得使用星号、井号、反引号、中划线列表符等格式标记。所有内容应以自然、清晰的口语化中文呈现。"
)


class ChatService:
    """对话服务类"""
    
    def __init__(self, api_key=None):
        """初始化服务"""
        self.api_key = api_key or _load_dashscope_api_key()
        if self.api_key:
            dashscope.api_key = self.api_key
        
        # 初始化对话历史（每个会话独立）
        self.sessions = {}
    
    def create_session(self, session_id):
        """创建新会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'messages': [{'role': Role.SYSTEM, 'content': SYSTEM_PROMPT}],
                'created_at': None
            }
        return session_id
    
    def get_session(self, session_id):
        """获取会话"""
        if session_id not in self.sessions:
            self.create_session(session_id)
        return self.sessions[session_id]
    
    def clear_session(self, session_id):
        """清除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def chat(self, session_id, user_message, stream=False, has_attachments=False, file_context: str | None = None):
        """
        对话接口
        :param session_id: 会话ID
        :param user_message: 用户消息
        :param stream: 是否流式返回
        :param has_attachments: 是否有附件（文件）
        :return: 助手回复或生成器
        """
        # 关键配置检查
        if not self.api_key:
            return {
                'success': False,
                'error': (
                    '未检测到 DashScope API Key。请设置环境变量 DASHSCOPE_API_KEY，'
                    '或在 agent/config.py 中配置 DASHSCOPE_API_KEY，'
                    '也可在 ~/.dashscope/api_key 存放密钥，或通过 DASHSCOPE_API_KEY_FILE_PATH 指定文件路径。'
                )
            }

        # 如果有附件但没有可用的文件内容上下文，则统一认为功能尚未支持
        if has_attachments and not file_context:
            return {
                'success': True,
                'reply': (
                    '当前的文件问答功能仅支持以下几类文本/结构化文档：'
                    'docx、xlsx/xls、md、txt、json。\n'
                    '对于 PDF、图片等其他类型文件，相关能力正在开发中，请耐心等待。'
                ),
                'session_id': session_id
            }
        
        # 正常对话流程
        session = self.get_session(session_id)
        messages = session['messages']

        # 如果有文件上下文，作为额外 SYSTEM 信息注入，提示模型优先依据文档回答
        if file_context:
            doc_system_prompt = (
                "下面是用户上传的文档内容摘要或正文片段，请在回答本轮问题时，"
                "优先依据这些文档内容进行推理和引用；当文档中没有相关信息时，再结合通用知识回答。\n\n"
                f"{file_context}"
            )
            messages.append({'role': Role.SYSTEM, 'content': doc_system_prompt})
        
        # 添加用户消息
        messages.append({'role': Role.USER, 'content': user_message})
        
        # 限制历史对话轮数
        current_rounds = (len(messages) - 1) // 2
        if current_rounds > MAX_HISTORY_ROUNDS:
            excess_rounds = current_rounds - MAX_HISTORY_ROUNDS
            messages = [messages[0]] + messages[1 + excess_rounds * 2:]
            session['messages'] = messages
        
        try:
            if stream:
                # 流式返回
                return self._chat_stream(messages)
            else:
                # 一次性返回
                responses = Generation.call(
                    model=LLM_MODEL,
                    messages=messages,
                    result_format='message'
                )
                
                if responses.status_code == 200:
                    reply = responses.output.choices[0].message.content
                    # 添加助手回复到历史
                    messages.append({'role': Role.ASSISTANT, 'content': reply})
                    return {
                        'success': True,
                        'reply': reply,
                        'session_id': session_id
                    }
                else:
                    return {
                        'success': False,
                        'error': f'LLM Error: {responses.status_code} - {responses.message}'
                    }
        except Exception as e:
            return {
                'success': False,
                'error': f'Exception: {str(e)}'
            }
    
    def _chat_stream(self, messages):
        """流式对话生成器"""
        try:
            responses = Generation.call(
                model=LLM_MODEL,
                messages=messages,
                stream=True,
                result_format='message'
            )
            
            full_reply = ""
            last_full_text = ""
            
            for response in responses:
                if response.status_code == 200:
                    text_chunk = response.output.choices[0].message.content
                    if not text_chunk:
                        continue
                    
                    # 只发送新增的文本
                    if text_chunk.startswith(last_full_text):
                        new_text = text_chunk[len(last_full_text):]
                        if new_text:
                            yield new_text
                    else:
                        yield text_chunk
                    
                    last_full_text = text_chunk
                    full_reply = text_chunk
                else:
                    yield f'\n[Error] {response.status_code} - {response.message}\n'
                    break
            
            # 添加助手回复到历史
            if full_reply:
                messages.append({'role': Role.ASSISTANT, 'content': full_reply})
            
        except Exception as e:
            yield f'\n[Exception] {str(e)}\n'


# 全局服务实例
_chat_service = None


def get_chat_service():
    """获取全局对话服务实例"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

