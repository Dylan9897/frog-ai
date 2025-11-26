# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2025/11/19 16:19
"""
智能体工作流
使用 LangGraph 编排打开文件/软件的完整流程
"""
import os
import sys
from typing import Dict, Any, Optional, List

from langgraph.graph import StateGraph, START, END
from src.agents.toolkit.intent_classifier import classify_user_intent, _classify_chitchat_or_other

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database.operate import get_database_instance

# 尝试导入 dashscope
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    print("[智能体] Warning: dashscope not available")


def extract_keywords_with_llm(user_text: str, available_files: List[Dict[str, Any]], 
                              api_key: str, model: str = 'qwen-turbo') -> List[str]:
    """
    使用大模型从用户输入中提取用于文件匹配的关键词
    
    Args:
        user_text: 用户输入的文本
        available_files: 可用的文件列表，每个文件包含 file_title 等信息
        api_key: DashScope API Key
        model: 使用的模型名称，默认 qwen-turbo
    
    Returns:
        提取的关键词列表
    """
    if not DASHSCOPE_AVAILABLE or not api_key:
        # 降级到简单匹配
        user_text_lower = user_text.lower()
        stop_words = ['打开', '运行', '启动', '找', '查找', '文件', '软件', '应用', '程序', '的', '了', '吗', '呢']
        keywords = [word for word in user_text_lower.split() 
                   if word not in stop_words and len(word) > 0]
        return keywords
    
    # 设置 API Key
    dashscope.api_key = api_key
    
    # 构建可用文件列表的描述
    file_list_text = "\n".join([f"- {file.get('file_title', '未知文件')}" 
                                for file in available_files[:20]])  # 限制前20个文件
    
    system_prompt = """你是一个关键词提取助手。用户想要打开某个文件，请从用户输入中提取用于匹配文件名的关键词。

要求：
1. 提取2-5个最相关的关键词，这些关键词应该能帮助识别用户想要打开的文件
2. 忽略常见的动词和停用词（如"打开"、"运行"、"文件"、"软件"等）
3. 关键词应该简洁、准确，能够匹配文件名中的关键信息
4. 如果用户提到了具体的文件名或文件名的一部分，优先提取这些信息

请仅输出关键词，用逗号分隔，不要包含任何解释或其他内容。
例如：如果用户说"打开我的项目文档"，应该输出：项目,文档
如果用户说"打开那个Excel表格"，应该输出：Excel,表格"""
    
    user_prompt = f"""用户输入：{user_text}

可用文件列表：
{file_list_text}

请提取用于匹配文件名的关键词："""
    
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
            max_tokens=100
        )
        
        if response.status_code == 200:
            result = response.output.choices[0].message.content.strip()
            # 解析关键词（去除可能的标点符号和多余空格）
            keywords = [kw.strip() for kw in result.replace('，', ',').split(',') if kw.strip()]
            print(f"[智能体] 大模型提取的关键词: {keywords}")
            return keywords
        else:
            print(f"[智能体] 关键词提取失败: {response.status_code} - {response.message}")
            # 降级到简单匹配
            user_text_lower = user_text.lower()
            stop_words = ['打开', '运行', '启动', '找', '查找', '文件', '软件', '应用', '程序', '的', '了', '吗', '呢']
            keywords = [word for word in user_text_lower.split() 
                       if word not in stop_words and len(word) > 0]
            return keywords
            
    except Exception as e:
        print(f"[智能体] 关键词提取异常: {str(e)}")
        # 降级到简单匹配
        user_text_lower = user_text.lower()
        stop_words = ['打开', '运行', '启动', '找', '查找', '文件', '软件', '应用', '程序', '的', '了', '吗', '呢']
        keywords = [word for word in user_text_lower.split() 
                   if word not in stop_words and len(word) > 0]
        return keywords


