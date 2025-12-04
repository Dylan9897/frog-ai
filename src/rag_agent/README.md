# RAG Agent 知识库管理系统

## 项目结构

```
src/rag_agent/
├── __init__.py
├── config.py              # 配置管理
├── models.py              # 数据模型定义
├── database.py            # 数据库操作（SQLite）
├── api.py                 # Flask API 路由
│
├── services/              # 业务逻辑层
│   ├── __init__.py
│   ├── document_service.py    # 文档管理服务
│   ├── parser_service.py      # 文档解析服务
│   ├── chunk_service.py       # 知识切片服务
│   └── embedding_service.py   # 向量化服务（可选）
│
├── parsers/               # 文档解析器
│   ├── __init__.py
│   ├── base_parser.py        # 基础解析器接口
│   ├── pdf_parser.py         # PDF 解析器
│   ├── docx_parser.py        # Word 解析器
│   ├── excel_parser.py       # Excel 解析器
│   └── text_parser.py        # 文本解析器
│
├── chunkers/              # 文本分块器
│   ├── __init__.py
│   ├── base_chunker.py       # 基础分块器接口
│   ├── semantic_chunker.py   # 语义分块器
│   └── rule_chunker.py       # 规则分块器
│
└── utils/                 # 工具函数
    ├── __init__.py
    ├── file_utils.py         # 文件操作工具
    └── text_utils.py         # 文本处理工具
```

## API 接口设计

### 1. 文档管理接口

#### 1.1 上传文档
- **POST** `/api/rag/documents/upload`
- **输入**:
  ```json
  {
    "file": File (multipart/form-data),
    "name": "string (可选，自定义文档名)"
  }
  ```
- **输出**:
  ```json
  {
    "success": true,
    "document": {
      "id": "doc-xxx",
      "name": "催收作业规范 V2.pdf",
      "status": "processing",
      "file_path": "/path/to/file",
      "file_size": 1024000,
      "created_at": "2024-01-01T00:00:00Z",
      "chunks_count": 0
    }
  }
  ```

#### 1.2 获取文档列表
- **GET** `/api/rag/documents`
- **查询参数**:
  - `status`: 文档状态筛选（可选：pending, processing, completed, archived）
  - `page`: 页码（默认1）
  - `page_size`: 每页数量（默认20）
- **输出**:
  ```json
  {
    "success": true,
    "documents": [
      {
        "id": "doc-xxx",
        "name": "催收作业规范 V2.pdf",
        "status": "pending",
        "status_color": "#ffb86c",
        "chunks_count": 15,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 128,
    "page": 1,
    "page_size": 20
  }
  ```

#### 1.3 获取文档详情
- **GET** `/api/rag/documents/{document_id}`
- **输出**:
  ```json
  {
    "success": true,
    "document": {
      "id": "doc-xxx",
      "name": "催收作业规范 V2.pdf",
      "status": "pending",
      "file_path": "/path/to/file",
      "file_size": 1024000,
      "total_pages": 50,
      "chunks_count": 15,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  }
  ```

#### 1.4 删除文档
- **DELETE** `/api/rag/documents/{document_id}`
- **输出**:
  ```json
  {
    "success": true,
    "message": "文档已删除"
  }
  ```

### 2. 文档解析接口

#### 2.1 获取文档页面内容（PDF预览）
- **GET** `/api/rag/documents/{document_id}/pages/{page_number}`
- **查询参数**:
  - `format`: 返回格式（image/png, text, json）
- **输出**:
  ```json
  {
    "success": true,
    "page": {
      "page_number": 3,
      "content": "base64_encoded_image 或 text_content",
      "format": "image/png",
      "width": 800,
      "height": 1200
    }
  }
  ```

#### 2.2 获取解析后的文本流
- **GET** `/api/rag/documents/{document_id}/parsed-text`
- **查询参数**:
  - `page`: 页码（可选，不传则返回全部）
