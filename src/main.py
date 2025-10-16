from flask import Flask, render_template, request, jsonify, send_file, make_response
import requests
import os
import uuid
from datetime import datetime
import json
from jinja2 import ChoiceLoader, FileSystemLoader

# 配置 Flask 支持多模板目录
app = Flask(__name__)
app.jinja_loader = ChoiceLoader([
    FileSystemLoader('templates'),           # 主模板目录
    FileSystemLoader('tts/templates')        # TTS 模块模板目录
])

# Disable template caching during dev and add global no-cache headers
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# TTS服务地址
DEFAULT_TTS_SERVICE_URL = "http://192.168.1.56:20053/voice/tts_1"

# 创建临时文件夹（在 tts 模块目录下）
TEMP_DIR = "tts/temp_audio"
VOICE_TYPES_DIR = "tts/custom_voices"
VOICE_CONFIG_FILE = "tts/voice_types.json"

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
if not os.path.exists(VOICE_TYPES_DIR):
    os.makedirs(VOICE_TYPES_DIR)


# 加载语音类型配置
def load_voice_types():
    if os.path.exists(VOICE_CONFIG_FILE):
        with open(VOICE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "default": {"name": "默认语音", "sample_rate": 21100, "description": "系统默认"},
        "zwb": {"name": "ZWB 语音", "sample_rate": 21100, "description": "ZWB音色"},
        "gll": {"name": "GLL 语音", "sample_rate": 21100, "description": "GLL音色"}
    }


def save_voice_types(voice_types):
    with open(VOICE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(voice_types, f, ensure_ascii=False, indent=2)


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/tts')
def tts_interface():
    """TTS 语音合成界面"""
    import time
    # unique version stamp for cache-busting
    version_stamp = str(int(time.time()))
    html = render_template('tts_interface.html', version=version_stamp)
    response = make_response(html)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/api/voice_types', methods=['GET'])
def get_voice_types():
    """获取所有语音类型"""
    voice_types = load_voice_types()
    return jsonify({'success': True, 'voice_types': voice_types})


@app.route('/api/upload_voice', methods=['POST'])
def upload_voice():
    """上传自定义语音类型（假接口-仅前端展示）"""
    try:
        # 获取表单数据
        voice_id = request.form.get('voice_id')
        voice_name = request.form.get('voice_name')
        sample_rate = request.form.get('sample_rate', 21100)
        description = request.form.get('description', '')

        # 简单验证
        if not voice_id or not voice_name:
            return jsonify({'success': False, 'error': '请填写语音ID和名称'}), 400

        # 检查文件
        if 'audio_file' not in request.files:
            return jsonify({'success': False, 'error': '请上传音频文件'}), 400

        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'}), 400

        # 验证文件类型
        if not audio_file.filename.lower().endswith('.wav'):
            return jsonify({'success': False, 'error': '只支持WAV格式音频文件'}), 400

        # 假接口：只更新内存中的配置，不保存文件
        voice_types = load_voice_types()
        voice_types[voice_id] = {
            'name': voice_name,
            'sample_rate': int(sample_rate),
            'description': description,
            'audio_file': audio_file.filename,
            'is_custom': True
        }
        save_voice_types(voice_types)

        print(f"[模拟上传] 新增语音类型: {voice_id} - {voice_name} (文件: {audio_file.filename})")

        return jsonify({
            'success': True,
            'message': f'语音类型 "{voice_name}" 上传成功（演示模式）',
            'voice_id': voice_id
        })

    except Exception as e:
        print(f"[错误] 上传语音类型失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'上传失败: {str(e)}'}), 500


@app.route('/api/delete_voice/<voice_id>', methods=['DELETE'])
def delete_voice(voice_id):
    """删除自定义语音类型（假接口-仅前端展示）"""
    try:
        voice_types = load_voice_types()

        if voice_id not in voice_types:
            return jsonify({'success': False, 'error': '语音类型不存在'}), 404

        # 不允许删除系统预设的语音类型
        if not voice_types[voice_id].get('is_custom', False):
            return jsonify({'success': False, 'error': '不能删除系统预设的语音类型'}), 400

        # 假接口：只从配置中删除，不删除实际文件
        del voice_types[voice_id]
        save_voice_types(voice_types)

        print(f"[模拟删除] 语音类型: {voice_id}")

        return jsonify({'success': True, 'message': '删除成功（演示模式）'})

    except Exception as e:
        print(f"[错误] 删除语音类型失败: {str(e)}")
        return jsonify({'success': False, 'error': f'删除失败: {str(e)}'}), 500


@app.route('/api/synthesize', methods=['POST'])
def synthesize():
    """调用TTS服务生成语音"""
    try:
        data = request.json
        text = data.get('text', '')
        voice_type = data.get('voice_type', 'default')
        sample_rate = data.get('sample_rate', 21100)

        print(f"[请求] 文本长度: {len(text)}, 语音类型: {voice_type}, 采样率: {sample_rate}")

        if not text:
            return jsonify({'success': False, 'error': '请输入文本内容'}), 400

        # 生成唯一的sessionId
        session_id = str(uuid.uuid4())

        # 构造请求数据
        payload = {
            'inputs': text,
            'type': voice_type if voice_type != 'default' else None,
            'sample_rate': int(sample_rate),
            'sessionId': session_id
        }

        print(f"[调用] TTS服务URL: {DEFAULT_TTS_SERVICE_URL}")
        print(f"[调用] 请求数据: {payload}")

        # 调用TTS服务
        response = requests.post(DEFAULT_TTS_SERVICE_URL, json=payload, timeout=60)

        print(f"[响应] 状态码: {response.status_code}")

        if response.status_code == 200:
            # 保存音频文件
            filename = f"{session_id}.wav"
            filepath = os.path.join(TEMP_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)

            print(f"[成功] 音频文件已保存: {filepath}")

            return jsonify({
                'success': True,
                'audio_url': f'/audio/{filename}',
                'session_id': session_id
            })
        else:
            error_msg = f'TTS服务返回错误: {response.status_code}, 响应内容: {response.text[:200]}'
            print(f"[错误] {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    except requests.exceptions.Timeout as e:
        error_msg = f'请求超时: {str(e)}'
        print(f"[错误] {error_msg}")
        return jsonify({'success': False, 'error': '请求超时，请重试'}), 500
    except requests.exceptions.ConnectionError as e:
        error_msg = f'连接错误: {str(e)}'
        print(f"[错误] {error_msg}")
        return jsonify({'success': False, 'error': f'无法连接到TTS服务，请检查服务地址'}), 500
    except Exception as e:
        error_msg = f'未知错误: {type(e).__name__} - {str(e)}'
        print(f"[错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'发生错误: {str(e)}'}), 500


@app.route('/audio/<filename>')
def get_audio(filename):
    """获取生成的音频文件"""
    filepath = os.path.join(TEMP_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='audio/wav')
    return "文件不存在", 404


if __name__ == '__main__':
    print("=" * 60)
    print("🐸 Frog AI 服务启动成功！")
    print("=" * 60)
    print(f"主页地址: http://localhost:5000")
    print(f"TTS界面: http://localhost:5000/tts")
    print(f"TTS服务地址: {DEFAULT_TTS_SERVICE_URL}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)

