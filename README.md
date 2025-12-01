## Frog AI / Sandbox OS Pro

一个本地运行的文档沙盒和 AI 助手：

- Web 沙盒界面：上传 PDF / 图片等文件，在卡片网格中管理、双击本机打开。
- 右侧 AI 面板：与大模型聊天、拖拽文件到对话框、支持流式输出 + TTS 播报。
- 实时语音输入：长按空格 1 秒开始录音，松开自动识别并发送问题。
- 桌面悬浮助手：系统启动 `start_all.py` 后，会在桌面右下角悬浮一只青蛙图标，点击后动画展开并在浏览器打开 `http://127.0.0.1:5000`。

本项目完全本地运行，只依赖 DashScope 云端模型 API（LLM 与 ASR）。

---

### 1. 环境准备

1. **Python 版本**
   - 建议使用 Python **3.9+**（Windows 下优先 3.9–3.11）。

2. **创建虚拟环境（可选但推荐）**

```bash
cd frog-ai
python -m venv .venv
.venv\Scripts\activate  # Windows
# 或
source .venv/bin/activate  # macOS / Linux
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

> 注意：`PyQt5` 在某些 Linux 环境下可能需要额外系统库，请根据提示安装。

4. **配置 DashScope API Key**

项目会按以下优先级加载 DashScope 密钥：

1. 环境变量 `DASHSCOPE_API_KEY`
2. `agent/config.py` 中的 `DASHSCOPE_API_KEY`
3. 环境变量 `DASHSCOPE_API_KEY_FILE_PATH` 指向的文件
4. 默认文件 `~/.dashscope/api_key`

推荐方式（Windows PowerShell 示例）：

```powershell
$env:DASHSCOPE_API_KEY="替换成你的 DashScope Key"
```

---

### 2. 启动服务

在项目根目录执行：

```bash
python start_all.py
```

该脚本会：

- 启动 Flask 主服务（`server.py`），监听 `http://127.0.0.1:5000`
- 启动 FastAPI ASR WebSocket 服务（端口 `5001`）
- 启动桌面悬浮 Frog 助手（`desktop_frog.py`）

浏览器中访问：

- 沙盒主界面：`http://127.0.0.1:5000`

---

### 3. 主要功能说明

#### 3.1 沙盒文件墙

- 顶部「上传文件到沙盒」按钮，或点击底部 `+` 卡片，即可批量上传文件到 `uploads/`。
- 网格区域支持纵向滚动，文件再多也不会挤压布局。
- 单个卡片：
  - 显示文件名与类型图标
  - 双击卡片：调用后端在本机用默认程序打开文件
  - 右上角菜单：可以删除文件

#### 3.2 AI 对话 & 文件解析

- 右侧面板可以直接聊天，也可以：
  - 将沙盒中的文件卡片 **拖拽** 到对话框作为上下文
  - 在对话框里上传单独的附件，仅在会话中使用
- 调用 `/parse-file` 对文件做基础解析，界面上方会有「正在解析 / 已完成」提示。

#### 3.3 智能“打开文件”意图

- 聊天时，如果你输入类似：
  - “帮我打开 2021.naacl-main.83 那篇论文”
  - “打开那篇 ACL 2021 的 findings 论文”
- 后端会：
  1. 用 LLM 做意图识别（是否为“打开文件”）
  2. 从沙盒中文件名中抽取关键词并匹配
  3. 在本机尝试打开最匹配的文件
  4. 将结果作为额外系统消息注入对话，让 AI 告诉你是否打开成功

#### 3.4 语音输入（ASR）

- 在页面任意位置：**长按空格键 1 秒** 开始录音，松开空格即停止。
- 录音过程中：
  - 底部输入框会提示「正在录音」
  - 聊天区域会出现一个“草稿气泡”，实时显示 ASR 转写结果
- 松开空格后：
  - 等待 ASR 返回最终文本
  - 自动把文本作为用户消息发送给 AI

> ASR 服务使用 DashScope `paraformer-realtime-v2` 模型，通过 WebSocket `ws://127.0.0.1:5001/ws` 连接。

#### 3.5 桌面悬浮 Frog 助手

- 启动 `start_all.py` 后，会弹出一个始终置顶的小窗口（青蛙图标）：
  - **拖动**：鼠标左键按住图标即可拖动到任何位置。
  - **点击**：轻点一下会有放大缩小动画，并在默认浏览器中打开 `http://127.0.0.1:5000`。
- 图标文件：
  - 优先使用 `templates/frog.png`
  - 若不存在则回退为 `big_eye_robot.png`

---

### 4. 开发建议

- 前端主要在 `index.html` 中，通过原生 JS + Tailwind 组织 UI 与事件。
- 后端核心逻辑在：
  - `server.py`：文件上传/管理、解析、聊天、智能打开文件等 API
  - `agent/chat.py`：封装 LLM 对话服务
  - `agent/intent_tools.py`：意图识别 + 关键词抽取 + 智能打开文件
  - `agent/asr_service.py` / `agent/asr_server.py`：ASR WebSocket 服务
- 如需更换模型或调整参数，可以在 `agent/config.py`、`agent/chat.py` 和 `agent/asr_service.py` 中修改。

---

### 5. 许可协议

本项目采用 **自定义「非商业使用」许可协议**：

- 允许个人、教学、科研等 **非商业场景** 下使用、修改和再分发代码；
- **禁止任何形式的商业使用**（包括收费产品、SaaS 服务、广告变现等），除非获得作者的书面授权；
- 详细条款请查阅根目录下的 `LICENSE` 文件。 



