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
from ..parsers.pdf_parser import PDFParser
from ..parsers.text_parser import TextParser
from ..parsers.docx_parser import DocxParser
from ..parsers.excel_parser import ExcelParser


class DocumentService:
    """文档管理服务类"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.documents_dir = Path(RAG_CONFIG["storage"]["documents_dir"])
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir = Path(RAG_CONFIG["storage"]["pages_dir"])
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        # 初始化解析器
        self.pdf_parser = PDFParser(str(self.pages_dir))
        self.text_parser = TextParser(str(self.pages_dir))
        self.docx_parser = DocxParser(str(self.pages_dir))
        self.excel_parser = ExcelParser(str(self.pages_dir))
    
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
            # 如果文件支持转换为图片，异步转换为图片（后台处理）
            if file_ext in ['pdf', 'txt', 'md', 'json', 'py', 'js', 'ts', 'html', 'css', 'docx', 'xlsx', 'xls']:
                import threading
                document.status = DocumentStatus.PROCESSING
                self.db.update_document(document)
                # 在后台线程中处理
                thread = threading.Thread(target=self._convert_document_to_images, args=(document,), daemon=True)
                thread.start()
            return document
        raise Exception("保存文档到数据库失败")
    
    def _convert_document_to_images(self, document: Document):
        """
        将文档转换为图片（按页）
        输入: document - Document 对象
        """
        try:
            print(f"[DocumentService] 开始转换文档为图片: {document.id}, 类型: {document.file_type}")
            
            pages_info = []
            file_ext = document.file_type.lower()
            
            # 根据文件类型选择对应的解析器
            if file_ext == 'pdf':
                pages_info = self.pdf_parser.convert_to_images(
                    document.file_path,
                    document.id,
                    format='png'
                )
            elif file_ext in ['txt', 'md', 'json', 'py', 'js', 'ts', 'html', 'css', 'log', 'yml', 'yaml', 'xml', 'csv']:
                # 文本类文件
                pages_info = self.text_parser.convert_to_images(
                    document.file_path,
                    document.id,
                    format='png'
                )
            elif file_ext == 'docx':
                # Word 文档
                pages_info = self.docx_parser.convert_to_images(
                    document.file_path,
                    document.id,
                    format='png'
                )
            elif file_ext in ['xlsx', 'xls']:
                # Excel 文件
                pages_info = self.excel_parser.convert_to_images(
                    document.file_path,
                    document.id,
                    format='png'
                )
            else:
                print(f"[DocumentService] 不支持的文件类型: {file_ext}")
                document.status = DocumentStatus.FAILED
                self.db.update_document(document)
                return
            
            if not pages_info:
                print(f"[DocumentService] 未生成任何页面图片")
                document.status = DocumentStatus.FAILED
                self.db.update_document(document)
                return
            
            # 保存页面信息到数据库
            for page_info in pages_info:
                self.db.create_page(
                    document_id=document.id,
                    page_number=page_info['page_number'],
                    image_path=page_info['image_path'],
                    width=page_info.get('width'),
                    height=page_info.get('height'),
                    format=page_info.get('format', 'png')
                )
            
            # 更新文档的总页数和状态
            document.total_pages = len(pages_info)
            document.status = DocumentStatus.COMPLETED
            document.parsed_at = datetime.now()
            self.db.update_document(document)
            
            print(f"[DocumentService] 成功转换 {len(pages_info)} 页图片")
        except Exception as e:
            print(f"[DocumentService] 转换图片失败: {e}")
            import traceback
            traceback.print_exc()
            # 更新状态为失败
            document.status = DocumentStatus.FAILED
            self.db.update_document(document)
    
    def get_document(self, document_id: str) -> Optional[Document]:
        """
        获取文档详情
        输入: document_id
        输出: Document 对象或 None
        """
        return self.db.get_document(document_id)
    
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
            
            # 3. 删除页面图片目录
            pages_dir = self.pages_dir / document.id
            if pages_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(pages_dir)
                    print(f"[DocumentService] 成功删除页面图片目录: {pages_dir}")
                except Exception as e:
                    print(f"[DocumentService] 删除页面图片目录失败: {e}")
            
            # 4. 删除数据库记录（级联删除相关切片和任务）
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
        document = self.db.get_document(document_id)
        if document:
            document.status = status
            document.updated_at = datetime.now()
            if self.db.update_document(document):
                return document
        return None
    
    def update_chunks_count(self, document_id: str) -> bool:
        """
        更新文档的切片数量
        输入: document_id
        输出: 是否成功
        """
        # TODO: 统计并更新切片数量
        pass

