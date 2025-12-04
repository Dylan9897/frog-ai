"""
文本解析服务
负责将各种文件格式解析为 Markdown 文本，支持并发处理
"""
import threading
import queue
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from ..database import DatabaseManager
from ..models import Document, DocumentStatus
from ..config import RAG_CONFIG
from ..parsers.text_to_markdown_parser import TextToMarkdownParser
from ..parsers.pdf_vl_parser import PDFVLParser


class TextParsingService:
    """文本解析服务类"""
    
    # 并发控制
    MAX_CONCURRENT_FILES = 3  # 最多同时处理3个文件
    MAX_CONCURRENT_PDF_PAGES = 3  # 每个PDF文件最多3个页码并发
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.temp_dir = Path(RAG_CONFIG["storage"]["temp_dir"])
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_vl_parser = PDFVLParser()
        
        # 并发控制
        self._file_semaphore = threading.Semaphore(self.MAX_CONCURRENT_FILES)
        self._pdf_page_semaphore = threading.Semaphore(self.MAX_CONCURRENT_PDF_PAGES)
        self._parsing_queue = queue.Queue()
        self._active_parsing = {}  # document_id -> thread
    
    def parse_document_async(
        self, 
        document: Document,
        on_progress: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        异步解析文档
        输入:
          - document: Document 对象
          - on_progress: 进度回调函数 (document_id, current_page, total_pages)
        """
        def _parse():
            try:
                self._file_semaphore.acquire()
                try:
                    self._parse_document(document, on_progress)
                finally:
                    self._file_semaphore.release()
            finally:
                if document.id in self._active_parsing:
                    del self._active_parsing[document.id]
        
        thread = threading.Thread(target=_parse, daemon=True)
        self._active_parsing[document.id] = thread
        thread.start()
    
    def _parse_document(
        self, 
        document: Document,
        on_progress: Optional[Callable[[str, int, int], None]] = None
    ):
        """解析文档（内部方法）"""
        try:
            print(f"[TextParsingService] 开始解析文档: {document.id}, 类型: {document.file_type}")
            
            file_ext = document.file_type.lower()
            file_path = Path(document.file_path)
            
            if not file_path.exists():
                print(f"[TextParsingService] 文件不存在: {file_path}")
                return
            
            # PDF 文件：使用 VL 大模型解析
            if file_ext == 'pdf':
                self._parse_pdf_document(document, on_progress)
            # 其他文件：使用文本转 Markdown 解析器
            else:
                self._parse_other_document(document, on_progress)
            
            print(f"[TextParsingService] 文档解析完成: {document.id}")
        except Exception as e:
            print(f"[TextParsingService] 解析文档失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_pdf_document(
        self, 
        document: Document,
        on_progress: Optional[Callable[[str, int, int], None]] = None
    ):
        """解析 PDF 文档（使用 VL 大模型）"""
        try:
            # 等待图片转换完成（最多等待60秒）
            max_wait = 60
            wait_interval = 2
            waited = 0
            total_pages = 0
            
            while waited < max_wait:
                # 获取总页数
                doc = self.db.get_document(document.id)
                if doc:
                    total_pages = doc.total_pages
                    if total_pages == 0:
                        # 尝试从数据库获取页面列表
                        pages = self.db.list_pages(document.id)
                        total_pages = len(pages)
                
                if total_pages > 0:
                    break
                
                print(f"[TextParsingService] 等待图片转换完成... ({waited}/{max_wait}秒)")
                time.sleep(wait_interval)
                waited += wait_interval
            
            if total_pages == 0:
                print(f"[TextParsingService] PDF 文档无页面或图片转换超时: {document.id}")
                return
            
            print(f"[TextParsingService] 开始解析 PDF，共 {total_pages} 页: {document.id}")
            
            # 使用线程池并发处理页面（最多3个并发）
            with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_PDF_PAGES) as executor:
                futures = {}
                
                for page_num in range(1, total_pages + 1):
                    future = executor.submit(
                        self._parse_pdf_page,
                        document.id,
                        str(document.file_path),
                        page_num
                    )
                    futures[future] = page_num
                
                # 等待所有页面完成
                completed = 0
                for future in as_completed(futures):
                    page_num = futures[future]
                    try:
                        future.result()
                        completed += 1
                        if on_progress:
                            on_progress(document.id, completed, total_pages)
                    except Exception as e:
                        print(f"[TextParsingService] 解析第 {page_num} 页失败: {e}")
            
            print(f"[TextParsingService] PDF 解析完成: {document.id}, 共 {completed}/{total_pages} 页")
            
            # 检查文档状态，如果图片转换也完成了，更新状态为 completed
            doc = self.db.get_document(document.id)
            if doc:
                # 检查图片转换是否完成（是否有页面图片）
                pages = self.db.list_pages(document.id)
                if len(pages) > 0:
                    # 图片转换已完成，解析也完成，更新状态为 completed
                    if doc.status == DocumentStatus.PROCESSING:
                        from datetime import datetime
                        doc.status = DocumentStatus.COMPLETED
                        doc.parsed_at = datetime.now()
                        doc.updated_at = datetime.now()
                        self.db.update_document(doc)
                        print(f"[TextParsingService] ✅ PDF文档处理完成（图片+解析），状态已更新为 completed: {document.id}")
                else:
                    # 图片转换还在进行中，保持 processing 状态
                    # 图片转换完成后会更新状态
                    print(f"[TextParsingService] PDF解析完成，等待图片转换完成: {document.id}")
        except Exception as e:
            print(f"[TextParsingService] PDF 解析失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_pdf_page(self, document_id: str, pdf_path: str, page_number: int):
        """解析 PDF 单页"""
        try:
            print(f"[TextParsingService] 开始解析 PDF 第 {page_number} 页: {document_id}")
            
            # 使用 VL 解析器流式解析
            content_parts = []
            for chunk in self.pdf_vl_parser.parse_page_stream(pdf_path, page_number):
                # chunk 已经在 pdf_vl_parser 中清理和去重过了，直接使用
                if chunk and chunk.strip():
                    content_parts.append(chunk)
            
            content = "".join(content_parts)
            
            # 再次清理：使用PDFVLParser的清理方法（双重保险，处理可能的重复）
            if content:
                content = self.pdf_vl_parser._clean_ai_output(content)
            
            # 最终去重：移除重复的段落，但保留换行和段落分隔
            if content:
                lines = content.split('\n')
                seen = set()
                unique_lines = []
                prev_was_empty = False
                
                for line in lines:
                    line_stripped = line.strip()
                    
                    # 处理空行：保留段落分隔，但避免连续多个空行
                    if not line_stripped:
                        if not prev_was_empty and unique_lines:
                            # 如果前一行不是空行，且列表不为空，添加一个空行作为段落分隔
                            unique_lines.append('')
                            prev_was_empty = True
                        # 如果前一行已经是空行，跳过（避免连续多个空行）
                        continue
                    
                    prev_was_empty = False
                    
                    # 处理非空行：去重
                    if line_stripped not in seen:
                        seen.add(line_stripped)
                        unique_lines.append(line)
                
                # 合并为文本，移除开头和结尾的空白，但保留中间的换行
                content = '\n'.join(unique_lines).strip()
            
            # 保存到数据库
            if content.strip():
                self.db.create_parsed_text(document_id, content, page_number)
                print(f"[TextParsingService] 成功解析并保存第 {page_number} 页")
        except Exception as e:
            print(f"[TextParsingService] 解析 PDF 第 {page_number} 页失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_other_document(
        self, 
        document: Document,
        on_progress: Optional[Callable[[str, int, int], None]] = None
    ):
        """解析其他格式文档（doc/docx/txt/json/excel/md）- 使用本地规则解析，不调用大模型"""
        try:
            file_ext = document.file_type.lower()
            file_path = str(document.file_path)
            
            print(f"[TextParsingService] 使用本地规则解析非PDF文档: {document.id}, 类型: {file_ext}")
            
            # 使用本地规则解析（TextToMarkdownParser），不调用大模型
            markdown_content = TextToMarkdownParser.parse_to_markdown(
                file_path, 
                file_ext,
                temp_dir=self.temp_dir
            )
            
            # 保存到数据库（单页，page_number=None）
            if markdown_content and markdown_content.strip():
                # 确保解析结果保存到数据库
                self.db.create_parsed_text(document.id, markdown_content, page_number=None)
                print(f"[TextParsingService] ✅ 成功解析并保存文档到数据库: {document.id}, 内容长度: {len(markdown_content)}")
                
                # 更新文档状态：检查图片转换是否完成
                doc = self.db.get_document(document.id)
                if doc:
                    # 检查是否有页面图片（图片转换是否完成）
                    pages = self.db.list_pages(document.id)
                    
                    # 如果图片转换已完成，更新状态为 completed
                    if len(pages) > 0:
                        if doc.status == DocumentStatus.PROCESSING:
                            from datetime import datetime
                            doc.status = DocumentStatus.COMPLETED
                            doc.parsed_at = datetime.now()
                            doc.updated_at = datetime.now()
                            self.db.update_document(doc)
                            print(f"[TextParsingService] ✅ 文档处理完成（图片+解析），状态已更新为 completed: {document.id}")
                    else:
                        # 图片转换还在进行中，但解析已完成，保持 processing 状态
                        # 图片转换完成后会更新状态
                        print(f"[TextParsingService] 解析完成，等待图片转换完成: {document.id}")
                
                if on_progress:
                    on_progress(document.id, 1, 1)
            else:
                print(f"[TextParsingService] ⚠️ 解析结果为空: {document.id}")
                # 解析结果为空，标记为失败
                doc = self.db.get_document(document.id)
                if doc:
                    doc.status = DocumentStatus.FAILED
                    self.db.update_document(doc)
        except Exception as e:
            print(f"[TextParsingService] ❌ 解析文档失败: {e}")
            import traceback
            traceback.print_exc()
            # 解析失败，更新状态
            try:
                doc = self.db.get_document(document.id)
                if doc:
                    doc.status = DocumentStatus.FAILED
                    self.db.update_document(doc)
            except:
                pass
    
    def get_parsed_text(self, document_id: str, page_number: Optional[int] = None) -> Optional[str]:
        """获取解析文本"""
        return self.db.get_parsed_text(document_id, page_number)
    
    def list_parsed_text_pages(self, document_id: str) -> List[Dict[str, Any]]:
        """获取文档的所有解析文本页面"""
        return self.db.list_parsed_text_pages(document_id)

