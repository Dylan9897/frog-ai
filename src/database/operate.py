# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2025/11/20 16:20

import os
import sys
import threading
from typing import Optional, Tuple
from .sql_manager import SandboxDatabase

# 尝试导入 dashscope（用于生成摘要和关键词）
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    print("[DB] Warning: dashscope not available, model summary generation will be disabled")

# 数据库实例（单例模式）
_db_instance = None

def get_database_instance(db_path: str = None):
    """获取数据库实例（单例模式）"""
    global _db_instance
    if _db_instance is None:
        if db_path is None:
            # 默认数据库路径：在 database 目录下
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, "sandbox.db")
        _db_instance = SandboxDatabase(db_path)
    return _db_instance


def get_file_type(file_path: str) -> str:
    """
    根据文件扩展名识别文件类型
    :param file_path: 文件路径
    :return: 文件类型字符串
    """
    if os.path.isdir(file_path):
        return "FOLDER"
    
    ext = os.path.splitext(file_path)[1].lower()
    
    file_type_map = {
        '.pdf': 'PDF',
        '.xlsx': 'EXCEL',
        '.xls': 'EXCEL',
        '.docx': 'WORD',
        '.doc': 'WORD',
        '.pptx': 'PPT',
        '.ppt': 'PPT',
        '.json': 'JSON',
        '.lnk': 'SHORTCUT',  # Windows 快捷方式
        '.txt': 'TEXT',
        '.csv': 'CSV',
        '.jpg': 'IMAGE',
        '.jpeg': 'IMAGE',
        '.png': 'IMAGE',
        '.gif': 'IMAGE',
        '.bmp': 'IMAGE',
        '.mp4': 'VIDEO',
        '.avi': 'VIDEO',
        '.mov': 'VIDEO',
        '.mp3': 'AUDIO',
        '.wav': 'AUDIO',
    }
    
    return file_type_map.get(ext, 'UNKNOWN')


def generate_file_summary_and_keywords(file_path: str, file_title: str, file_type: str, 
                                       api_key: Optional[str] = None, 
                                       model: str = 'qwen-turbo') -> Tuple[Optional[str], Optional[str]]:
    """
    使用大模型为文件生成模型摘要索引和关键词
    
    :param file_path: 文件路径
    :param file_title: 文件标题
    :param file_type: 文件类型
    :param api_key: DashScope API Key（可选，会尝试从环境变量获取）
    :param model: 使用的模型名称，默认 qwen-turbo
    :return: (model_summary_index, keywords) 元组
    """
    if not DASHSCOPE_AVAILABLE:
        print("[DB] Warning: dashscope not available, skipping summary generation")
        return None, None
    
    # 尝试获取 API Key
    if not api_key:
        api_key = os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            # 尝试从配置文件加载
            try:
                from src.config.config import DASHSCOPE_API_KEY as CFG_API_KEY
                api_key = CFG_API_KEY
            except Exception:
                pass
    
    if not api_key:
        print("[DB] Warning: No API key available, skipping summary generation")
        return None, None
    
    # 设置 API Key
    dashscope.api_key = api_key
    
    # 构建提示词
    system_prompt = """你是一个文件摘要助手。请根据文件信息生成：
1. 模型摘要索引（model_summary_index）：一个简洁的、用于检索的摘要描述（20-50字），描述文件的主要内容和用途
2. 关键词（keywords）：3-8个关键词，用逗号分隔，用于文件检索和匹配

请严格按照以下格式输出，不要包含任何其他内容：
模型摘要索引：<摘要内容>
关键词：<关键词1,关键词2,关键词3>"""
    
    user_prompt = f"""文件信息：
- 文件标题：{file_title}
- 文件类型：{file_type}
- 文件路径：{file_path}

请生成模型摘要索引和关键词。"""
    
    try:
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        
        response = Generation.call(
            model=model,
            messages=messages,
            result_format='message',
            temperature=0.3,
            max_tokens=200
        )
        
        if response.status_code == 200:
            result = response.output.choices[0].message.content.strip()
            
            # 解析结果
            model_summary_index = None
            keywords = None
            
            lines = result.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('模型摘要索引：') or line.startswith('模型摘要索引:'):
                    model_summary_index = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                elif line.startswith('关键词：') or line.startswith('关键词:'):
                    keywords = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            
            if model_summary_index and keywords:
                print(f"[DB] 成功生成摘要和关键词: {file_title}")
                return model_summary_index, keywords
            else:
                print(f"[DB] Warning: 解析摘要结果失败: {result}")
                return None, None
        else:
            print(f"[DB] Warning: 生成摘要失败: {response.status_code} - {response.message}")
            return None, None
            
    except Exception as e:
        print(f"[DB] Warning: 生成摘要异常: {str(e)}")
        return None, None


