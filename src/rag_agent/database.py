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
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_document_id ON parsing_tasks(document_id)')
        
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
        # TODO: 实现文档更新
        pass
    
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
    
    # ==================== Chunk 操作 ====================
    
    def create_chunk(self, chunk: Chunk) -> bool:
        """创建切片记录"""
        # TODO: 实现切片创建
        pass
    
    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """获取切片"""
        # TODO: 实现切片查询
        pass
    
    def list_chunks(
        self,
        document_id: str,
        status: Optional[ChunkStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Chunk], int]:
        """列出切片（分页）"""
        # TODO: 实现分页查询
        pass
    
    def update_chunk(self, chunk: Chunk) -> bool:
        """更新切片"""
        # TODO: 实现切片更新
        pass
    
    def delete_chunk(self, chunk_id: str) -> bool:
        """删除切片"""
        # TODO: 实现切片删除
        pass
    
    def count_chunks(self, document_id: str, status: Optional[ChunkStatus] = None) -> int:
        """统计切片数量"""
        # TODO: 实现统计
        pass
    
    # ==================== ParsingTask 操作 ====================
    
    def create_task(self, task: ParsingTask) -> bool:
        """创建解析任务"""
        # TODO: 实现任务创建
        pass
    
    def get_task(self, task_id: str) -> Optional[ParsingTask]:
        """获取任务"""
        # TODO: 实现任务查询
        pass
    
    def update_task(self, task: ParsingTask) -> bool:
        """更新任务"""
        # TODO: 实现任务更新
        pass

