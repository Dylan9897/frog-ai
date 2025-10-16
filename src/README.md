# Frog AI - TTS 语音合成服务

## 项目结构

```
src/
├── main.py              # Flask 主应用入口
├── templates/           # 主模板目录
│   └── index.html       # 主页
└── tts/                 # TTS 模块
    ├── templates/
    │   └── tts_interface.html  # TTS 界面
    ├── custom_voices/   # 自定义语音文件
    └── temp_audio/      # 临时音频文件
```

## 启动方式

### 方式一：从 src 目录启动
```bash
cd src
python main.py
```

### 方式二：从项目根目录启动
```bash
python start.py
```

## 访问地址

- **主页**: http://localhost:5000
- **TTS 界面**: http://localhost:5000/tts

## 功能说明

- **主页** (`/`): 应用入口，可以导航到各个功能模块
- **TTS 语音合成** (`/tts`): 文本转语音服务

## 依赖

```bash
pip install flask requests
```

