"""
基础解析器接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class BaseParser(ABC):
    """基础解析器抽象类"""
    
    @abstractmethod
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        解析文档
        输入: file_path - 文件路径
        输出: {
            "success": bool,
            "content": str,  # 解析后的文本内容
            "pages": List[Dict],  # 页面信息列表
            "metadata": Dict  # 文档元数据
        }
        """
        pass
    
    @abstractmethod
    def get_page_content(
        self, 
        file_path: str, 
        page_number: int,
        format: str = 'text'
    ) -> Optional[bytes]:
        """
        获取指定页面内容
        输入:
          - file_path: 文件路径
          - page_number: 页码（从1开始）
          - format: 返回格式（text, image/png, json）
        输出: 页面内容（bytes）或 None
        """
        pass
    
    @abstractmethod
    def get_total_pages(self, file_path: str) -> int:
        """
        获取文档总页数
        输入: file_path
        输出: 总页数
        """
        pass
    
    def validate_file(self, file_path: str) -> tuple[bool, Optional[str]]:
        """
        验证文件是否可解析
        输入: file_path
        输出: (是否有效, 错误信息)
        """
        path = Path(file_path)
        if not path.exists():
            return False, "文件不存在"
        if not path.is_file():
            return False, "路径不是文件"
        return True, None

