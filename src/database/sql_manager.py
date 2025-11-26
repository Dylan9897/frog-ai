# encoding : utf-8 -*-
# @author  : 冬瓜
# @mail    : dylan_han@126.com
# @Time    : 2025/11/19 18:19

import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any


class SandboxDatabase:
    def __init__(self, db_path: str = "sandbox.db"):
        """
        Initialize database connection
        :param db_path: SQLite database file path
        """
        self.db_path = db_path
        self.init_table()

    def init_table(self):
        """
        Initialize data table, create if not exists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create table with all required fields using English names
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS sandbox_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sessionId TEXT NOT NULL, -- unique key
            file_path TEXT NOT NULL,
            shortcut_path TEXT UNIQUE, -- shortcut path as unique key
            file_type TEXT NOT NULL,
            file_title TEXT,
            summary_content TEXT,
            model_summary_index TEXT,
            keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_sql)
        conn.commit()
        conn.close()

    def insert_by_shortcut(self, sessionId: str, file_path: str, shortcut_path: str,
                           file_type: str = None, file_title: str = None,
                           summary_content: str = None, model_summary_index: str = None,
                           keywords: str = None):
        """
        Insert data by shortcut path
        :param sessionId: Session ID
        :param file_path: Original file path
        :param shortcut_path: Shortcut path in sandbox
        :param file_type: File type
        :param file_title: File title
        :param summary_content: Summary content
        :param model_summary_index: Model summary index
        :param keywords: Keywords
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            insert_sql = """
            INSERT INTO sandbox_records 
            (sessionId, file_path, shortcut_path, file_type, file_title, summary_content, model_summary_index, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(insert_sql, (
                sessionId, file_path, shortcut_path, file_type,
                file_title, summary_content, model_summary_index, keywords
            ))
            conn.commit()
            print(f"[DB] Successfully inserted record: {shortcut_path}")
        except sqlite3.IntegrityError:
            print(f"[DB] Error: Shortcut path '{shortcut_path}' already exists")
        except Exception as e:
            print(f"[DB] Insert failed: {e}")
        finally:
            conn.close()

    def delete_by_shortcut(self, shortcut_path: str):
        """
        Delete data by shortcut path
        :param shortcut_path: Shortcut path to delete
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            delete_sql = "DELETE FROM sandbox_records WHERE shortcut_path = ?"
            cursor.execute(delete_sql, (shortcut_path,))
            affected_rows = cursor.rowcount
            conn.commit()

            if affected_rows > 0:
                print(f"[DB] Successfully deleted record: {shortcut_path}")
            else:
                print(f"[DB] No record found: {shortcut_path}")
        except Exception as e:
            print(f"[DB] Delete failed: {e}")
        finally:
            conn.close()

    def update_record(self, shortcut_path: str = None, sessionId: str = None,
                      **kwargs: Dict[str, Any]):
        """
        Update fields by shortcut path or sessionId
        :param shortcut_path: Shortcut path (higher priority)
        :param sessionId: Session ID
        :param kwargs: Field-value pairs to update
        """
        if not shortcut_path and not sessionId:
            print("[DB] Error: Must provide shortcut_path or sessionId as update condition")
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build update SQL
        update_fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['file_path', 'file_type', 'file_title', 'summary_content', 'model_summary_index', 'keywords',
                       'updated_at']:
                update_fields.append(f"{key} = ?")
                values.append(value)

        if not update_fields:
            print("[DB] Error: No valid fields to update")
            conn.close()
            return

        # Add update timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        update_sql = f"UPDATE sandbox_records SET {', '.join(update_fields)} WHERE "
        if shortcut_path:
            update_sql += "shortcut_path = ?"
            values.append(shortcut_path)
        else:
            update_sql += "sessionId = ?"
            values.append(sessionId)

        try:
            cursor.execute(update_sql, values)
            affected_rows = cursor.rowcount
            conn.commit()

            if affected_rows > 0:
                condition = f"shortcut '{shortcut_path}'" if shortcut_path else f"sessionId '{sessionId}'"
                print(f"[DB] Successfully updated {affected_rows} record(s): {condition}")
            else:
                condition = f"shortcut '{shortcut_path}'" if shortcut_path else f"sessionId '{sessionId}'"
                print(f"[DB] No matching record found: {condition}")
        except Exception as e:
            print(f"[DB] Update failed: {e}")
        finally:
            conn.close()

    def get_record_by_shortcut(self, shortcut_path: str) -> Optional[Dict[str, Any]]:
        """
        Get record by shortcut path (helper method)
        :param shortcut_path: Shortcut path to query
        :return: Record dictionary or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM sandbox_records WHERE shortcut_path = ?", (shortcut_path,))
            row = cursor.fetchone()
            if row:
                # Get column names
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"[DB] Query failed: {e}")
            return None
        finally:
            conn.close()

    def get_all_records(self) -> list:
        """
        Get all records (for debugging)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM sandbox_records")
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"[DB] Query failed: {e}")
            return []
        finally:
            conn.close()

    def search_by_summary_index(self, query_text: str, limit: int = 10) -> list:
        """
        Search records by model_summary_index using LIKE query
        
        :param query_text: Search text to match against model_summary_index
        :param limit: Maximum number of results to return
        :return: List of matching records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            search_pattern = f"%{query_text}%"
            cursor.execute(
                "SELECT * FROM sandbox_records WHERE model_summary_index LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (search_pattern, limit)
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"[DB] Search by summary index failed: {e}")
            return []
        finally:
            conn.close()

    def search_by_keywords(self, query_text: str, limit: int = 10) -> list:
        """
        Search records by keywords using LIKE query
        
        :param query_text: Search text to match against keywords
        :param limit: Maximum number of results to return
        :return: List of matching records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            search_pattern = f"%{query_text}%"
            cursor.execute(
                "SELECT * FROM sandbox_records WHERE keywords LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (search_pattern, limit)
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"[DB] Search by keywords failed: {e}")
            return []
        finally:
            conn.close()

    def search_by_text(self, query_text: str, limit: int = 10) -> list:
        """
        Search records by both model_summary_index and keywords
        
        :param query_text: Search text to match
        :param limit: Maximum number of results to return
        :return: List of matching records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            search_pattern = f"%{query_text}%"
            cursor.execute(
                """SELECT * FROM sandbox_records 
                   WHERE model_summary_index LIKE ? OR keywords LIKE ? OR file_title LIKE ?
                   ORDER BY updated_at DESC LIMIT ?""",
                (search_pattern, search_pattern, search_pattern, limit)
            )
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"[DB] Search by text failed: {e}")
            return []
        finally:
            conn.close()


# Usage example
if __name__ == "__main__":
    # Create database instance
    db = SandboxDatabase("test_sandbox.db")

    # Test insert
    db.insert_by_shortcut(
        sessionId="session_001",
        file_path="/home/user/documents/report.pdf",
        shortcut_path="../sandbox_files/report.pdf.lnk",
        file_type="PDF",
        file_title="Quarterly Report",
        summary_content="This is the summary of Q3 2023 financial report",
        model_summary_index="idx_12345",
        keywords="finance,report,Q3,2023"
    )

    # Test update
    db.update_record(
        shortcut_path="../sandbox_files/report.pdf.lnk",
        file_title="Q3 2023 Financial Report",
        keywords="finance,report,Q3,2023,updated"
    )

    # Test update by sessionId
    db.update_record(
        sessionId="session_001",
        summary_content="Updated summary content"
    )

    # Test delete
    # db.delete_by_shortcut("../sandbox_files/report.pdf.lnk")

    # View all records
    records = db.get_all_records()
    for record in records:
        print(record)



