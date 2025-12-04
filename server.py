from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context, session, render_template, redirect, url_for
from flask_cors import CORS
import os
import mimetypes
import json
import sys
import secrets
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入统一配置
from config.app_config import (
    UPLOAD_FOLDER, CACHE_FOLDER, SHORTCUT_DIR, SHORTCUT_CONFIG_PATH,
    TEMPLATES_DIR, ALLOWED_EXTENSIONS, FLASK_CONFIG
)

# 导入业务模块
from src.agent.file_parser import parse_file, SUPPORTED_EXTS
from src.agent.chat import get_chat_service
from src.agent.intent_tools import smart_open_file_from_text
from src.databases.user_db import create_user, authenticate_user, get_user_by_id, init_database
from src.rag_agent.api import rag_bp

# 初始化 Flask 应用
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
# 配置 Session（用于登录状态管理）
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = FLASK_CONFIG['SESSION_COOKIE_HTTPONLY']
app.config['SESSION_COOKIE_SAMESITE'] = FLASK_CONFIG['SESSION_COOKIE_SAMESITE']
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = FLASK_CONFIG['MAX_CONTENT_LENGTH']

# 允许跨域请求 - 配置更详细的 CORS 选项
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# 注册 RAG Agent 蓝图
app.register_blueprint(rag_bp)


