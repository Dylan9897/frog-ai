# encoding : utf-8 -*-
# @author  : 冬瓜
# @mail    : dylan_han@126.com
# @Time    : 2025/11/20 17:00

import os
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional
from openpyxl.utils import get_column_letter


def db_to_excel(db_path: str, excel_path: Optional[str] = None, sheet_name: str = "沙盒记录") -> bool:
    """
    将 SQLite 数据库文件转换为 Excel 文件
    
    :param db_path: SQLite 数据库文件路径
    :param excel_path: 输出的 Excel 文件路径（可选，默认为数据库文件同目录下的同名 .xlsx 文件）
    :param sheet_name: Excel 工作表名称（默认：沙盒记录）
    :return: 转换是否成功
    """
    try:
        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            print(f"[ERROR] 数据库文件不存在: {db_path}")
            return False
        
        # 如果没有指定 Excel 输出路径，使用默认路径
        if excel_path is None:
            base_name = os.path.splitext(os.path.basename(db_path))[0]
            db_dir = os.path.dirname(os.path.abspath(db_path))
            excel_path = os.path.join(db_dir, f"{base_name}.xlsx")
        
        # 确保输出目录存在
        excel_dir = os.path.dirname(os.path.abspath(excel_path))
        os.makedirs(excel_dir, exist_ok=True)
        
        # 连接数据库并读取数据
        conn = sqlite3.connect(db_path)
        
        # 使用 pandas 读取整个表
        query = "SELECT * FROM sandbox_records"
        df = pd.read_sql_query(query, conn)
        
        # 关闭数据库连接
        conn.close()
        
        # 检查是否有数据
        if df.empty:
            print(f"[WARNING] 数据库中没有数据，将创建空的 Excel 文件")
        else:
            print(f"[INFO] 读取到 {len(df)} 条记录")
        
        # 设置中文字段名映射（可选，用于更好的显示）
        column_mapping = {
            'id': 'ID',
            'sessionId': '会话ID',
            'file_path': '原始文件路径',
            'shortcut_path': '快捷方式路径',
            'file_type': '文件类型',
            'file_title': '文件标题',
            'summary_content': '摘要内容',
            'model_summary_index': '模型摘要索引',
            'keywords': '关键词',
            'created_at': '创建时间',
            'updated_at': '更新时间'
        }
        
        # 重命名列（如果列存在）
        df.rename(columns=column_mapping, inplace=True)
        
        # 导出到 Excel
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # 获取工作表对象以调整列宽
            worksheet = writer.sheets[sheet_name]
            
            # 自动调整列宽
            for idx, col in enumerate(df.columns, 1):
                max_length = max(
                    df[col].astype(str).map(len).max(),  # 数据最大长度
                    len(str(col))  # 列名长度
                )
                # 设置列宽（稍微宽一点以便阅读）
                adjusted_width = min(max_length + 2, 50)  # 最大宽度限制为 50
                column_letter = get_column_letter(idx)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"[SUCCESS] Excel 文件已生成: {excel_path}")
        print(f"[INFO] 共导出 {len(df)} 条记录")
        return True
        
    except sqlite3.Error as e:
        print(f"[ERROR] 数据库操作失败: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 转换失败: {e}")
        return False


def convert_default_db_to_excel(excel_path: Optional[str] = None) -> bool:
    """
    转换默认数据库文件（sandbox.db）为 Excel
    
    :param excel_path: 输出的 Excel 文件路径（可选）
    :return: 转换是否成功
    """
    # 获取默认数据库路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    default_db_path = os.path.join(current_dir, "sandbox.db")
    
    return db_to_excel(default_db_path, excel_path)


if __name__ == "__main__":
    # 示例用法
    print("=" * 50)
    print("数据库转 Excel 工具")
    print("=" * 50)
    
    # 方式1: 转换默认数据库
    print("\n[方式1] 转换默认数据库 (sandbox.db)...")
    success = convert_default_db_to_excel()
    
    if success:
        print("\n✅ 转换成功！")
    else:
        print("\n❌ 转换失败！")
    
    # 方式2: 指定数据库路径
    # print("\n[方式2] 转换指定数据库...")
    # db_path = "src/database/sandbox.db"
    # excel_path = "src/database/sandbox_export.xlsx"
    # success = db_to_excel(db_path, excel_path)
    
    print("\n" + "=" * 50)

