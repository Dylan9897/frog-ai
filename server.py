from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import os
import mimetypes
import json
from agent.file_parser import parse_file
from agent.chat import get_chat_service

# 初始化 Flask 应用
app = Flask(__name__)
# 允许跨域请求 - 配置更详细的 CORS 选项
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# --- 实用函数 ---
def allowed_file(filename):
    """只允许特定的文件扩展名，防止恶意上传"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'js', 'html', 'css',
                                               'md', 'json', 'csv', 'xml', 'doc', 'docx', 'pptx'}


# --- 静态文件和根路由 ---

@app.route('/')
def index():
    """根路由：返回 index_v3.html 文件。"""
    # 确保 index_v3.html 能够被正确找到并发送
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')


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
            # 成功上传，返回 200 OK 和 JSON
            return jsonify({"message": f"File {filename} uploaded successfully", "path": filepath}), 200
        except Exception as e:
            print(f"Error saving file {filename}: {e}")
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

    is_text_file = False
    if mimetype:
        if any(mimetype.startswith(t) for t in text_mimetypes):
            is_text_file = True
        elif 'code' in mimetype or 'script' in mimetype:
            is_text_file = True
    elif '.' in filename and filename.rsplit('.', 1)[1].lower() in ['py', 'js', 'html', 'css', 'md']:
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
        
        # 安全检查：防止路径遍历攻击
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.abspath(filepath).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return jsonify({"error": "Access denied"}), 403
        
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
        
        # 如果有附件，直接返回非流式响应
        if has_attachments:
            result = chat_service.chat(
                session_id=session_id,
                user_message=message or '（仅附件）',
                stream=False,
                has_attachments=True
            )
            if result.get('success'):
                return jsonify({
                    "success": True,
                    "reply": result.get('reply', ''),
                    "session_id": result.get('session_id', session_id)
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": result.get('error', '对话失败')
                }), 500
        
        # 流式输出
        def generate():
            try:
                # 获取会话消息
                session = chat_service.get_session(session_id)
                messages = session['messages']
                
                # 添加用户消息
                from dashscope.api_entities.dashscope_response import Role
                messages.append({'role': Role.USER, 'content': message})
                
                # 限制历史对话轮数
                from agent.chat import MAX_HISTORY_ROUNDS
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


if __name__ == '__main__':
    print("----------------------------------------------------------")
    print("🚀 Sandbox OS Pro 后端服务已启动，请勿关闭此窗口！")
    print(f"📁 文件将存储在: {os.path.abspath(UPLOAD_FOLDER)}")
    print("🔗 API 正在监听: http://127.0.0.1:5000")
    print("----------------------------------------------------------")
    # 生产环境中应禁用 debug=True
    app.run(host='127.0.0.1', port=5000, debug=True)