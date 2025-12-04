"""
应用统一配置文件
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# ==================== 数据目录配置 ====================
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 沙盒文件上传目录
UPLOAD_FOLDER = str(DATA_DIR / "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 对话附件缓存目录
CACHE_FOLDER = str(DATA_DIR / "cache")
os.makedirs(CACHE_FOLDER, exist_ok=True)

# 沙盒快捷方式目录
SHORTCUT_DIR = str(DATA_DIR / "sandbox_shortcuts")
os.makedirs(SHORTCUT_DIR, exist_ok=True)
SHORTCUT_CONFIG_PATH = os.path.join(SHORTCUT_DIR, 'shortcuts.json')

# DOCX 目录（如果使用）
DOCX_FOLDER = str(DATA_DIR / "docx")
os.makedirs(DOCX_FOLDER, exist_ok=True)

# ==================== 模板目录配置 ====================
TEMPLATES_DIR = PROJECT_ROOT / "config" / "templates"

# ==================== 数据库配置 ====================
# 用户数据库
USERS_DB_PATH = str(DATA_DIR / "users.db")

# RAG Agent 数据库（在 rag_agent 配置中定义）
RAG_DB_PATH = str(DATA_DIR / "rag_agent" / "rag_agent.db")

# ==================== Flask 配置 ====================
FLASK_CONFIG = {
    'SECRET_KEY': os.environ.get('SECRET_KEY', None),  # 将在 server.py 中生成
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'UPLOAD_FOLDER': UPLOAD_FOLDER,
    'MAX_CONTENT_LENGTH': 100 * 1024 * 1024  # 100MB
}

# ==================== 文件类型配置 ====================
# 允许上传的文件扩展名（白名单策略）
ALLOWED_EXTENSIONS = {
    # 文本 / 配置类
    'txt', 'log', 'md', 'markdown', 'rst',
    'json', 'yaml', 'yml', 'ini', 'cfg',
    'csv', 'tsv', 'xml',
    # 代码 / 脚本类
    'py', 'js', 'jsx', 'ts', 'tsx',
    'html', 'htm', 'css',
    # 文档 / 表格 / 演示
    'pdf',
    'doc', 'docx',
    'xls', 'xlsx',
    'ppt', 'pptx',
    # 图片
    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'ico',
    # 压缩包
    'zip', 'rar', '7z', 'tar', 'gz',
    # 音频 / 视频（仅作为附件管理,不做文本预览）
    'mp3', 'wav', 'ogg', 'flac', 'mp4', 'mov', 'avi', 'mkv', 'webm',
}

