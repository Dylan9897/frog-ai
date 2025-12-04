"""
使用大模型进行语义分块的分块器
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
import json
import re

from .base_chunker import BaseChunker

try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:  # pragma: no cover - 运行环境可能没有安装 dashscope
    DASHSCOPE_AVAILABLE = False

from ..parsers.pdf_vl_parser import _load_dashscope_api_key


class SemanticLLMChunker(BaseChunker):
    """
    使用通用大模型（Qwen）按语义生成知识切片。

    注意：
    - 如果 dashscope 或 API Key 不可用，将回退到简单规则分块。
    - 返回的数据结构与 BaseChunker 约定保持一致。
    """

    DEFAULT_MODEL = "qwen-max"

    def __init__(self, model: Optional[str] = None):
        self.model = model or self.DEFAULT_MODEL
        self._init_dashscope()

    def _init_dashscope(self) -> None:
        api_key = _load_dashscope_api_key()
        if api_key and DASHSCOPE_AVAILABLE:
            dashscope.api_key = api_key
        elif not DASHSCOPE_AVAILABLE:
            print("[SemanticLLMChunker] dashscope 未安装，将使用规则分块降级。")
        else:
            print("[SemanticLLMChunker] DashScope API Key 未配置，将使用规则分块降级。")

    @staticmethod
    def _clean_text_for_llm(text: str, max_length: int = 20000) -> str:
        """
        清理文本中的特殊字符，防止调用 LLM 时出错。
        
        处理内容：
        1. 移除控制字符（除了换行、制表符）
        2. 移除零宽字符
        3. 标准化空白字符
        4. 限制文本长度
        
        Args:
            text: 原始文本
            max_length: 最大长度限制（避免超过 API 限制）
            
        Returns:
            清理后的文本
        """
        if not text:
            return ""
        
        # 1. 移除控制字符（保留换行\n、制表符\t、回车\r）
        # 控制字符范围：\x00-\x1F 和 \x7F-\x9F，但排除 \n \t \r
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        
        # 2. 移除零宽字符（Zero Width Characters）
        # 包括：零宽空格、零宽非连接符、零宽连接符、左至右/右至左标记等
        zero_width_chars = [
            '\u200B',  # 零宽空格
            '\u200C',  # 零宽非连接符
            '\u200D',  # 零宽连接符
            '\u200E',  # 左至右标记
            '\u200F',  # 右至左标记
            '\uFEFF',  # 零宽非断空格（BOM）
        ]
        for char in zero_width_chars:
            text = text.replace(char, '')
        
        # 3. 标准化空白字符：多个连续空格/制表符压缩为一个空格
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 4. 标准化换行：多个连续换行压缩为最多两个换行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 5. 去除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        # 6. 限制总长度（避免超过 API token 限制）
        if len(text) > max_length:
            text = text[:max_length] + "\n...(内容过长，已截断)"
        
        return text.strip()

    # ------------------------------------------------------------------ #
    # BaseChunker 接口实现
    # ------------------------------------------------------------------ #

    def chunk(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ) -> List[Dict[str, Any]]:
        if not text:
            return []

        # 如果大模型不可用，直接使用规则分块
        if not DASHSCOPE_AVAILABLE or not _load_dashscope_api_key():
            return self._rule_based_chunk(text, chunk_size, chunk_overlap, min_chunk_size)

        # 清理文本中的特殊字符，防止 API 调用失败
        cleaned_text = self._clean_text_for_llm(text)
        if not cleaned_text:
            print("[SemanticLLMChunker] 清理后文本为空，使用规则分块")
            return self._rule_based_chunk(text, chunk_size, chunk_overlap, min_chunk_size)

        system_prompt = (
            "你是一个知识工程助手，需要把文档内容整理成适合知识库检索的「知识片」。"
            "每个知识片应围绕一个清晰的要点或场景，内容完整、可单独理解。"
            "返回格式必须是 JSON 数组，不要输出任何解释性文字。"
        )

        # 完全使用 f-string，避免 .format() 与文档内容中的 {} 字符冲突
        user_prompt = f"""请根据下面的文档内容，自动拆分为若干知识片（Knowledge Chunk）：
