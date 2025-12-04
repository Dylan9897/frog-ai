"""
知识切片服务
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from ..models import Chunk, ChunkStatus
from ..database import DatabaseManager
from ..chunkers.semantic_chunker import SemanticLLMChunker


class ChunkService:
    """知识切片服务类"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def create_chunk(
        self,
        document_id: str,
        content: str,
        source_page: int,
        tags: Optional[List[str]] = None,
        start_char: Optional[int] = None,
        end_char: Optional[int] = None
    ) -> Chunk:
        """创建知识切片"""
        now = datetime.now()
        chunk = Chunk(
            id=f"chunk-{uuid.uuid4().hex[:12]}",
            document_id=document_id,
            content=content,
            source_page=source_page,
            tags=tags or [],
            start_char=start_char,
            end_char=end_char,
            status=ChunkStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        if self.db.create_chunk(chunk):
            self._update_document_chunks_count(document_id)
            return chunk
        raise RuntimeError("创建知识切片失败")
    
    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """获取切片详情"""
        return self.db.get_chunk(chunk_id)
    
    def list_chunks(
        self,
        document_id: str,
        status: Optional[ChunkStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取文档的知识切片列表（分页）"""
        chunks, total = self.db.list_chunks(document_id, status, page, page_size)
        return {
            "chunks": chunks,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    
    def update_chunk(
        self,
        chunk_id: str,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_page: Optional[int] = None
    ) -> Optional[Chunk]:
        """更新知识切片"""
        chunk = self.db.get_chunk(chunk_id)
        if not chunk:
            return None

        if content is not None:
            chunk.content = content
        if tags is not None:
            chunk.tags = tags
        if source_page is not None:
            chunk.source_page = source_page

        chunk.updated_at = datetime.now()

        if self.db.update_chunk(chunk):
            return chunk
        return None
    
    def delete_chunk(self, chunk_id: str) -> bool:
        """删除知识切片"""
        chunk = self.db.get_chunk(chunk_id)
        if not chunk:
            return False

        success = self.db.delete_chunk(chunk_id)
        if success:
            self._update_document_chunks_count(chunk.document_id)
        return success
    
    def confirm_chunk(self, chunk_id: str, status: ChunkStatus = ChunkStatus.CONFIRMED) -> Optional[Chunk]:
        """确认切片入库 / 归档"""
        chunk = self.db.get_chunk(chunk_id)
        if not chunk:
            return None

        chunk.status = status
        now = datetime.now()
        chunk.updated_at = now
        chunk.confirmed_at = now

        if self.db.update_chunk(chunk):
            return chunk
        return None
    
    def auto_chunk(
        self,
        document_id: str,
        chunker_type: str = "semantic",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ) -> List[Chunk]:
        """
        自动分块（从文档解析文本生成切片，默认使用大模型语义分块）
        """
        # 获取文档，确保存在
        document = self.db.get_document(document_id)
        if not document:
            raise ValueError(f"文档不存在: {document_id}")

        # 获取所有解析文本页面
        pages = self.db.list_parsed_text_pages(document_id)
        if not pages:
            # 对于非分页解析的文档，退回到整篇内容
            content = self.db.get_parsed_text(document_id, page_number=None)
            if not content:
                raise ValueError("文档尚未完成解析，无法自动生成知识切片")
            pages = [
                {
                    "page_number": 1,
                    "content": content,
                }
            ]

        if chunker_type not in ("semantic",):
            # 目前仅实现 semantic，将其它类型统一归为 semantic
            chunker_type = "semantic"

        chunker = SemanticLLMChunker()
        created_chunks: List[Chunk] = []

        for page_info in pages:
            page_number = page_info.get("page_number") or 1
            text = page_info.get("content") or ""
            if not text.strip():
                continue

            # 使用分块器生成结构化切片
            segments = chunker.chunk(
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                min_chunk_size=min_chunk_size,
            )

            for seg in segments:
                content = (seg.get("content") or "").strip()
                if not content:
                    continue
                tags = seg.get("tags") or []
                source_page = seg.get("page") or page_number
                start_char = seg.get("start_char")
                end_char = seg.get("end_char")

                chunk = self.create_chunk(
                    document_id=document_id,
                    content=content,
                    source_page=source_page,
                    tags=tags,
                    start_char=start_char,
                    end_char=end_char,
                )
                created_chunks.append(chunk)

        # 最后再统一更新一次文档切片数量（内部会重新统计）
        self._update_document_chunks_count(document_id)
        return created_chunks

    # ------------------------------------------------------------------ #
    # 内部工具方法
    # ------------------------------------------------------------------ #

    def _update_document_chunks_count(self, document_id: str) -> None:
        """根据数据库中实际切片数量刷新 documents.chunks_count 字段"""
        count = self.db.count_chunks(document_id)
        document = self.db.get_document(document_id)
        if not document:
            return

        document.chunks_count = count
        document.updated_at = datetime.now()
        self.db.update_document(document)

