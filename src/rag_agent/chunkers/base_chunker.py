"""
基础分块器接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseChunker(ABC):
    """基础分块器抽象类"""
    
    @abstractmethod
    def chunk(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        将文本分块
        输入:
          - text: 待分块的文本
          - chunk_size: 每个切片的最大字符数
          - chunk_overlap: 切片重叠字符数
          - min_chunk_size: 最小切片大小
        输出: [
          {
            "content": str,  # 切片内容
            "start_char": int,  # 起始字符位置
            "end_char": int,  # 结束字符位置
            "page": int  # 所属页码（如果可确定）
          },
          ...
        ]
        """
        pass

