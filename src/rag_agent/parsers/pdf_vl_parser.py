"""
PDF VL 解析器
使用阿里云 DashScope VL 系列大模型解析 PDF 文件
"""
from pathlib import Path
from typing import Dict, Any, Optional, List, Iterator
import base64
import os

try:
    import dashscope
    from dashscope import MultiModalConversation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def _load_dashscope_api_key() -> Optional[str]:
    """加载 DashScope API Key"""
    # 1. 环境变量
    env_key = os.environ.get('DASHSCOPE_API_KEY')
    if env_key:
        return env_key.strip()
    
    # 2. 从配置文件加载
    try:
        from src.agent.config import DASHSCOPE_API_KEY
        if DASHSCOPE_API_KEY:
            return str(DASHSCOPE_API_KEY).strip()
    except (ImportError, AttributeError):
        pass
    
    return None


class PDFVLParser:
    """PDF VL 解析器（使用阿里云 VL 大模型）"""
    
    # VL 模型配置
    VL_MODEL = "qwen-vl-max"  # 可选: qwen-vl-max, qwen-vl-plus
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化 PDF VL 解析器"""
        self.api_key = api_key or _load_dashscope_api_key()
        if self.api_key and DASHSCOPE_AVAILABLE:
            dashscope.api_key = self.api_key
        else:
            print("[PDFVLParser] 警告: DashScope API Key 未配置或 dashscope 未安装")
    
    def _clean_ai_output(self, text: str) -> str:
        """
        清理AI返回的内容，移除格式标记、JSON片段、LaTeX命令等
        只保留纯文本内容
        """
        if not text:
            return ""
        
        import re
        
        # 1. 移除 markdown 前缀（各种变体）
        text = re.sub(r'^markdown\s*\n?', '', text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'^```markdown\s*\n?', '', text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'^```\s*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        
        # 2. 移除完整的JSON对象（更全面的匹配）
        # 匹配 {'text': '...'} 或 {"text": "..."} 并提取内容
        text = re.sub(r"\{['\"]?text['\"]?\s*:\s*['\"]([^'\"]*)['\"]\s*\}", r'\1', text)
        text = re.sub(r"\{['\"]?text['\"]?\s*:\s*([^}]*?)\s*\}", r'\1', text)
        
        # 3. 移除JSON结构片段（更彻底的清理）
        # 处理 }{'text': ' 或 }{"text": " 等连接片段
        text = re.sub(r"}\s*\{['\"]?text['\"]?\s*:\s*['\"]?", '', text)
        text = re.sub(r"}\s*\{['\"]?text['\"]?\s*:\s*", '', text)
        text = re.sub(r"}\s*\{", '', text)  # 移除所有 }{ 连接
        
        # 4. 移除残留的JSON键值对模式
        text = re.sub(r"['\"]?text['\"]?\s*:\s*['\"]?", '', text)
        text = re.sub(r"['\"]?content['\"]?\s*:\s*['\"]?", '', text)
        text = re.sub(r"['\"]?message['\"]?\s*:\s*['\"]?", '', text)
        
        # 5. 移除残留的JSON结构字符（但保留正常文本中的大括号）
        # 只移除明显是JSON结构的片段
        text = re.sub(r"^\s*[{}'\"\[\]]+\s*", '', text)  # 开头的JSON字符
        text = re.sub(r"\s*[{}'\"\[\]]+\s*$", '', text)  # 结尾的JSON字符
        # 移除孤立的JSON字符（前后都是空白或换行）
        text = re.sub(r"\s+[{}'\"\[\]]\s+", ' ', text)
        
        # 6. 移除LaTeX数学公式标记（$...$ 或 $$...$$）
        text = re.sub(r'\$\$[^$]*\$\$', '', text)  # 块级公式
        text = re.sub(r'\$[^$]*\$', '', text)  # 行内公式（但避免误删）
        
        # 7. 移除LaTeX命令和特殊符号
        text = re.sub(r'\^\{[^}]*\}', '', text)  # 上标命令 ^{...}
        text = re.sub(r'\\[a-zA-Z]+\*?', '', text)  # LaTeX命令如 \spadesuit, \star 等
        text = re.sub(r'\\[{}]', '', text)  # 转义的大括号
        text = re.sub(r'\\n', '\n', text)  # 将 \n 转换为实际换行
        
        # 8. 移除其他可能的格式标记
        text = re.sub(r'<[^>]+>', '', text)  # 移除HTML标签
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # 移除Markdown链接，保留文本
        
        # 9. 规范化空白字符（保留必要的格式）
        text = text.replace('\r\n', '\n').replace('\r', '\n')  # 统一换行符
        # 不要合并多个空格，因为markdown可能需要它们（如代码块、列表缩进）
        # 只合并行内的多个连续空格（但保留行首的缩进）
        lines = text.split('\n')
        normalized_lines = []
        for line in lines:
            # 保留行首的空白（用于markdown缩进）
            leading_spaces = len(line) - len(line.lstrip())
            leading = line[:leading_spaces]
            content = line[leading_spaces:]
            # 只对行内容合并多个空格
            content = re.sub(r'[ \t]{2,}', ' ', content)
            normalized_lines.append(leading + content)
        text = '\n'.join(normalized_lines)
        text = re.sub(r'\n{3,}', '\n\n', text)  # 多个换行合并为最多两个
        
        # 10. 移除行首行尾的空白并去重
        lines = text.split('\n')
        cleaned_lines = []
        seen_lines = set()  # 用于检测完全重复的行
        prev_line = None
        
        prev_was_empty = False
        for line in lines:
            original_line = line
            line_stripped = line.strip()
            
            # 处理空行：保留段落分隔，但避免连续多个空行
            if not line_stripped:
                if not prev_was_empty and cleaned_lines:
                    # 如果前一行不是空行，且列表不为空，添加一个空行作为段落分隔
                    cleaned_lines.append('')
                    prev_was_empty = True
                # 如果前一行已经是空行，跳过（避免连续多个空行）
                continue
            
            prev_was_empty = False
            
            # 保留原始行的格式（用于markdown缩进），但用于比较时使用strip后的版本
            line = line  # 保留原始格式
            line_for_compare = line_stripped  # 用于去重比较
            
            # 跳过完全重复的行（使用集合检测，基于strip后的内容）
            if line_for_compare in seen_lines:
                continue
            
            # 处理增量输出：如果当前行是前一行的一部分（前一行更长）
            prev_line_compare = prev_line.strip() if prev_line else None
            if prev_line_compare and prev_line_compare.startswith(line_for_compare) and len(prev_line_compare) > len(line_for_compare) + 2:
                # 前一行已经包含当前行的内容，跳过
                continue
            
            # 处理增量输出：如果当前行包含前一行（当前行更长）
            if prev_line_compare and line_for_compare.startswith(prev_line_compare) and len(line_for_compare) > len(prev_line_compare) + 2:
                # 用更完整的行替换前一行
                if cleaned_lines:
                    removed = cleaned_lines.pop()
                    removed_compare = removed.strip()
                    if removed_compare in seen_lines:
                        seen_lines.remove(removed_compare)
                cleaned_lines.append(line)
                seen_lines.add(line_for_compare)
                prev_line = line
            else:
                # 检查是否与已存在的行重复（相似度检查）
                is_duplicate = False
                for existing_line_compare in seen_lines:
                    # 如果当前行是已存在行的前缀或后缀，且长度接近，认为是重复
                    if (existing_line_compare.startswith(line_for_compare) or line_for_compare.startswith(existing_line_compare)) and abs(len(existing_line_compare) - len(line_for_compare)) < 5:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    cleaned_lines.append(line)
                    seen_lines.add(line_for_compare)
                    prev_line = line
        
        text = '\n'.join(cleaned_lines)
        
        # 11. 最终清理：移除开头和结尾的空白
        text = text.strip()
        
        # 12. 移除可能的残留JSON字符
        while text and text[0] in ['{', '[', '"', "'"]:
            text = text[1:].strip()
        while text and text[-1] in ['}', ']', '"', "'"]:
            text = text[:-1].strip()
        
        return text
    
    def _pdf_page_to_base64(self, pdf_path: str, page_number: int, dpi: int = 150) -> Optional[str]:
        """将 PDF 页面转换为 base64 图片"""
        if not PYMUPDF_AVAILABLE:
            print("[PDFVLParser] PyMuPDF 未安装，无法转换 PDF 页面")
            return None
        
        try:
            doc = fitz.open(pdf_path)
            if page_number < 1 or page_number > len(doc):
                doc.close()
                return None
            
            page = doc[page_number - 1]
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为 base64
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            doc.close()
            return img_base64
        except Exception as e:
            print(f"[PDFVLParser] PDF 页面转图片失败: {e}")
            return None
    
    def parse_page_stream(
        self, 
        pdf_path: str, 
        page_number: int,
        prompt: Optional[str] = None
    ) -> Iterator[str]:
        """
        流式解析 PDF 页面
        输入:
          - pdf_path: PDF 文件路径
          - page_number: 页码（从1开始）
          - prompt: 自定义提示词
        输出: 生成器，yield 文本片段
        """
        if not self.api_key:
            yield "[错误] DashScope API Key 未配置"
            return
        
        if not DASHSCOPE_AVAILABLE:
            yield "[错误] dashscope 库未安装，请运行: pip install dashscope"
            return
        
        if not PYMUPDF_AVAILABLE:
            yield "[错误] PyMuPDF 未安装，请运行: pip install PyMuPDF"
            return
        
        # 将 PDF 页面转换为图片
        img_base64 = self._pdf_page_to_base64(pdf_path, page_number)
        if not img_base64:
            yield f"[错误] 无法读取 PDF 第 {page_number} 页"
            return
        
        # 构建提示词
        default_prompt = "请识别并提取这张图片中的所有文字内容，保持原有的格式和结构，使用 Markdown 格式输出。"
        final_prompt = prompt or default_prompt
        
        try:
            # 调用 VL 模型（流式）
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": f"data:image/png;base64,{img_base64}"
                        },
                        {
                            "text": final_prompt
                        }
                    ]
                }
            ]
            
            response = MultiModalConversation.call(
                model=self.VL_MODEL,
                messages=messages,
                stream=True
            )
            
            # 流式输出
            # DashScope流式响应返回的是累积的完整文本，需要提取增量部分
            accumulated_text = ""  # 累积的完整文本（清理后）
            for chunk in response:
                try:
                    # 检查响应状态
                    if hasattr(chunk, 'status_code') and chunk.status_code != 200:
                        error_msg = getattr(chunk, 'message', f'状态码: {chunk.status_code}')
                        yield f"[错误] API调用失败: {error_msg}"
                        return
                    
                    # 提取内容
                    content = None
                    if hasattr(chunk, 'output') and chunk.output:
                        if hasattr(chunk.output, 'choices') and chunk.output.choices:
                            choice = chunk.output.choices[0]
                            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                                content = choice.message.content
                    elif hasattr(chunk, 'choices') and chunk.choices:
                        # 某些版本的响应格式可能不同
                        choice = chunk.choices[0]
                        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                            content = choice.message.content
                    
                    if content:
                        # 确保返回字符串类型
                        content_str = ""
                        if isinstance(content, str):
                            content_str = content
                        elif isinstance(content, list):
                            # 如果是列表，提取文本内容
                            text_items = []
                            for item in content:
                                if isinstance(item, str):
                                    text_items.append(item)
                                elif isinstance(item, dict):
                                    # 如果是字典，尝试提取text字段
                                    if 'text' in item:
                                        text_items.append(str(item['text']))
                                    else:
                                        text_items.append(str(item))
                                else:
                                    text_items.append(str(item))
                            content_str = "".join(text_items)
                        elif isinstance(content, dict):
                            # 如果是字典，尝试提取text字段
                            if 'text' in content:
                                content_str = str(content['text'])
                            else:
                                content_str = str(content)
                        else:
                            content_str = str(content)
                        
                        # 清理并处理增量输出
                        if content_str:
                            # 清理内容：移除JSON格式、LaTeX命令等
                            cleaned_content = self._clean_ai_output(content_str)
                            
                            if cleaned_content:
                                # DashScope返回的是累积文本，需要提取新增部分
                                if accumulated_text and cleaned_content.startswith(accumulated_text):
                                    # 新内容包含已累积的文本，提取新增部分
                                    new_text = cleaned_content[len(accumulated_text):]
                                    if new_text:
                                        accumulated_text = cleaned_content
                                        yield new_text
                                elif accumulated_text and len(cleaned_content) < len(accumulated_text):
                                    # 新内容比累积文本短，可能是格式变化，跳过
                                    continue
                                else:
                                    # 首次输出或新内容不包含累积文本
                                    if accumulated_text:
                                        # 如果累积文本在新内容中，提取新增部分
                                        if accumulated_text in cleaned_content:
                                            idx = cleaned_content.find(accumulated_text)
                                            if idx == 0:
                                                new_text = cleaned_content[len(accumulated_text):]
                                            else:
                                                # 累积文本不在开头，可能是格式变化，使用全部
                                                new_text = cleaned_content
                                                accumulated_text = cleaned_content
                                        else:
                                            # 完全不包含，可能是新的开始
                                            new_text = cleaned_content
                                            accumulated_text = cleaned_content
                                    else:
                                        # 首次输出
                                        new_text = cleaned_content
                                        accumulated_text = cleaned_content
                                    
                                    if new_text:
                                        yield new_text
                except Exception as e:
                    print(f"[PDFVLParser] 处理chunk时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
                    
        except Exception as e:
            error_msg = str(e)
            print(f"[PDFVLParser] 解析失败: {error_msg}")
            import traceback
            traceback.print_exc()
            yield f"[错误] 解析失败: {error_msg}"
    
    def parse_page(
        self, 
        pdf_path: str, 
        page_number: int,
        prompt: Optional[str] = None
    ) -> str:
        """
        解析 PDF 页面（非流式）
        输入:
          - pdf_path: PDF 文件路径
          - page_number: 页码（从1开始）
          - prompt: 自定义提示词
        输出: 解析后的文本
        """
        result = ""
        for chunk in self.parse_page_stream(pdf_path, page_number, prompt):
            result += chunk
        return result

