"""
数据库操作层
使用 SQLite 存储文档、切片、任务等数据
"""
import sqlite3
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
from .config import RAG_CONFIG
from .models import Document, Chunk, ParsingTask, DocumentStatus, ChunkStatus, TaskStatus


class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or RAG_CONFIG["database"]["path"]
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 创建 documents 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
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
                metadata TEXT
            )
        ''')
        
        # 创建 chunks 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                source_page INTEGER NOT NULL,
                start_char INTEGER,
                end_char INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                embedding TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        ''')
        
        # 创建 parsing_tasks 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parsing_tasks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress REAL DEFAULT 0.0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        ''')
        
        # 创建 document_pages 表（存储页面图片信息）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_pages (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                format TEXT DEFAULT 'png',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                UNIQUE(document_id, page_number)
            )
        ''')
        
        # 创建 parsed_text 表（存储解析后的文本）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parsed_text (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                page_number INTEGER,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                UNIQUE(document_id, page_number)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_document_id ON parsing_tasks(document_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pages_document_id ON document_pages(document_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pages_doc_page ON document_pages(document_id, page_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_parsed_text_document_id ON parsed_text(document_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_parsed_text_doc_page ON parsed_text(document_id, page_number)')
        
        conn.commit()
        conn.close()
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # 启用外键约束（必须在每个连接上启用）
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
    # ==================== Document 操作 ====================
    
    def create_document(self, document: Document) -> bool:
        """创建文档记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO documents (id, name, file_path, file_size, file_type, status, total_pages, chunks_count, created_at, updated_at, parsed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                document.id, document.name, document.file_path, document.file_size,
                document.file_type, document.status.value, document.total_pages,
                document.chunks_count, document.created_at, document.updated_at,
                document.parsed_at, json.dumps(document.metadata, ensure_ascii=False)
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"创建文档失败: {e}")
            return False
        finally:
            conn.close()
    
    def get_document(self, document_id: str) -> Optional[Document]:
        """获取文档"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_document(row)
            return None
        finally:
            conn.close()
    
    def list_documents(
        self,
        status: Optional[DocumentStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Document], int]:
        """列出文档（分页）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            offset = (page - 1) * page_size
            if status:
                cursor.execute('SELECT COUNT(*) FROM documents WHERE status = ?', (status.value,))
                total = cursor.fetchone()[0]
                cursor.execute('''
                    SELECT * FROM documents WHERE status = ? 
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                ''', (status.value, page_size, offset))
            else:
                cursor.execute('SELECT COUNT(*) FROM documents')
                total = cursor.fetchone()[0]
                cursor.execute('SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?', (page_size, offset))
            
            documents = [self._row_to_document(row) for row in cursor.fetchall()]
            return documents, total
        finally:
            conn.close()
    
    def _row_to_document(self, row) -> Document:
        """将数据库行转换为 Document 对象"""
        return Document(
            id=row['id'],
            name=row['name'],
            file_path=row['file_path'],
            file_size=row['file_size'],
            file_type=row['file_type'],
            status=DocumentStatus(row['status']),
            total_pages=row['total_pages'],
            chunks_count=row['chunks_count'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
            parsed_at=datetime.fromisoformat(row['parsed_at']) if row['parsed_at'] else None,
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )
    
    def update_document(self, document: Document) -> bool:
        """更新文档"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE documents SET
                    name = ?, file_path = ?, file_size = ?, file_type = ?,
                    status = ?, total_pages = ?, chunks_count = ?,
                    updated_at = ?, parsed_at = ?, metadata = ?
                WHERE id = ?
            ''', (
                document.name, document.file_path, document.file_size, document.file_type,
                document.status.value, document.total_pages, document.chunks_count,
                document.updated_at, document.parsed_at, json.dumps(document.metadata, ensure_ascii=False),
                document.id
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"更新文档失败: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def delete_document(self, document_id: str) -> bool:
        """删除文档（级联删除相关切片和任务）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 启用外键约束（确保级联删除生效）
            cursor.execute('PRAGMA foreign_keys = ON')
            # 验证外键约束是否启用
            cursor.execute('PRAGMA foreign_keys')
            fk_enabled = cursor.fetchone()[0]
            print(f"[Database] 外键约束状态: {fk_enabled}")
            
            # 先手动删除相关切片和任务（如果外键约束未生效）
            try:
                cursor.execute('DELETE FROM chunks WHERE document_id = ?', (document_id,))
                chunks_deleted = cursor.rowcount
                print(f"[Database] 删除相关切片: {chunks_deleted} 条")
            except Exception as e:
                print(f"[Database] 删除切片时出错（可能不存在）: {e}")
            
            try:
                cursor.execute('DELETE FROM parsing_tasks WHERE document_id = ?', (document_id,))
                tasks_deleted = cursor.rowcount
                print(f"[Database] 删除相关任务: {tasks_deleted} 条")
            except Exception as e:
                print(f"[Database] 删除任务时出错（可能不存在）: {e}")
            
            # 删除文档记录
            cursor.execute('DELETE FROM documents WHERE id = ?', (document_id,))
            deleted = cursor.rowcount > 0
            
            if deleted:
                conn.commit()
                print(f"[Database] 成功删除文档: {document_id}，已提交事务")
            else:
                conn.rollback()
                print(f"[Database] 文档不存在: {document_id}，已回滚事务")
            
            return deleted
        except Exception as e:
            print(f"[Database] 删除文档失败: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()
    
    # ==================== Document Pages 操作 ====================
    
    def create_page(self, document_id: str, page_number: int, image_path: str, 
                    width: Optional[int] = None, height: Optional[int] = None, 
                    format: str = 'png') -> bool:
        """创建页面图片记录"""
        import uuid
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            page_id = f"page-{uuid.uuid4().hex[:12]}"
            cursor.execute('''
                INSERT OR REPLACE INTO document_pages 
                (id, document_id, page_number, image_path, width, height, format)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (page_id, document_id, page_number, image_path, width, height, format))
            conn.commit()
            return True
        except Exception as e:
            print(f"创建页面记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_page(self, document_id: str, page_number: int) -> Optional[Dict[str, Any]]:
        """获取页面信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM document_pages 
                WHERE document_id = ? AND page_number = ?
            ''', (document_id, page_number))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
    
    def list_pages(self, document_id: str) -> List[Dict[str, Any]]:
        """获取文档的所有页面"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM document_pages 
                WHERE document_id = ?
                ORDER BY page_number ASC
            ''', (document_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def delete_pages(self, document_id: str) -> bool:
        """删除文档的所有页面（级联删除时自动执行）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM document_pages WHERE document_id = ?', (document_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"删除页面记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    # ==================== Chunk 操作 ====================
    
    def create_chunk(self, chunk: Chunk) -> bool:
        """创建切片记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO chunks (
                    id, document_id, content, tags, source_page,
                    start_char, end_char, status,
                    created_at, updated_at, confirmed_at, embedding
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.content,
                    json.dumps(chunk.tags, ensure_ascii=False) if chunk.tags else None,
                    chunk.source_page,
                    chunk.start_char,
                    chunk.end_char,
                    chunk.status.value,
                    chunk.created_at,
                    chunk.updated_at,
                    chunk.confirmed_at,
                    json.dumps(chunk.embedding) if chunk.embedding is not None else None,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"创建切片失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def _row_to_chunk(self, row) -> Chunk:
        """将数据库行转换为 Chunk 对象"""
        return Chunk(
            id=row["id"],
            document_id=row["document_id"],
            content=row["content"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source_page=row["source_page"],
            start_char=row["start_char"],
            end_char=row["end_char"],
            status=ChunkStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
            confirmed_at=datetime.fromisoformat(row["confirmed_at"]) if row["confirmed_at"] else None,
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
        )
    
    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """获取切片"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_chunk(row)
            return None
        finally:
            conn.close()
    
    def list_chunks(
        self,
        document_id: str,
        status: Optional[ChunkStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Chunk], int]:
        """列出切片（分页）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            offset = (page - 1) * page_size
            params: Tuple[Any, ...]

            if status:
                cursor.execute(
                    "SELECT COUNT(*) FROM chunks WHERE document_id = ? AND status = ?",
                    (document_id, status.value),
                )
                total = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT * FROM chunks
                    WHERE document_id = ? AND status = ?
                    ORDER BY created_at ASC
                    LIMIT ? OFFSET ?
                    """,
                    (document_id, status.value, page_size, offset),
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM chunks WHERE document_id = ?",
                    (document_id,),
                )
                total = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT * FROM chunks
                    WHERE document_id = ?
                    ORDER BY created_at ASC
                    LIMIT ? OFFSET ?
                    """,
                    (document_id, page_size, offset),
                )

            chunks = [self._row_to_chunk(row) for row in cursor.fetchall()]
            return chunks, total
        finally:
            conn.close()
    
    def update_chunk(self, chunk: Chunk) -> bool:
        """更新切片"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE chunks SET
                    content = ?,
                    tags = ?,
                    source_page = ?,
                    start_char = ?,
                    end_char = ?,
                    status = ?,
                    updated_at = ?,
                    confirmed_at = ?,
                    embedding = ?
                WHERE id = ?
                """,
                (
                    chunk.content,
                    json.dumps(chunk.tags, ensure_ascii=False) if chunk.tags else None,
                    chunk.source_page,
                    chunk.start_char,
                    chunk.end_char,
                    chunk.status.value,
                    chunk.updated_at,
                    chunk.confirmed_at,
                    json.dumps(chunk.embedding) if chunk.embedding is not None else None,
                    chunk.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"更新切片失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def delete_chunk(self, chunk_id: str) -> bool:
        """删除切片"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))
            deleted = cursor.rowcount > 0
            if deleted:
                conn.commit()
            else:
                conn.rollback()
            return deleted
        except Exception as e:
            print(f"删除切片失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def count_chunks(self, document_id: str, status: Optional[ChunkStatus] = None) -> int:
        """统计切片数量"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if status:
                cursor.execute(
                    "SELECT COUNT(*) FROM chunks WHERE document_id = ? AND status = ?",
                    (document_id, status.value),
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM chunks WHERE document_id = ?",
                    (document_id,),
                )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    
    # ==================== ParsingTask 操作 ====================
    
    def create_task(self, task: ParsingTask) -> bool:
        """创建解析任务"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO parsing_tasks (
                    id, document_id, status, progress,
                    error_message, created_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.document_id,
                    task.status.value,
                    task.progress,
                    task.error_message,
                    task.created_at,
                    task.completed_at,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"创建解析任务失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_task(self, task_id: str) -> Optional[ParsingTask]:
        """获取任务"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM parsing_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ParsingTask(
                id=row["id"],
                document_id=row["document_id"],
                status=TaskStatus(row["status"]),
                progress=row["progress"],
                error_message=row["error_message"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            )
        finally:
            conn.close()
    
    def update_task(self, task: ParsingTask) -> bool:
        """更新任务"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE parsing_tasks SET
                    status = ?,
                    progress = ?,
                    error_message = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    task.status.value,
                    task.progress,
                    task.error_message,
                    task.completed_at,
                    task.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"更新解析任务失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    # ==================== ParsedText 操作 ====================
    
    def create_parsed_text(self, document_id: str, content: str, page_number: Optional[int] = None) -> bool:
        """创建或更新解析文本"""
        import uuid
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            parsed_id = f"parsed-{uuid.uuid4().hex[:12]}"
            cursor.execute('''
                INSERT OR REPLACE INTO parsed_text 
                (id, document_id, page_number, content, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                parsed_id, document_id, page_number, content, datetime.now()
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"保存解析文本失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_parsed_text(self, document_id: str, page_number: Optional[int] = None) -> Optional[str]:
        """获取解析文本"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if page_number is not None:
                cursor.execute('''
                    SELECT content FROM parsed_text 
                    WHERE document_id = ? AND page_number = ?
                    ORDER BY updated_at DESC LIMIT 1
                ''', (document_id, page_number))
            else:
                # 获取所有页面的文本，按页码排序
                cursor.execute('''
                    SELECT content FROM parsed_text 
                    WHERE document_id = ?
                    ORDER BY page_number ASC
                ''', (document_id,))
            
            rows = cursor.fetchall()
            if rows:
                if page_number is not None:
                    return rows[0]['content']
                else:
                    # 合并所有页面的文本
                    return "\n\n".join([row['content'] for row in rows])
            return None
        finally:
            conn.close()
    
    def list_parsed_text_pages(self, document_id: str) -> List[Dict[str, Any]]:
        """获取文档的所有解析文本页面"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT page_number, content, updated_at 
                FROM parsed_text 
                WHERE document_id = ?
                ORDER BY page_number ASC
            ''', (document_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def delete_parsed_text(self, document_id: str) -> bool:
        """删除文档的所有解析文本"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM parsed_text WHERE document_id = ?', (document_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"删除解析文本失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

