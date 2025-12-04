"""
RAG Agent 配置管理
"""
import os
from pathlib import Path

# 基础路径
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "rag_agent"

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

# RAG Agent 配置
RAG_CONFIG = {
    "storage": {
        "documents_dir": str(DATA_DIR / "documents"),
        "parsed_text_dir": str(DATA_DIR / "parsed"),
        "embeddings_dir": str(DATA_DIR / "embeddings"),
        "temp_dir": str(DATA_DIR / "temp"),
        "pages_dir": str(DATA_DIR / "pages")  # 页面图片存储目录
    },
    "parsing": {
        "supported_formats": ["pdf", "docx", "xlsx", "xls", "txt", "md", "json"],
        "max_file_size": 100 * 1024 * 1024,  # 100MB
        "ocr_enabled": True,
        "extract_images": False
    },
    "chunking": {
        "default_chunk_size": 500,
        "default_chunk_overlap": 50,
        "min_chunk_size": 100,
        "default_chunker": "semantic"  # semantic 或 rule
    },
    "database": {
        "path": str(DATA_DIR / "rag_agent.db")
    },
    "api": {
        "max_upload_size": 100 * 1024 * 1024,  # 100MB
        "default_page_size": 20,
        "max_page_size": 100
    }
}

# 文档状态枚举
DOCUMENT_STATUS = {
    "PENDING": "pending",        # 待处理
    "PROCESSING": "processing",  # 处理中
    "COMPLETED": "completed",    # 已完成
    "ARCHIVED": "archived",      # 已归档
    "FAILED": "failed"           # 处理失败
}

# 切片状态枚举
CHUNK_STATUS = {
    "PENDING": "pending",        # 待审核
    "CONFIRMED": "confirmed",    # 已确认入库
    "ARCHIVED": "archived"       # 已归档
}

# 解析任务状态枚举
TASK_STATUS = {
    "PENDING": "pending",
    "PROCESSING": "processing",
    "COMPLETED": "completed",
    "FAILED": "failed"
}

# 初始化存储目录
for dir_path in RAG_CONFIG["storage"].values():
    Path(dir_path).mkdir(parents=True, exist_ok=True)

