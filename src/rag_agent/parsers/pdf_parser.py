"""
PDF 解析器
将 PDF 文件转换为图片（按页）
"""
import io
from pathlib import Path
from typing import Dict, Any, Optional, List
from PIL import Image
import fitz  # PyMuPDF

from .base_parser import BaseParser


class PDFParser(BaseParser):
    """PDF 解析器"""
    
    def __init__(self, pages_dir: str, dpi: int = 150):
        """
        初始化 PDF 解析器
        参数:
          - pages_dir: 页面图片存储目录
          - dpi: 图片分辨率（默认 150）
        """
        self.pages_dir = Path(pages_dir)
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        解析 PDF 文档
        输入: file_path - PDF 文件路径
        输出: {
            "success": bool,
            "content": str,  # 解析后的文本内容
            "pages": List[Dict],  # 页面信息列表
            "metadata": Dict  # 文档元数据
        }
        """
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            pages_info = []
            full_text = []
            
            for page_num in range(total_pages):
                page = doc[page_num]
                # 提取文本
                text = page.get_text()
                full_text.append(text)
                
                pages_info.append({
                    "page_number": page_num + 1,
                    "text": text,
                    "width": page.rect.width,
                    "height": page.rect.height
                })
            
            # 提取元数据
            metadata = doc.metadata
            
            doc.close()
            
            return {
                "success": True,
                "content": "\n\n".join(full_text),
                "pages": pages_info,
                "metadata": metadata,
                "total_pages": total_pages
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": "",
                "pages": [],
                "metadata": {}
            }
    
    def convert_to_images(
        self, 
        file_path: str, 
        document_id: str,
        format: str = 'png'
    ) -> List[Dict[str, Any]]:
        """
        将 PDF 转换为图片（按页）
        输入:
          - file_path: PDF 文件路径
          - document_id: 文档ID
          - format: 图片格式（png 或 jpg）
        输出: 页面图片信息列表
        """
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            pages_info = []
            
            # 创建文档专用目录
            doc_pages_dir = self.pages_dir / document_id
            doc_pages_dir.mkdir(parents=True, exist_ok=True)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                
                # 设置缩放比例（根据 DPI）
                zoom = self.dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                
                # 渲染页面为图片
                pix = page.get_pixmap(matrix=mat)
                
                # 保存图片
                image_filename = f"page_{page_num + 1:04d}.{format}"
                image_path = doc_pages_dir / image_filename
                
                if format.lower() == 'jpg' or format.lower() == 'jpeg':
                    pix.save(str(image_path), output="jpeg", jpg_quality=95)
                else:
                    pix.save(str(image_path), output="png")
                
                pages_info.append({
                    "page_number": page_num + 1,
                    "image_path": str(image_path),
                    "width": pix.width,
                    "height": pix.height,
                    "format": format
                })
            
            doc.close()
            return pages_info
        except Exception as e:
            print(f"[PDFParser] 转换图片失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_page_content(
        self, 
        file_path: str, 
        page_number: int,
        format: str = 'image/png'
    ) -> Optional[bytes]:
        """
        获取指定页面内容
        输入:
          - file_path: 文件路径
          - page_number: 页码（从1开始）
          - format: 返回格式（text, image/png, image/jpeg）
        输出: 页面内容（bytes）或 None
        """
        try:
            doc = fitz.open(file_path)
            if page_number < 1 or page_number > len(doc):
                doc.close()
                return None
            
            page = doc[page_number - 1]
            
            if format.startswith('image/'):
                # 返回图片
                zoom = self.dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                img_bytes = pix.tobytes(format.split('/')[1])
                doc.close()
                return img_bytes
            else:
                # 返回文本
                text = page.get_text()
                doc.close()
                return text.encode('utf-8')
        except Exception as e:
            print(f"[PDFParser] 获取页面内容失败: {e}")
            return None
    
    def get_total_pages(self, file_path: str) -> int:
        """
        获取文档总页数
        输入: file_path
        输出: 总页数
        """
        try:
            doc = fitz.open(file_path)
            total = len(doc)
            doc.close()
            return total
        except Exception as e:
            print(f"[PDFParser] 获取总页数失败: {e}")
            return 0