- **输出**:
  ```json
  {
    "success": true,
    "parsed_text": {
      "document_id": "doc-xxx",
      "content": "清洗后的文本内容...",
      "page_number": 3,
      "cleaned_at": "2024-01-01T00:00:00Z"
    }
  }
  ```

#### 2.3 触发文档解析
- **POST** `/api/rag/documents/{document_id}/parse`
- **输入**:
  ```json
  {
    "force_reparse": false,  // 是否强制重新解析
    "parser_options": {      // 解析器选项
      "ocr_enabled": true,
      "extract_images": false
    }
  }
  ```
- **输出**:
  ```json
  {
    "success": true,
    "task_id": "task-xxx",
    "status": "processing",
    "message": "文档解析任务已启动"
  }
  ```

### 3. 知识切片（Chunks）接口

#### 3.1 获取文档的知识切片列表
- **GET** `/api/rag/documents/{document_id}/chunks`
- **查询参数**:
  - `status`: 切片状态（pending, confirmed, archived）
  - `page`: 页码
  - `page_size`: 每页数量
- **输出**:
  ```json
  {
    "success": true,
    "chunks": [
      {
        "id": "CHUNK-001",
        "document_id": "doc-xxx",
        "content": "催收作业人员不得对客户使用...",
        "tags": ["# 催收规范", "# A级违规"],
        "source_page": 3,
        "start_char": 100,
        "end_char": 500,
        "status": "pending",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20
  }
  ```

#### 3.2 创建知识切片
- **POST** `/api/rag/documents/{document_id}/chunks`
- **输入**:
  ```json
  {
    "content": "切片内容文本",
    "source_page": 3,
    "start_char": 100,
    "end_char": 500,
    "tags": ["# 催收规范", "# A级违规"]
  }
  ```
- **输出**:
  ```json
  {
    "success": true,
    "chunk": {
      "id": "CHUNK-001",
      "document_id": "doc-xxx",
      "content": "切片内容文本",
      "tags": ["# 催收规范", "# A级违规"],
      "source_page": 3,
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z"
    }
  }
  ```

#### 3.3 更新知识切片
- **PUT** `/api/rag/chunks/{chunk_id}`
- **输入**:
  ```json
  {
    "content": "更新后的内容",
    "tags": ["# 新标签"],
    "source_page": 4
  }
  ```
- **输出**:
  ```json
  {
    "success": true,
    "chunk": {
      "id": "CHUNK-001",
      "content": "更新后的内容",
      "tags": ["# 新标签"],
      "updated_at": "2024-01-01T00:00:00Z"
    }
  }
  ```

#### 3.4 删除知识切片
- **DELETE** `/api/rag/chunks/{chunk_id}`
- **输出**:
  ```json
  {
    "success": true,
    "message": "切片已删除"
  }
  ```

#### 3.5 确认切片入库
- **POST** `/api/rag/chunks/{chunk_id}/confirm`
- **输入**:
  ```json
  {
    "status": "confirmed"  // 或 "archived"
  }
  ```
- **输出**:
  ```json
  {
    "success": true,
    "chunk": {
      "id": "CHUNK-001",
      "status": "confirmed",
      "confirmed_at": "2024-01-01T00:00:00Z"
    }
  }
  ```

#### 3.6 自动分块（从文档生成切片）
- **POST** `/api/rag/documents/{document_id}/auto-chunk`
- **输入**:
  ```json
  {
    "chunker_type": "semantic",  // 或 "rule"
    "chunk_size": 500,           // 每个切片的最大字符数
    "chunk_overlap": 50,         // 切片重叠字符数
    "min_chunk_size": 100        // 最小切片大小
  }
  ```
- **输出**:
  ```json
  {
    "success": true,
    "task_id": "task-xxx",
    "chunks_created": 15,
    "message": "自动分块任务已启动"
  }
  ```

## 数据模型