def manager_database(action: str, **kwargs):
    """
    数据库管理统一接口
    
    :param action: 操作类型，可选值：
        - 'add': 添加文件到数据库
        - 'delete': 从数据库删除文件
        - 'update': 更新数据库记录
        - 'get': 查询数据库记录
    
    :param kwargs: 其他参数
        对于 'add' 操作：
            - sessionId: 会话ID（必需）
            - file_path: 原始文件路径（必需）
            - shortcut_path: 快捷方式路径（必需）
            - file_type: 文件类型（可选，会自动识别）
            - file_title: 文件标题（可选）
            - summary_content: 摘要内容（可选）
            - model_summary_index: 模型摘要索引（可选）
            - keywords: 关键词（可选）
            - db_path: 数据库路径（可选）
        
        对于 'delete' 操作：
            - shortcut_path: 快捷方式路径（必需）
            - db_path: 数据库路径（可选）
        
        对于 'update' 操作：
            - shortcut_path: 快捷方式路径（可选，与 sessionId 二选一）
            - sessionId: 会话ID（可选，与 shortcut_path 二选一）
            - db_path: 数据库路径（可选）
            - 其他字段：file_path, file_type, file_title, summary_content, model_summary_index, keywords
        
        对于 'get' 操作：
            - shortcut_path: 快捷方式路径（必需）
            - db_path: 数据库路径（可选）
    
    :return: 操作结果
    """
    db_path = kwargs.pop('db_path', None)
    db = get_database_instance(db_path)
    
    if action == 'add':
        # 添加文件到数据库
        sessionId = kwargs.get('sessionId')
        file_path = kwargs.get('file_path')
        shortcut_path = kwargs.get('shortcut_path')
        
        if not all([sessionId, file_path, shortcut_path]):
            print("[DB] Error: sessionId, file_path, and shortcut_path are required for 'add' action")
            return False
        
        # 自动识别文件类型（如果未提供）
        if 'file_type' not in kwargs or kwargs['file_type'] is None:
            kwargs['file_type'] = get_file_type(file_path)
        
        # 如果没有提供 file_title，使用文件名
        if 'file_title' not in kwargs or kwargs['file_title'] is None:
            kwargs['file_title'] = os.path.basename(file_path)
        
        # 检查是否需要异步生成摘要和关键词
        need_generate_summary = ('model_summary_index' not in kwargs or kwargs['model_summary_index'] is None) or \
                                ('keywords' not in kwargs or kwargs['keywords'] is None)
        
        # 保存用于后台生成的参数
        api_key = kwargs.pop('api_key', None)  # 从 kwargs 中获取 api_key（如果提供）
        model = kwargs.pop('model', 'qwen-turbo')  # 从 kwargs 中获取 model（如果提供）
        
        # 立即插入数据库（不等待摘要生成）
        try:
            db.insert_by_shortcut(
                sessionId=sessionId,
                file_path=file_path,
                shortcut_path=shortcut_path,
                file_type=kwargs.get('file_type'),
                file_title=kwargs.get('file_title'),
                summary_content=kwargs.get('summary_content'),
                model_summary_index=kwargs.get('model_summary_index'),
                keywords=kwargs.get('keywords')
            )
            print(f"[DB] 文件已插入数据库: {kwargs.get('file_title')}")
            
            # 如果需要生成摘要和关键词，在后台异步执行
            if need_generate_summary:
                def background_update_summary():
                    """后台任务：生成摘要和关键词并更新数据库"""
                    try:
                        print(f"[DB] 开始后台生成摘要和关键词: {kwargs.get('file_title')}")
                        generated_summary, generated_keywords = generate_file_summary_and_keywords(
                            file_path=file_path,
                            file_title=kwargs.get('file_title'),
                            file_type=kwargs.get('file_type'),
                            api_key=api_key,
                            model=model
                        )
                        
                        # 更新数据库
                        if generated_summary or generated_keywords:
                            update_kwargs = {}
                            if generated_summary:
                                update_kwargs['model_summary_index'] = generated_summary
                            if generated_keywords:
                                update_kwargs['keywords'] = generated_keywords
                            
                            if update_kwargs:
                                db.update_record(shortcut_path=shortcut_path, **update_kwargs)
                                print(f"[DB] 后台更新摘要和关键词完成: {kwargs.get('file_title')}")
                        else:
                            print(f"[DB] 后台生成摘要和关键词失败: {kwargs.get('file_title')}")
                    except Exception as e:
                        print(f"[DB] 后台更新摘要异常: {str(e)}")
                
                # 启动后台线程
                thread = threading.Thread(target=background_update_summary, daemon=True)
                thread.start()
                print(f"[DB] 已启动后台任务生成摘要和关键词: {kwargs.get('file_title')}")
            
            return True
        except Exception as e:
            print(f"[DB] Add operation failed: {e}")
            return False
    
    elif action == 'delete':
        # 从数据库删除文件
        shortcut_path = kwargs.get('shortcut_path')
        if not shortcut_path:
            print("[DB] Error: shortcut_path is required for 'delete' action")
            return False
        
        try:
            db.delete_by_shortcut(shortcut_path)
            return True
        except Exception as e:
            print(f"[DB] Delete operation failed: {e}")
            return False
    
    elif action == 'update':
        # 更新数据库记录
        shortcut_path = kwargs.get('shortcut_path')
        sessionId = kwargs.get('sessionId')
        
        if not shortcut_path and not sessionId:
            print("[DB] Error: shortcut_path or sessionId is required for 'update' action")
            return False
        
        # 移除 action 和 db_path，保留其他更新字段
        update_kwargs = {k: v for k, v in kwargs.items() 
                        if k not in ['action', 'db_path', 'shortcut_path', 'sessionId']}
        
        try:
            db.update_record(shortcut_path=shortcut_path, sessionId=sessionId, **update_kwargs)
            return True
        except Exception as e:
            print(f"[DB] Update operation failed: {e}")
            return False
    
    elif action == 'get':
        # 查询数据库记录
        shortcut_path = kwargs.get('shortcut_path')
        if not shortcut_path:
            print("[DB] Error: shortcut_path is required for 'get' action")
            return None
        
        try:
            return db.get_record_by_shortcut(shortcut_path)
        except Exception as e:
            print(f"[DB] Get operation failed: {e}")
            return None
    
    else:
        print(f"[DB] Error: Unknown action '{action}'. Supported actions: 'add', 'delete', 'update', 'get'")
        return False
