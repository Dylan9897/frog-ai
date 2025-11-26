# 蕉绿蛙 (TianWa) - AI 对话助手

## 简介

蕉绿蛙是一个基于阿里云 DashScope API 的智能对话助手，集成了 Qwen 大语言模型，提供流畅的文本对话体验。

## 功能特性

- ✅ **智能对话**：基于 Qwen-Max 大模型，理解能力强
- ✅ **会话管理**：支持多会话并发，自动管理对话历史
- ✅ **简洁界面**：现代化的 Web 界面，操作简单
- ✅ **实时响应**：快速响应用户输入
- ✅ **历史限制**：自动管理对话历史，避免上下文过长

## 技术栈

- **后端**：Flask + Python
- **前端**：原生 JavaScript + HTML5 + CSS3
- **AI 服务**：阿里云 DashScope API (Qwen-Max)

## 使用方法

### 1. 配置 API Key

在使用蕉绿蛙之前，需要配置阿里云 DashScope 的 API Key：

```bash
# 方法一：设置环境变量（推荐）
export DASHSCOPE_API_KEY="your_api_key_here"

# 方法二：在代码中配置
# 编辑 tianwa_service.py，修改初始化代码
```

### 2. 启动服务

```bash
cd src
python main.py
```

### 3. 访问界面

打开浏览器访问：http://localhost:5000/tianwa

## 项目结构

```
tianwa/
├── __init__.py              # 模块初始化
├── tianwa_service.py        # 核心服务逻辑
├── templates/               # 前端模板
│   └── tianwa_interface.html
└── README.md                # 使用说明
```

## API 接口

### POST /api/tianwa/chat

对话接口

**请求参数：**
```json
{
  "session_id": "session_xxx",
  "message": "你好"
}
```

**响应参数：**
```json
{
  "success": true,
  "reply": "你好！我是蕉绿蛙，有什么可以帮助你的吗？",
  "session_id": "session_xxx"
}
```

## 核心类

### TianWaService

蕉绿蛙服务核心类，提供对话管理功能。

**主要方法：**

- `create_session(session_id)`: 创建新会话
- `get_session(session_id)`: 获取会话
- `clear_session(session_id)`: 清除会话
- `chat(session_id, user_message, stream=False)`: 对话接口

## 配置项

在 `tianwa_service.py` 中可以配置：

```python
LLM_MODEL = 'qwen-max'           # 使用的模型
MAX_HISTORY_ROUNDS = 5           # 历史对话轮数限制
SYSTEM_PROMPT = "..."            # 系统提示词
```

## 注意事项

1. **API Key 安全**：不要将 API Key 提交到代码仓库
2. **并发限制**：注意 DashScope API 的并发和配额限制
3. **会话管理**：长时间不使用的会话会占用内存，建议定期清理

## 后续优化

- [ ] 添加流式输出支持
- [ ] 添加语音输入/输出功能
- [ ] 添加对话导出功能
- [ ] 添加更多个性化设置
- [ ] 优化会话管理策略

## 原始代码说明

蕉绿蛙的核心逻辑来自 `task1` 文件夹中的语音机器人项目，进行了以下优化：

1. **删除冗余代码**：移除了分案系统相关的所有代码
2. **简化架构**：从 tkinter GUI 改为 Web 界面
3. **模块化设计**：将功能封装为独立的服务类
4. **集成到项目**：与现有的 Frog AI 项目无缝集成

## 许可证

与 Frog AI 项目保持一致