### Document（文档）
```python
{
    "id": str,              # 文档ID
    "name": str,            # 文档名称
    "file_path": str,       # 文件存储路径
    "file_size": int,       # 文件大小（字节）
    "file_type": str,       # 文件类型（pdf, docx, xlsx等）
    "status": str,          # 状态：pending, processing, completed, archived
    "total_pages": int,     # 总页数
    "chunks_count": int,    # 切片数量
    "created_at": datetime,
    "updated_at": datetime,
    "parsed_at": datetime,  # 解析完成时间
    "metadata": dict        # 额外元数据
}
```

### Chunk（知识切片）
```python
{
    "id": str,              # 切片ID
    "document_id": str,     # 所属文档ID
    "content": str,         # 切片内容
    "tags": List[str],      # 标签列表
    "source_page": int,     # 来源页码
    "start_char": int,      # 在原文中的起始字符位置
    "end_char": int,        # 在原文中的结束字符位置
    "status": str,          # 状态：pending, confirmed, archived
    "created_at": datetime,
    "updated_at": datetime,
    "confirmed_at": datetime,  # 确认入库时间
    "embedding": List[float]   # 向量嵌入（可选）
}
```

### ParsingTask（解析任务）
```python
{
    "id": str,              # 任务ID
    "document_id": str,     # 文档ID
    "status": str,          # 状态：pending, processing, completed, failed
    "progress": float,      # 进度（0-100）
    "error_message": str,   # 错误信息
    "created_at": datetime,
    "completed_at": datetime
}
```

## 服务层接口设计

### DocumentService
```python
class DocumentService:
    def upload_document(file, name=None) -> Document
    def get_document(document_id) -> Document
    def list_documents(status=None, page=1, page_size=20) -> List[Document]
    def delete_document(document_id) -> bool
    def update_document_status(document_id, status) -> Document
```

### ParserService
```python
class ParserService:
    def parse_document(document_id, options=None) -> ParsingTask
    def get_parsed_text(document_id, page=None) -> str
    def get_page_content(document_id, page_number, format='image') -> bytes
    def get_parsing_status(task_id) -> ParsingTask
```

### ChunkService
```python
class ChunkService:
    def create_chunk(document_id, content, source_page, tags=None) -> Chunk
    def get_chunk(chunk_id) -> Chunk
    def list_chunks(document_id, status=None, page=1, page_size=20) -> List[Chunk]
    def update_chunk(chunk_id, content=None, tags=None, source_page=None) -> Chunk
    def delete_chunk(chunk_id) -> bool
    def confirm_chunk(chunk_id) -> Chunk
    def auto_chunk(document_id, options) -> List[Chunk]
```

## 数据库设计

### documents 表
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total_pages INTEGER DEFAULT 0,
    chunks_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parsed_at TIMESTAMP,
    metadata TEXT  -- JSON 字符串
);
```

### chunks 表
```sql
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,  -- JSON 数组字符串
    source_page INTEGER NOT NULL,
    start_char INTEGER,
    end_char INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    embedding TEXT,  -- JSON 数组字符串（向量）
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);
```

### parsing_tasks 表
```sql
CREATE TABLE parsing_tasks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL DEFAULT 0.0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);
```

## 配置项

```python
# config.py
RAG_CONFIG = {
    "storage": {
        "documents_dir": "data/rag_agent/documents",
        "parsed_text_dir": "data/rag_agent/parsed",
        "embeddings_dir": "data/rag_agent/embeddings"
    },
    "parsing": {
        "supported_formats": ["pdf", "docx", "xlsx", "txt", "md"],
        "max_file_size": 100 * 1024 * 1024,  # 100MB
        "ocr_enabled": True
    },
    "chunking": {
        "default_chunk_size": 500,
        "default_chunk_overlap": 50,
        "min_chunk_size": 100
    },
    "database": {
        "path": "data/rag_agent/rag_agent.db"
    }
}
```

