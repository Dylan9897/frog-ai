"""
清空所有上传的文档
包括数据库记录和物理文件
"""
import sys
import sqlite3
import shutil
from pathlib import Path

# 项目根目录
project_root = Path(__file__).parent
data_dir = project_root / "data" / "rag_agent"

# 数据库路径
db_path = data_dir / "rag_agent.db"

# 存储目录
storage_dirs = {
    "documents": data_dir / "documents",
    "pages": data_dir / "pages",
    "parsed": data_dir / "parsed",
}

def clear_all_documents():
    """清空所有文档"""
    print("=" * 60)
    print("开始清空所有文档...")
    print("=" * 60)
    
    # 1. 连接数据库，获取所有文档
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 获取所有文档
    cursor.execute("SELECT id, name, file_path FROM documents")
    documents = cursor.fetchall()
    total = len(documents)
    
    print(f"\n找到 {total} 个文档，开始删除...")
    
    # 2. 删除每个文档的物理文件
    success_count = 0
    fail_count = 0
    
    for doc_id, doc_name, file_path in documents:
        print(f"\n正在删除: {doc_name} (ID: {doc_id})")
        
        # 删除物理文件
        if file_path:
            file_obj = Path(file_path)
            if file_obj.exists():
                try:
                    file_obj.unlink()
                    print(f"  [OK] 删除文件: {file_path}")
                except Exception as e:
                    print(f"  [FAIL] 删除文件失败: {e}")
        
        # 删除页面图片目录
        pages_dir = storage_dirs["pages"] / doc_id
        if pages_dir.exists():
            try:
                shutil.rmtree(pages_dir)
                print(f"  [OK] 删除页面目录: {pages_dir}")
            except Exception as e:
                print(f"  [FAIL] 删除页面目录失败: {e}")
        
        success_count += 1
    
    # 3. 清空数据库表
    print("\n" + "=" * 60)
    print("清空数据库...")
    print("=" * 60)
    
    try:
        # 启用外键约束
        cursor.execute('PRAGMA foreign_keys = ON')
        
        # 删除所有文档（级联删除相关数据）
        cursor.execute("DELETE FROM documents")
        print(f"[OK] 已删除所有文档记录")
        
        # 清空其他表（以防万一）
        cursor.execute("DELETE FROM chunks")
        cursor.execute("DELETE FROM parsing_tasks")
        cursor.execute("DELETE FROM document_pages")
        cursor.execute("DELETE FROM parsed_text")
        print(f"[OK] 已清空所有相关表")
        
        conn.commit()
    except Exception as e:
        print(f"[FAIL] 清空数据库失败: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    # 4. 清空存储目录
    print("\n" + "=" * 60)
    print("清空存储目录...")
    print("=" * 60)
    
    for name, dir_path in storage_dirs.items():
        if dir_path.exists():
            try:
                # 删除目录中的所有内容，但保留目录本身
                for item in dir_path.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                        print(f"[OK] 删除目录: {item.name}")
                    else:
                        item.unlink()
                        print(f"[OK] 删除文件: {item.name}")
            except Exception as e:
                print(f"[FAIL] 清空目录失败 {name}: {e}")
        else:
            print(f"目录不存在，跳过: {name}")
    
    # 5. 总结
    print("\n" + "=" * 60)
    print("清空完成！")
    print("=" * 60)
    print(f"成功处理: {success_count} 个文档")
    print(f"处理失败: {fail_count} 个文档")
    print(f"总计: {total} 个文档")
    print("\n提示: 数据库记录已删除，存储目录已清空。")

if __name__ == "__main__":
    try:
        clear_all_documents()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