def _load_shortcuts() -> dict:
    """读取快捷方式配置 JSON，失败时返回空字典。"""
    if not os.path.exists(SHORTCUT_CONFIG_PATH):
        return {}
    try:
        with open(SHORTCUT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data or {}
    except Exception as e:
        print(f"读取快捷方式配置失败: {e}")
        return {}


def _save_shortcuts(shortcuts: dict) -> None:
    """保存快捷方式配置 JSON。"""
    try:
        with open(SHORTCUT_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(shortcuts, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"写入快捷方式配置失败: {e}")


def register_shortcut(filename: str, filepath: str):
    """
    记录一个“快捷方式”信息到 JSON 文件中，方便后续扩展/集成。
    实际打开文件时仍然直接使用真实路径（os.startfile）。
    """
    try:
        shortcuts = _load_shortcuts()
        shortcuts[filename] = os.path.abspath(filepath)
        _save_shortcuts(shortcuts)
    except Exception as e:
        print(f"注册快捷方式失败: {e}")


def remove_shortcut(filename: str):
    """从快捷方式配置 JSON 中移除某个文件的映射。"""
    try:
        shortcuts = _load_shortcuts()
        if filename in shortcuts:
            shortcuts.pop(filename, None)
            _save_shortcuts(shortcuts)
    except Exception as e:
        print(f"移除快捷方式失败: {e}")


# --- 实用函数 ---

def allowed_file(filename: str) -> bool:
    """只允许特定的文件扩展名，防止恶意上传"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def resolve_file_path(filename: str) -> str | None:
    """
    根据文件名在沙盒上传目录和问答缓存目录中查找真实路径。
    优先使用沙盒目录（uploads），否则回退到 cache。
    """
    # 先查沙盒目录
    upload_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))
    if upload_path.startswith(os.path.abspath(UPLOAD_FOLDER)) and os.path.exists(upload_path):
        return upload_path

    # 再查缓存目录
    cache_path = os.path.abspath(os.path.join(CACHE_FOLDER, filename))
    if cache_path.startswith(os.path.abspath(CACHE_FOLDER)) and os.path.exists(cache_path):
        return cache_path

    return None


# --- 静态文件和根路由 ---

@app.route('/')
def index():
    """根路由：检查登录状态，未登录则跳转到登录页"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return redirect(url_for('dashboard'))


@app.route('/login')
def login_page():
    """登录页面"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    """仪表板页面（需要登录）"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('AppDashboard.html')


@app.route('/sandbox')
def sandbox():
    """沙盒环境页面（需要登录）"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html')


@app.route('/knowledgebase')
def knowledgebase():
    """知识库页面（需要登录）"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('agent_knowledge_base.html')


@app.route('/config')
def config_dashboard():
    """系统配置页面（需要登录）"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('config_dashboard.html')


# --- API 路由 ---

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传，并保留原始文件名"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            file.save(filepath)

            # 记录一份“快捷方式”信息到 JSON（sandbox_shortcuts/shortcuts.json）
            try:
                register_shortcut(filename, filepath)
            except Exception as e:
                # 不影响主流程，只打印日志
                print(f"Warning: register_shortcut failed for {filename}: {e}")

            # 成功上传，返回 200 OK 和 JSON
            return jsonify({"message": f"File {filename} uploaded successfully", "path": filepath}), 200
        except Exception as e:
            print(f"Error saving file {filename}: {e}")
            return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

    return jsonify({"error": "File type not allowed"}), 400


@app.route('/chat-upload', methods=['POST'])
def chat_upload_file():
    """处理对话附件上传，文件仅存储在 cache 目录，不出现在沙盒文件墙中。"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(CACHE_FOLDER, filename)

        try:
            file.save(filepath)
            return jsonify({"message": f"File {filename} uploaded successfully", "path": filepath}), 200
        except Exception as e:
            print(f"Error saving chat file {filename}: {e}")
            return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

    return jsonify({"error": "File type not allowed"}), 400


@app.route('/files', methods=['GET'])
def list_files():
    """获取所有已上传文件的列表"""
    try:
        files = os.listdir(app.config['UPLOAD_FOLDER'])
        # 过滤掉隐藏文件，并确保列表不为空
        files = [f for f in files if not f.startswith('.')]

        # 返回标准的 JSON 格式，状态码 200，明确指定 Content-Type
        response = jsonify({"files": files})
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        print(f"返回文件列表: {files}")  # 调试信息
        return response, 200
    except Exception as e:
        # 如果文件系统错误，返回 500
        print(f"Error listing files: {e}")
        response = jsonify({"error": f"Failed to list files: {str(e)}"})
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response, 500


@app.route('/file/<filename>', methods=['GET'])
def view_file(filename):
    """查看文件内容，仅对文本文件返回内容，对二进制文件返回提示。"""
    # 安全检查：防止路径遍历攻击
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.abspath(filepath).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
        return "Access denied.", 403

    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    mimetype, _ = mimetypes.guess_type(filename)

    # 识别可作为文本预览的类型
    text_mimetypes = ['text/', 'json', 'xml', 'csv', 'javascript', 'python']

    # 额外按扩展名强制当作文本预览的类型
    text_like_exts = {
        'txt', 'log',
        'md', 'markdown',
        'json', 'yaml', 'yml', 'ini', 'cfg',
        'csv', 'tsv', 'xml',
        'py', 'js', 'jsx', 'ts', 'tsx',
        'html', 'htm', 'css',
    }

    is_text_file = False
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if mimetype:
        if any(mimetype.startswith(t) for t in text_mimetypes):
            is_text_file = True
        elif 'code' in mimetype or 'script' in mimetype:
            is_text_file = True
    if not is_text_file and ext in text_like_exts:
        is_text_file = True

    if is_text_file:
        try:
            # 尝试以 UTF-8 读取文件内容
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            # 返回文本内容，Content-Type 确保浏览器正确显示
            return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        except UnicodeDecodeError:
            # 编码错误，返回提示信息
            print(f"Warning: File {filename} could not be decoded with UTF-8.")
            return f"文件 {filename} 是二进制文件或编码错误，无法作为文本预览。", 200, {
                'Content-Type': 'text/plain; charset=utf-8'}
        except Exception as e:
            # 其他文件系统错误
            print(f"Error reading file {filename}: {e}")
            return f"读取文件时发生错误: {str(e)}", 500, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        # 二进制文件，返回提示信息
        return f"文件 {filename} 是二进制文件 ({mimetype or '未知类型'})，无法直接作为文本预览。", 200, {
            'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/file/<filename>', methods=['DELETE'])
def delete_file(filename):
    """删除指定的文件"""
    # 安全检查：防止路径遍历攻击
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.abspath(filepath).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
        return jsonify({"error": "Access denied"}), 403

    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    try:
        os.remove(filepath)

        # 同步删除对应的快捷方式配置
        try:
            remove_shortcut(filename)
        except Exception as e:
            # 不影响主流程，只记录日志
            print(f"Warning: remove_shortcut failed for {filename}: {e}")

        return jsonify({"message": f"File {filename} deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting file {filename}: {e}")
        return jsonify({"error": f"Failed to delete file: {str(e)}"}), 500


@app.route('/parse-file', methods=['POST'])
def parse_file_endpoint():
    """解析文件内容"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({"error": "文件名不能为空"}), 400
        
        # 解析路径：优先在 uploads，其次在 cache
        filepath = resolve_file_path(filename)
        if not filepath:
            return jsonify({"error": f"文件不存在: {filename}"}), 404
        
        # 调用解析函数
        result = parse_file(filepath)
        
        if result['success']:
            return jsonify({
                "success": True,
                "content": result['content'],
                "message": result['message'],
                "filename": result.get('filename'),
                "file_size": result.get('file_size')
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result['message']
            }), 500
            
    except Exception as e:
        print(f"Error parsing file: {e}")
        return jsonify({"error": f"解析文件时发生错误: {str(e)}"}), 500


@app.route('/open-file', methods=['POST'])
def open_file():
    """
    在服务器本机上用系统默认程序打开指定的沙盒文件。
    前端只需要传入 filename，双击触发该接口即可。
    """
    try:
        data = request.get_json() or {}
        filename = data.get('filename')

        if not filename:
            return jsonify({"error": "filename 不能为空"}), 400

        # 计算文件真实路径，并做安全检查
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        real_path = os.path.abspath(filepath)

        if not real_path.startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return jsonify({"error": "Access denied"}), 403

        if not os.path.exists(real_path):
            return jsonify({"error": "文件不存在"}), 404

        # 使用系统默认程序打开文件（Windows 上使用 os.startfile）
        try:
            if os.name == 'nt':
                os.startfile(real_path)
            else:
                # macOS / Linux 简单兼容处理
                import subprocess
                opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                subprocess.Popen([opener, real_path])
        except Exception as e:
            print(f"Error opening file {real_path}: {e}")
            return jsonify({"error": f"打开文件失败: {str(e)}"}), 500

        # 同步更新快捷方式 JSON（防止旧数据缺失）
        try:
            register_shortcut(filename, real_path)
        except Exception as e:
            print(f"Warning: register_shortcut in open_file failed for {filename}: {e}")

        return jsonify({
            "success": True,
            "message": f"已尝试用系统默认程序打开文件: {filename}"
        }), 200

    except Exception as e:
        print(f"Error in open_file: {e}")
        return jsonify({"error": f"打开文件时发生错误: {str(e)}"}), 500


@app.route('/chat', methods=['POST'])
def chat_endpoint():
    """对话接口（流式输出）"""
    try:
        data = request.get_json()
        session_id = data.get('session_id', 'default')
        message = data.get('message', '')
        has_attachments = data.get('has_attachments', False)
        
        if not message and not has_attachments:
            return jsonify({"error": "消息内容不能为空"}), 400
        
        # 获取对话服务
        chat_service = get_chat_service()

        # 预处理附件：仅支持特定文本/表格类型，并将解析后的内容作为上下文送入大模型
        file_context = None
        if has_attachments:
            attachment_names = data.get('attachment_filenames') or []

            if attachment_names:
                supported_contents = []

                for name in attachment_names:
                    _, ext = os.path.splitext(name)
                    if ext.lower() not in SUPPORTED_EXTS:
                        continue

                    filepath = resolve_file_path(name)
                    if not filepath:
                        continue

                    parse_result = parse_file(filepath)
                    if parse_result.get('success'):
                        supported_contents.append(parse_result.get('content', ''))

                if supported_contents:
                    # 将所有支持的文档内容拼接成一个上下文字符串
                    file_context = "\n\n".join(supported_contents)
                else:
                    # 全部不支持或解析失败，统一返回默认话术（非流式即可）
                    return jsonify({
                        "success": True,
                        "reply": (
                            "当前仅支持基于以下几类文档进行问答：docx、xlsx/xls、md、txt、json。\n"
                            "你上传的文件类型暂不在支持范围内，相关功能正在开发中。"
                        ),
                        "session_id": session_id
                    }), 200

        # 先做一次智能意图识别与打开文件动作（如果需要）
        smart_action_result = smart_open_file_from_text(message, UPLOAD_FOLDER)
        smart_action_summary = None
        if smart_action_result.get("intent") == "打开文件":
            # 根据打开结果生成一条系统提示，作为额外上下文注入给 LLM
            target_name = smart_action_result.get("target_name") or "目标文件"
            if smart_action_result.get("opened"):
                smart_action_summary = (
                    f"系统提示：根据用户指令，已经在本机尝试打开名为「{target_name}」的沙盒文件。"
                    "请用自然的口吻向用户确认你已经帮他打开了这个文件，并可继续回答其他问题。"
                )
            else:
                error = smart_action_result.get("error") or "未知原因"
                smart_action_summary = (
                    f"系统提示：检测到用户意图是打开文件，但在沙盒中未能成功打开对应文件（原因：{error}）。"
                    "请向用户说明当前无法自动打开文件，并给出可能的检查/解决建议。"
                )
        
        # 流式输出
        def generate():
            try:
                # 获取会话消息
                session = chat_service.get_session(session_id)
                messages = session['messages']
                
                # 添加用户消息
                from dashscope.api_entities.dashscope_response import Role
                messages.append({'role': Role.USER, 'content': message})

                # 如果有文档上下文，将其作为系统提示注入
                if file_context:
                    doc_system_prompt = (
                        "下面是用户上传的文档内容摘要或正文片段，请在回答本轮问题时，"
                        "优先依据这些文档内容进行推理和引用；当文档中没有相关信息时，再结合通用知识回答。\n\n"
                        f"{file_context}"
                    )
                    messages.append({'role': Role.SYSTEM, 'content': doc_system_prompt})

                # 如果有智能动作结果，作为额外 SYSTEM 信息注入
                if smart_action_summary:
                    messages.append({'role': Role.SYSTEM, 'content': smart_action_summary})
                
                # 限制历史对话轮数
                from src.agent.chat import MAX_HISTORY_ROUNDS
                current_rounds = (len(messages) - 1) // 2
                if current_rounds > MAX_HISTORY_ROUNDS:
                    excess_rounds = current_rounds - MAX_HISTORY_ROUNDS
                    messages = [messages[0]] + messages[1 + excess_rounds * 2:]
                    session['messages'] = messages
                
                # 调用流式生成
                full_reply = ""
                for chunk in chat_service._chat_stream(messages):
                    if chunk:
                        full_reply += chunk
                        # 发送数据块
                        yield f"data: {json.dumps({'chunk': chunk, 'done': False}, ensure_ascii=False)}\n\n"
                
                # 发送完成信号
                yield f"data: {json.dumps({'chunk': '', 'done': True, 'full_reply': full_reply}, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                error_msg = f"流式输出错误: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'error': error_msg, 'done': True}, ensure_ascii=False)}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
            
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"对话时发生错误: {str(e)}"}), 500


@app.route('/chat/clear', methods=['POST'])
def clear_chat_endpoint():
    """清除对话记录"""
    try:
        data = request.get_json()
        session_id = data.get('session_id', 'default')
        
        # 获取对话服务
        chat_service = get_chat_service()
        
        # 清除会话
        chat_service.clear_session(session_id)
        
        return jsonify({
            "success": True,
            "message": "对话记录已清除"
        }), 200
            
    except Exception as e:
        print(f"Error clearing chat: {e}")
        return jsonify({"error": f"清除对话记录时发生错误: {str(e)}"}), 500


# --- 用户认证相关路由 ---

@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip() or None
        
        if not username or not password:
            return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400
        
        if len(username) < 3:
            return jsonify({"success": False, "message": "用户名至少需要3个字符"}), 400
        
        if len(password) < 6:
            return jsonify({"success": False, "message": "密码至少需要6个字符"}), 400
        
        success, message = create_user(username, password, email)
        
        if success:
            return jsonify({"success": True, "message": message}), 200
        else:
            return jsonify({"success": False, "message": message}), 400
    
    except Exception as e:
        print(f"注册错误: {e}")
        return jsonify({"success": False, "message": f"注册失败: {str(e)}"}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400
        
        success, user_info, message = authenticate_user(username, password)
        
        if success and user_info:
            # 设置 session
            session['user_id'] = user_info['id']
            session['username'] = user_info['username']
            session['email'] = user_info.get('email')
            
            return jsonify({
                "success": True,
                "message": message,
                "user": {
                    "id": user_info['id'],
                    "username": user_info['username'],
                    "email": user_info.get('email')
                }
            }), 200
        else:
            return jsonify({"success": False, "message": message}), 401
    
    except Exception as e:
        print(f"登录错误: {e}")
        return jsonify({"success": False, "message": f"登录失败: {str(e)}"}), 500


@app.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    try:
        session.clear()
        return jsonify({"success": True, "message": "已成功登出"}), 200
    except Exception as e:
        print(f"登出错误: {e}")
        return jsonify({"success": False, "message": f"登出失败: {str(e)}"}), 500


@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    """检查当前登录状态"""
    if 'user_id' in session:
        user_info = get_user_by_id(session['user_id'])
        if user_info:
            return jsonify({
                "authenticated": True,
                "user": {
                    "id": user_info['id'],
                    "username": user_info['username'],
                    "email": user_info.get('email')
                }
            }), 200
    
    return jsonify({"authenticated": False}), 200


if __name__ == '__main__':
    # 初始化数据库
    init_database()
    
    # 检查 ASR 服务是否运行
    import socket
    def check_asr_service():
        """检查 ASR 服务是否在运行"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 5001))
            sock.close()
            return result == 0
        except:
            return False
    
    asr_running = check_asr_service()
    
    print("----------------------------------------------------------")
    print("🚀 Sandbox OS Pro 后端服务已启动，请勿关闭此窗口！")
    print(f"📁 文件将存储在: {os.path.abspath(UPLOAD_FOLDER)}")
    print("🔗 API 正在监听: http://127.0.0.1:5000")
    print("🔐 登录页面: http://127.0.0.1:5000/login")
    print("📊 仪表板: http://127.0.0.1:5000/dashboard")
    print("----------------------------------------------------------")
    if not asr_running:
        print("⚠️  警告: ASR 服务未运行 (端口 5001)")
        print("   语音识别功能将不可用。")
        print("   请运行以下命令启动 ASR 服务：")
        print("   python -m uvicorn src.agent.asr_server:app --host 0.0.0.0 --port 5001")
        print("   或者使用 start_all.py 同时启动所有服务：")
        print("   python start_all.py")
        print("----------------------------------------------------------")
    else:
        print("✅ ASR 服务已运行: ws://127.0.0.1:5001/ws")
        print("----------------------------------------------------------")
    
    # 生产环境中应禁用 debug=True
    app.run(host='127.0.0.1', port=5000, debug=True)