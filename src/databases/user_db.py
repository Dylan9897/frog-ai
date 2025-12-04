"""
用户数据库操作
"""
import sqlite3
import os
import hashlib
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path
import sys

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.app_config import USERS_DB_PATH


def get_db_connection():
    """获取数据库连接"""
    Path(USERS_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(USERS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库，创建用户表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"[数据库] 用户数据库已初始化: {USERS_DB_PATH}")


def hash_password(password: str) -> str:
    """使用 SHA256 哈希密码"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash


def create_user(username: str, password: str, email: Optional[str] = None) -> Tuple[bool, str]:
    """创建新用户"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return False, "用户名已存在"
        
        if email:
            cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                conn.close()
                return False, "邮箱已被注册"
        
        password_hash = hash_password(password)
        cursor.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        
        conn.commit()
        conn.close()
        return True, "注册成功"
    except Exception as e:
        return False, f"注册失败: {str(e)}"


def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[dict], str]:
    """验证用户登录"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT id, username, email, password_hash FROM users WHERE username = ? OR email = ?',
            (username, username)
        )
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            return False, None, "用户名或密码错误"
        
        if not verify_password(password, user_row['password_hash']):
            conn.close()
            return False, None, "用户名或密码错误"
        
        cursor.execute(
            'UPDATE users SET last_login = ? WHERE id = ?',
            (datetime.now().isoformat(), user_row['id'])
        )
        conn.commit()
        
        user_info = {
            'id': user_row['id'],
            'username': user_row['username'],
            'email': user_row['email']
        }
        
        conn.close()
        return True, user_info, "登录成功"
    except Exception as e:
        return False, None, f"登录失败: {str(e)}"


def get_user_by_id(user_id: int) -> Optional[dict]:
    """根据用户ID获取用户信息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, email, created_at, last_login FROM users WHERE id = ?', (user_id,))
        user_row = cursor.fetchone()
        conn.close()
        
        if user_row:
            return {
                'id': user_row['id'],
                'username': user_row['username'],
                'email': user_row['email'],
                'created_at': user_row['created_at'],
                'last_login': user_row['last_login']
            }
        return None
    except Exception as e:
        print(f"[数据库] 获取用户信息失败: {e}")
        return None


# 初始化数据库（模块导入时自动执行）
init_database()