def build_smart_agent(api_key: str, config_path: str, model: str = 'qwen-turbo'):
    """
    构建智能体工作流

    Args:
        api_key: DashScope API Key
        config_path: 配置文件路径
        model: 使用的模型名称，默认 qwen-turbo

    Returns:
        编译后的 LangGraph 工作流
    """
    def state_classifier(state: Dict[str, Any]) -> Dict[str, Any]:
        """第1步：意图分类"""
        text = state.get('text', '')
        print(f"[智能体] 步骤1: 意图分类 - 用户输入: {text}")
        label = classify_user_intent(text, api_key, model)

        # 如果意图是 其他 ，则做二次判断是否为闲聊
        if label == "其他":
            label = _classify_chitchat_or_other(text)

        print(f"[智能体] 意图分类结果: {label}")
        return {**state, 'label': label}

    def state_resolve_target(state: Dict[str, Any]) -> Dict[str, Any]:
        """第2步：解析目标文件并打开"""
        text = state.get('text', '')
        label = state.get('label', '')
        
        print(f"[智能体] 步骤2: 解析目标 - 意图: {label}, 用户输入: {text}")
        
        # 只有"打开文件"或"打开软件"意图才需要解析目标
        if label not in ['打开文件', '打开软件']:
            print(f"[智能体] 意图不是'打开文件'或'打开软件'，跳过文件解析")
            return {**state, 'opened': False, 'action': label, 'error': '意图不匹配'}
        
        try:
            # 获取数据库实例
            db = get_database_instance()
            
            # 获取所有文件记录
            all_records = db.get_all_records()
            
            if not all_records:
                print(f"[智能体] 沙盒中没有文件记录")
                return {
                    **state,
                    'opened': False,
                    'action': label,
                    'error': '沙盒中没有文件，请先添加文件到沙盒'
                }
            
            # 使用大模型提取关键词
            keywords = extract_keywords_with_llm(text, all_records, api_key, model)
            
            # 根据提取的关键词匹配文件，并统计命中数量
            matching_records = []
            keyword_list = [kw.lower() for kw in keywords if kw.strip()]
            for record in all_records:
                file_title = record.get('file_title', '').lower()
                if keyword_list:
                    hit_count = sum(1 for keyword in keyword_list if keyword and keyword in file_title)
                    if hit_count > 0:
                        matching_records.append((hit_count, record))
                else:
                    # 如果没有提取到关键词，使用简单的文本匹配作为降级方案
                    user_text_lower = text.lower()
                    if any(word in file_title for word in user_text_lower.split() if len(word) > 1):
                        matching_records.append((1, record))
            
            if not matching_records:
                print(f"[智能体] 未找到匹配的文件")
                return {
                    **state,
                    'opened': False,
                    'action': label,
                    'error': '未找到匹配的文件，请检查文件是否已添加到沙盒'
                }
            
            # 选择命中关键词最多的记录
            matching_records.sort(key=lambda item: item[0], reverse=True)
            target_record = matching_records[0][1]
            file_path = target_record.get('file_path')
            file_title = target_record.get('file_title', '文件')
            shortcut_path = target_record.get('shortcut_path')
            
            print(f"[智能体] 找到匹配文件: {file_title} ({file_path})")
            
            # 检查文件是否存在
            if not file_path or not os.path.exists(file_path):
                # 如果原始文件不存在，尝试从快捷方式读取
                if shortcut_path and os.path.exists(shortcut_path):
                    try:
                        with open(shortcut_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.startswith("SOURCE_PATH="):
                                    file_path = line[len("SOURCE_PATH="):].strip()
                                    break
                    except Exception as e:
                        print(f"[智能体] 读取快捷方式失败: {e}")
                
                if not file_path or not os.path.exists(file_path):
                    return {
                        **state,
                        'opened': False,
                        'action': label,
                        'target_name': file_title,
                        'error': '文件不存在或已移动'
                    }
            
            # 打开文件
            try:
                if sys.platform.startswith('darwin'):  # macOS
                    os.system(f'open "{file_path}"')
                elif sys.platform.startswith('win'):  # Windows
                    os.startfile(file_path)
                else:  # Linux
                    os.system(f'xdg-open "{file_path}"')
                
                print(f"[智能体] 成功打开文件: {file_title}")
                return {
                    **state,
                    'opened': True,
                    'action': label,
                    'target_name': file_title,
                    'target': file_path,
                    'error': ''
                }
            except Exception as e:
                print(f"[智能体] 打开文件失败: {e}")
                return {
                    **state,
                    'opened': False,
                    'action': label,
                    'target_name': file_title,
                    'error': f'打开文件失败: {str(e)}'
                }
                
        except Exception as e:
            print(f"[智能体] 解析目标异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                'opened': False,
                'action': label,
                'error': f'解析目标失败: {str(e)}'
            }

    # 构建工作流图
    graph = StateGraph(dict)

    # 添加节点
    graph.add_node('classify', state_classifier)
    graph.add_node('resolve', state_resolve_target)
    
    # 添加边
    graph.add_edge(START, 'classify')
    graph.add_edge('classify', 'resolve')
    graph.add_edge('resolve', END)

    return graph.compile()