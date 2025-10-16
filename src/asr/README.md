# ASR 实时语音识别服务

## 功能说明

基于 DashScope `paraformer-realtime-v2` 模型的实时语音识别服务，使用 FastAPI + WebSocket 实现。

## 特性

- ✅ 实时流式识别（中间结果 + 最终结果）
- ✅ 自动添加语义标点
- ✅ WebSocket 异步通信
- ✅ 独立服务部署
- ✅ 跨域支持（CORS）

## 架构

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  浏览器前端     │ ◄─WS──► │ FastAPI ASR      │ ◄─API─► │ DashScope       │
│  (5000端口)     │         │ 服务 (5001端口)  │         │ paraformer-v2   │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements_asr.txt
```

### 2. 配置 API Key

在 `src/tianwa/config.py` 中配置：

```python
DASHSCOPE_API_KEY = "sk-your-api-key-here"
```

或设置环境变量：

```bash
export DASHSCOPE_API_KEY="sk-your-api-key-here"
```

### 3. 启动服务

#### 方式一：只启动 ASR 服务

```bash
python start_asr.py
```

ASR 服务将运行在 `ws://localhost:5001/ws`

#### 方式二：同时启动所有服务（推荐）

```bash
python start_all.py
```

将同时启动：
- Flask 主服务：`http://localhost:5000`
- FastAPI ASR 服务：`ws://localhost:5001/ws`

### 4. 测试

打开浏览器访问 `http://localhost:5000/tianwa`，按住空格键说话即可测试。

## 音频格式要求

- **格式**: PCM
- **采样率**: 16000 Hz
- **位深**: 16 bit
- **声道**: 单声道（mono）

## WebSocket API

### 端点

```
ws://localhost:5001/ws
```

### 消息格式

**客户端 → 服务器**:

```json
{
  "type": "audio",
  "data": "base64编码的PCM音频数据"
}
```

或

```json
{
  "type": "stop"
}
```

**服务器 → 客户端**:

```json
{
  "type": "partial",
  "text": "部分识别结果"
}
```

```json
{
  "type": "final",
  "text": "最终识别结果"
}
```

```json
{
  "type": "error",
  "message": "错误信息"
}
```

## Python API 使用示例

```python
from asr import ASRService

asr = ASRService()

def on_partial(text):
    print(f'[部分结果] {text}')

def on_final(text):
    print(f'[最终结果] {text}')

def on_error(error):
    print(f'[错误] {error}')

# 启动识别
asr.start_recognition(
    on_partial=on_partial,
    on_final=on_final,
    on_error=on_error
)

# 发送音频数据
asr.send_audio(audio_bytes)

# 停止识别
asr.stop_recognition()
```

## 常见问题

### 1. 无法连接到 WebSocket

确保 ASR 服务已启动：

```bash
python start_asr.py
```

检查端口 5001 是否被占用。

### 2. 识别无结果

- 检查 API Key 是否配置正确
- 确认麦克风权限已授予浏览器
- 查看浏览器控制台和服务器终端的日志

### 3. 跨域问题

ASR 服务已配置 CORS，允许所有来源。生产环境建议限制具体域名。

## 配置

API Key 优先级：
1. 环境变量 `DASHSCOPE_API_KEY`
2. `src/tianwa/config.py` 中的 `DASHSCOPE_API_KEY`

## 依赖

- `fastapi` - Web 框架
- `uvicorn` - ASGI 服务器
- `websockets` - WebSocket 支持
- `dashscope` - 阿里云 DashScope SDK

