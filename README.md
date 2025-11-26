# 🐸 Frog AI (蕉绿蛙)

**Frog AI** 是一个开源语音智能体引擎，融合 ASR（语音识别）+ LLM（大语言模型）+ TTS（语音合成），打造端到端语音交互闭环。社区驱动，让 AI 从云端轻语回应。

## ✨ 特性

- 🎤 **实时语音识别 (ASR)**: 基于阿里云 DashScope 的 paraformer-realtime-v2 模型，支持实时语音转文字
- 🤖 **智能对话 (LLM)**: 集成通义千问大模型，支持流式输出，提供流畅的对话体验
- 🧠 **智能体系统**: 支持意图识别和任务执行，可打开文件、运行软件等操作
- 📦 **沙盒管理**: 提供图形化沙盒管理器，方便管理文件和快捷方式
- 🌐 **Web 界面**: 基于 Flask 的 Web 服务，提供友好的交互界面
- ⚡ **流式响应**: 支持流式输出，实时显示 AI 回复内容

## 📋 系统要求

- Python 3.8+
- 阿里云 DashScope API Key（用于 LLM 和 ASR 服务）

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

复制配置文件模板并填入你的 DashScope API Key：

```bash
cp src/config/config.py.example src/config/config.py
```

编辑 `src/config/config.py`：

```python
# DashScope API Key
DASHSCOPE_API_KEY = "your-api-key-here"

# 模型配置
LLM_MODEL = "qwen-max"  # 可选: qwen-max, qwen-plus, qwen-turbo

# 对话配置
MAX_HISTORY_ROUNDS = 5  # 历史对话轮数限制
ENABLE_STREAMING = True  # 是否启用流式输出
```

或者通过环境变量设置：

```bash
export DASHSCOPE_API_KEY="your-api-key-here"
```

### 3. 启动服务

#### 方式一：统一启动（推荐）

启动所有服务（Flask 主服务 + ASR 服务）：

```bash
python start_all.py
```

#### 方式二：分别启动

**启动 Flask 主服务：**

```bash
cd src
python main.py
```

**启动 ASR 服务：**

```bash
cd src
python -m uvicorn asr.asr_server:app --host 0.0.0.0 --port 5001
```

**启动沙盒管理器（可选）：**

```bash
cd src
python sandbox.py
```

### 4. 访问服务

- **蕉绿蛙 Web 界面**: http://localhost:5000/tianwa
- **ASR WebSocket 服务**: ws://localhost:5001/ws
- **ASR 健康检查**: http://localhost:5001/

## 📁 项目结构

```
frog-ai/
├── src/
│   ├── main.py                 # Flask 主服务
│   ├── sandbox.py              # 沙盒管理器（GUI）
│   ├── config/
│   │   └── config.py           # 配置文件
│   ├── tianwa/                 # 蕉绿蛙服务模块
│   │   ├── tianwa_service.py   # 核心服务类
│   │   └── templates/          # Web 模板
│   ├── asr/                    # 语音识别模块
│   │   ├── asr_service.py      # ASR 服务类
│   │   └── asr_server.py       # FastAPI WebSocket 服务器
│   ├── agents/                 # 智能体模块
│   │   ├── smart_agent/        # 智能体工作流
│   │   └── toolkit/            # 工具包（意图识别等）
│   └── database/               # 数据库模块
│       ├── sql_manager.py      # SQLite 数据库管理
│       └── operate.py          # 数据库操作
├── start_all.py                # 统一启动脚本
├── requirements.txt            # 依赖列表
└── README.md                   # 项目文档
```

## 🔧 配置说明

### 模型配置

- `qwen-max`: 最强性能，适合复杂任务
- `qwen-plus`: 平衡性能和速度
- `qwen-turbo`: 最快响应，适合简单对话

### 对话配置

- `MAX_HISTORY_ROUNDS`: 控制对话历史保留轮数，避免上下文过长
- `ENABLE_STREAMING`: 启用流式输出，提供更好的用户体验

## 🎯 功能模块

### 1. 蕉绿蛙对话服务

基于通义千问大模型，提供智能对话能力：

- 支持多轮对话，自动管理对话历史
- 支持流式输出，实时显示回复
- 可自定义系统提示词

### 2. 语音识别服务 (ASR)

实时语音转文字服务：

- 基于 WebSocket 的实时通信
- 支持部分结果和最终结果回调
- 使用 paraformer-realtime-v2 模型

### 3. 智能体系统

支持意图识别和任务执行：

- 意图分类（打开文件、闲聊等）
- 文件操作（打开文件、运行软件）
- 可扩展的任务执行能力

### 4. 沙盒管理器

图形化文件管理工具：

- 拖拽添加文件
- 文件分类管理
- 数据库持久化存储

## 🔌 API 接口

### 对话接口

**POST** `/api/tianwa/chat`

请求体：
```json
{
  "session_id": "unique-session-id",
  "message": "用户消息",
  "stream": true
}
```

响应（流式）：
```
data: {"chunk": "部分文本", "done": false}

data: {"chunk": "", "done": true, "full_reply": "完整回复"}
```

### ASR WebSocket

**WebSocket** `ws://localhost:5001/ws`

发送音频数据：
```json
{
  "type": "audio",
  "data": "base64-encoded-audio-data"
}
```

接收识别结果：
```json
{
  "type": "partial|final",
  "text": "识别文本"
}
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📝 许可证

本项目采用 **非商业许可证**，详见 [LICENSE](LICENSE) 文件。

**重要提示**：
- ✅ 允许个人学习、研究使用
- ✅ 允许教育机构教学使用
- ❌ **禁止商业用途**
- ❌ 禁止用于任何盈利性项目

## 👤 作者

- **冬瓜** - dylan_han@126.com

## 🙏 致谢

- [阿里云 DashScope](https://dashscope.aliyun.com/) - 提供 LLM 和 ASR 服务
- [LangGraph](https://github.com/langchain-ai/langgraph) - 智能体工作流编排
- [Flask](https://flask.palletsprojects.com/) - Web 框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架

## 📮 联系方式

如有问题或建议，请通过以下方式联系：

- Email: dylan_han@126.com
- Issue: [GitHub Issues](https://github.com/your-repo/frog-ai/issues)

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