要求：
1. 每个知识片只描述一个相对完整的知识点，可以包含必要的上下文。
2. 保持原文关键信息，不要发挥，不要编造内容。
3. 尽量控制每个知识片的长度在约 {chunk_size} 个中文字符以内，必要时可略微超过。
4. 使用简明的中文撰写。
5. 使用 JSON 数组返回，每个元素的结构为：
{{
  "content": "知识片正文，保持段落换行",
  "tags": ["可选标签1", "可选标签2"]
}}
注意：
- 严格返回 JSON，不要包裹在 ```json ``` 代码块里。
- 如果无法识别标签，可以让 tags 为空数组。

文档内容如下：
--------------------
{cleaned_text}
--------------------
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            resp = Generation.call(
                model=self.model,
                messages=messages,
                result_format="message",
                temperature=0.2,
                max_tokens=2048,
            )

            if resp.status_code != 200:
                print(f"[SemanticLLMChunker] LLM 调用失败: {resp.status_code} - {resp.message}")
                return self._rule_based_chunk(text, chunk_size, chunk_overlap, min_chunk_size)

            content = resp.output.choices[0].message.content or ""
            result = self._parse_llm_output(content, chunk_size, chunk_overlap, min_chunk_size)
            
            # 如果 LLM 解析失败返回空列表，回退到规则分块
            if not result:
                print("[SemanticLLMChunker] LLM 输出解析失败，回退到规则分块")
                return self._rule_based_chunk(text, chunk_size, chunk_overlap, min_chunk_size)
            
            return result
        except Exception as e:  # pragma: no cover - 保护性兜底
            print(f"[SemanticLLMChunker] 调用 LLM 异常: {e}")
            return self._rule_based_chunk(text, chunk_size, chunk_overlap, min_chunk_size)

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #

    def _parse_llm_output(
        self,
        raw_text: str,
        chunk_size: int,
        chunk_overlap: int,
        min_chunk_size: int,
    ) -> List[Dict[str, Any]]:
        """
        从大模型输出中提取 JSON 数组，如果失败则回退到规则分块。
        """
        if not raw_text:
            return []

        # 1. 尝试移除 markdown 代码块标记（如果 LLM 返回了 ```json ... ```）
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            # 移除开头的 ```json 或 ```
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            # 移除结尾的 ```
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        
        # 2. 尝试截取第一个 JSON 数组
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
        else:
            candidate = cleaned

        try:
            data = json.loads(candidate)
            chunks: List[Dict[str, Any]] = []
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    content = (item.get("content") or "").strip()
                    if not content:
                        continue
                    tags = item.get("tags") or []
                    if isinstance(tags, str):
                        tags = [tags]
                    chunks.append(
                        {
                            "content": content,
                            "tags": [str(t).strip() for t in tags if str(t).strip()],
                            "start_char": None,
                            "end_char": None,
                            # page 字段在上层根据实际页码填充
                            "page": None,
                        }
                    )
            if chunks:
                return chunks
        except json.JSONDecodeError as e:
            print(f"[SemanticLLMChunker] 解析 LLM JSON 输出失败: {e}")
            print(f"[SemanticLLMChunker] 原始输出: {raw_text[:200]}...")
        except Exception as e:
            print(f"[SemanticLLMChunker] 处理 LLM 输出时发生异常: {e}")

        # JSON 解析失败时回退（这里不应该用 raw_text，应该用原始输入）
        print("[SemanticLLMChunker] 回退到规则分块")
        return []

    def _rule_based_chunk(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        min_chunk_size: int,
    ) -> List[Dict[str, Any]]:
        """
        简单的规则分块：按段落 & 固定长度切分，保证即使没有大模型也能工作。
        """
        if not text:
            return []

        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        merged_text = "\n".join(paragraphs)

        chunks: List[Dict[str, Any]] = []
        start = 0
        length = len(merged_text)

        while start < length:
            end = min(start + chunk_size, length)

            # 尝试在 chunk_size 附近向左找到一个段落边界
            boundary = merged_text.rfind("\n", start + min_chunk_size, end)
            if boundary != -1 and boundary > start + min_chunk_size:
                end = boundary

            content = merged_text[start:end].strip()
            if content:
                chunks.append(
                    {
                        "content": content,
                        "tags": [],
                        "start_char": start,
                        "end_char": end,
                        "page": None,
                    }
                )

            if end >= length:
                break

            # 下一个切片从 overlap 之后开始
            start = max(end - chunk_overlap, start + min_chunk_size)

        return chunks


