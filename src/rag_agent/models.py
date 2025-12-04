"""
数据模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class DocumentStatus(str, Enum):
    """文档状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    FAILED = "failed"


class ChunkStatus(str, Enum):
    """切片状态"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Document:
    """文档模型"""
    id: str
    name: str
    file_path: str
    file_size: int
    file_type: str
    status: DocumentStatus = DocumentStatus.PENDING
    total_pages: int = 0
    chunks_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    parsed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "status": self.status.value,
            "status_color": self._get_status_color(),
            "total_pages": self.total_pages,
            "chunks_count": self.chunks_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None,
            "metadata": self.metadata
        }

    def _get_status_color(self) -> str:
        """获取状态对应的颜色"""
        color_map = {
            DocumentStatus.PENDING: "#ffb86c",      # 警告色
            DocumentStatus.PROCESSING: "#8f9bb3",   # 次要文本色
            DocumentStatus.COMPLETED: "#00d2b6",    # 成功色
            DocumentStatus.ARCHIVED: "#8f9bb3",
            DocumentStatus.FAILED: "#ff6b6b"        # 错误色
        }
        return color_map.get(self.status, "#8f9bb3")


@dataclass
class Chunk:
    """知识切片模型"""
    id: str
    document_id: str
    content: str
    source_page: int
    tags: List[str] = field(default_factory=list)
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    status: ChunkStatus = ChunkStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = None
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "tags": self.tags,
            "source_page": self.source_page,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None
        }


@dataclass
class ParsingTask:
    """解析任务模型"""
    id: str
    document_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "status": self.status.value,
            "progress": self.progress,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class PageContent:
    """页面内容模型"""
    page_number: int
    content: bytes  # 可以是图片的 base64 编码或文本内容
    format: str  # image/png, text/plain, application/json
    width: Optional[int] = None
    height: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        import base64
        return {
            "page_number": self.page_number,
            "content": base64.b64encode(self.content).decode('utf-8') if isinstance(self.content, bytes) else self.content,
            "format": self.format,
            "width": self.width,
            "height": self.height
        }


@dataclass
class ParsedText:
    """解析后的文本模型"""
    document_id: str
    content: str
    page_number: Optional[int] = None
    cleaned_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "document_id": self.document_id,
            "content": self.content,
            "page_number": self.page_number,
            "cleaned_at": self.cleaned_at.isoformat() if self.cleaned_at else None
        }

