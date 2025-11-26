# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2025/11/18 21:34
from flask import Flask, render_template, request, jsonify, send_file, make_response, Response, stream_with_context
import requests
import os
import uuid
from datetime import datetime
import json
from jinja2 import ChoiceLoader, FileSystemLoader

# 配置 Flask 支持多模板目录
app = Flask(__name__)
# 使用绝对路径，避免运行目录引起的模板解析混淆
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, 'templates')
TIANWA_TEMPLATES_DIR = os.path.join(PROJECT_ROOT, 'tianwa', 'templates')
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(TEMPLATES_DIR),           # 主模板目录
    FileSystemLoader(TIANWA_TEMPLATES_DIR)     # 蕉绿蛙模块模板目录
])


# Disable template caching during dev and add global no-cache headers
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True
@app.route('/tianwa')
def tianwa_interface():
    """蕉绿蛙 AI 助手界面"""
    return render_template('tianwa_interface.html')


@app.route('/api/tianwa/chat', methods=['POST'])
def tianwa_chat():
    """蕉绿蛙对话接口（支持流式输出）"""
    try:
        from tianwa.tianwa_service import get_tianwa_service
        
        # 检查是否启用流式输出
        try:
            from src.config.config import ENABLE_STREAMING
            use_stream = ENABLE_STREAMING
        except:
            use_stream = False

        data = request.json
        session_id = data.get('session_id')
        message = data.get('message')
        stream = data.get('stream', use_stream)  # 支持请求参数覆盖配置

        if not session_id or not message:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400

        # 获取蕉绿蛙服务
        service = get_tianwa_service()

        # 调用对话接口
        result = service.chat(session_id, message, stream=stream)
        
        # 如果是流式输出（生成器）
        if stream and hasattr(result, '__iter__') and not isinstance(result, dict):
            def generate():
                try:
                    full_reply = ""
                    for chunk in result:
                        if chunk:
                            full_reply += chunk
                            # 发送流式数据块（SSE 格式）
                            yield f"data: {json.dumps({'chunk': chunk, 'done': False}, ensure_ascii=False)}\n\n"
                    # 发送完成信号
                    yield f"data: {json.dumps({'chunk': '', 'done': True, 'full_reply': full_reply}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    error_msg = f'流式输出错误: {str(e)}'
                    yield f"data: {json.dumps({'error': error_msg, 'done': True}, ensure_ascii=False)}\n\n"
            
            return Response(
                stream_with_context(generate()),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no'  # 禁用 nginx 缓冲
                }
            )
        else:
            # 非流式输出（普通 JSON 响应）
            return jsonify(result)

    except Exception as e:
        print(f"[蕉绿蛙错误] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'服务错误: {str(e)}'}), 500


@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == '__main__':
    print("=" * 60)
    print("🐸 Frog AI 服务启动成功！")
    print("=" * 60)
    print(f"蕉绿蛙助手: http://localhost:5000/tianwa")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)