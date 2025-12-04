"""
文档管理服务
"""
import os
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..models import Document, DocumentStatus
from ..database import DatabaseManager
from ..config import RAG_CONFIG


class DocumentService:
    """文档管理服务类"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.documents_dir = Path(RAG_CONFIG["storage"]["documents_dir"])
        self.documents_dir.mkdir(parents=True, exist_ok=True)
    
    def upload_document(self, file, name: Optional[str] = None) -> Document:
        """上传文档"""
        # 验证文件
        filename = file.filename or 'unknown'
        file_ext = Path(filename).suffix.lower().lstrip('.')
        if file_ext not in RAG_CONFIG["parsing"]["supported_formats"]:
            raise ValueError(f"不支持的文件类型: {file_ext}")
        
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > RAG_CONFIG["parsing"]["max_file_size"]:
            raise ValueError(f"文件大小超过限制: {file_size} bytes")
        
        # 生成ID和保存路径
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        save_name = f"{doc_id}_{filename}"
        file_path = self.documents_dir / save_name
        
        # 保存文件
        file.save(str(file_path))
        
        # 创建文档对象
        document = Document(
            id=doc_id,
            name=name or filename,
            file_path=str(file_path),
            file_size=file_size,
            file_type=file_ext,
            status=DocumentStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 保存到数据库
        if self.db.create_document(document):
            return document
        raise Exception("保存文档到数据库失败")
    
    def get_document(self, document_id: str) -> Optional[Document]:
        """
        获取文档详情
        输入: document_id
        输出: Document 对象或 None
        """
        # TODO: 从数据库查询并返回 Document
        pass
    
    def list_documents(
        self, 
        status: Optional[DocumentStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取文档列表"""
        documents, total = self.db.list_documents(status, page, page_size)
        return {
            "documents": documents,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    
    def delete_document(self, document_id: str) -> bool:
        """
        删除文档
        输入: document_id
        输出: 是否成功
        """
        try:
            print(f"[DocumentService] 开始删除文档: {document_id}")
            # 1. 获取文档信息（用于删除文件）
            document = self.db.get_document(document_id)
            if not document:
                print(f"[DocumentService] 文档不存在: {document_id}")
                return False
            
            print(f"[DocumentService] 找到文档: {document.name}, 文件路径: {document.file_path}")
            
            # 2. 删除物理文件
            file_path = Path(document.file_path)
            if file_path.exists():
                try:
                    file_path.unlink()
                    print(f"[DocumentService] 成功删除物理文件: {file_path}")
                except Exception as e:
                    print(f"[DocumentService] 删除文件失败: {e}")
                    # 文件删除失败不影响数据库删除
            else:
                print(f"[DocumentService] 文件不存在，跳过删除: {file_path}")
            
            # 3. 删除数据库记录（级联删除相关切片和任务）
            result = self.db.delete_document(document_id)
            print(f"[DocumentService] 数据库删除结果: {result}")
            return result
        except Exception as e:
            print(f"[DocumentService] 删除文档失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_document_status(
        self, 
        document_id: str, 
        status: DocumentStatus
    ) -> Optional[Document]:
        """
        更新文档状态
        输入:
          - document_id
          - status: 新状态
        输出: 更新后的 Document 对象
        """
        # TODO: 更新文档状态
        pass
    
    def update_chunks_count(self, document_id: str) -> bool:
        """
        更新文档的切片数量
        输入: document_id
        输出: 是否成功
        """
        # TODO: 统计并更新切片数量
        pass

