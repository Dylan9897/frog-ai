import sys
import os
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QListWidget, QListWidgetItem, QPushButton, QHBoxLayout,
    QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
import pyaudio


class AudioRecorder:
    def __init__(self, status_callback):
        self.status_callback = status_callback
        self.is_recording = False
        self.stream = None
        self.p = None

    def start_recording(self):
        # 录音参数
        chunk = 1024
        format = pyaudio.paInt16
        channels = 2
        rate = 44100

        try:
            self.p = pyaudio.PyAudio()

            # 打开流
            self.stream = self.p.open(
                format=format,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk
            )

            self.is_recording = True
            self.status_callback("🔴 录音中... (松开空格键停止)")

            # 开始录音循环
            while self.is_recording:
                data = self.stream.read(chunk, exception_on_overflow=False)
                # 这里可以对接音频处理逻辑，当前只是丢弃数据

        except Exception as e:
            print(f"录音出错: {e}")
            self.status_callback("录音出错，请重试")
        finally:
            self.stop_recording()

    def stop_recording(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.p:
            self.p.terminate()
        self.is_recording = False
        if not QApplication.instance().closing:
            self.status_callback("按住空格键开始录音")


class SandboxWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("沙盒录音启动器")
        self.setGeometry(0, 0, 400, 550)
        self.setWindowFlags(Qt.Window)

        # 沙盒存储目录（仅用于快捷方式）
        self.sandbox_dir = os.path.abspath("../sandbox_files")
        os.makedirs(self.sandbox_dir, exist_ok=True)

        # 录音相关变量
        self.space_pressed_time = 0
        self.recorder = None
        self.is_space_pressed = False
        self.main_timer = QTimer()
        self.main_timer.timeout.connect(self.check_space_press)
        self.main_timer.start(50)  # 每50ms检查一次
        self.closing = False

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        # 沙盒区域标签
        self.label = QLabel("📁 拖拽文件/文件夹到此区域\n(右上角沙盒)")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "background-color: rgba(240, 240, 240, 200);"
            "border: 2px dashed #aaa;"
            "border-radius: 8px;"
            "padding: 15px;"
            "font-size: 14px;"
        )
        layout.addWidget(self.label)

        # 录音状态标签
        self.recording_label = QLabel("按住空格键开始录音")
        self.recording_label.setAlignment(Qt.AlignCenter)
        self.recording_label.setStyleSheet(
            "background-color: rgba(255, 255, 255, 150);"
            "border: 1px solid #ccc;"
            "border-radius: 4px;"
            "padding: 8px;"
            "font-weight: bold;"
        )
        layout.addWidget(self.recording_label)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(
            "QListWidget {"
            "   background-color: white;"
            "   border: 1px solid #ccc;"
            "   border-radius: 4px;"
            "}"
        )
        self.file_list.itemClicked.connect(self.open_item)
        layout.addWidget(self.file_list)

        # 控制按钮
        button_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新列表")
        self.clear_btn = QPushButton("清空沙盒")
        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)

        # 连接按钮事件
        self.refresh_btn.clicked.connect(self.refresh_file_list)
        self.clear_btn.clicked.connect(self.clear_sandbox)

        # 启用拖放
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)  # 启用键盘焦点

        # 初始化文件列表
        self.refresh_file_list()

    def check_space_press(self):
        """主定时器检查空格键状态"""
        if self.is_space_pressed:
            elapsed = time.time() - self.space_pressed_time
            if elapsed >= 1.0 and self.recorder is None:
                # 开始录音
                self.start_recording()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not self.is_space_pressed:
            self.is_space_pressed = True
            self.space_pressed_time = time.time()
            self.recording_label.setText("⏳ 按住空格键... (1秒后开始录音)")
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and self.is_space_pressed:
            self.is_space_pressed = False
            if self.recorder and self.recorder.is_recording:
                # 停止录音
                self.recorder.is_recording = False
            else:
                # 按压时间不足1秒，重置状态
                self.recording_label.setText("按住空格键开始录音")
        super().keyReleaseEvent(event)

    def start_recording(self):
        """开始录音"""
        self.recorder = AudioRecorder(self.update_recording_status)
        # 在新线程中运行录音
        from PyQt5.QtCore import QThread
        class RecorderThread(QThread):
            def __init__(self, recorder):
                super().__init__()
                self.recorder = recorder

            def run(self):
                self.recorder.start_recording()

        self.recorder_thread = RecorderThread(self.recorder)
        self.recorder_thread.start()

    def update_recording_status(self, status):
        """更新录音状态标签"""
        self.recording_label.setText(status)

    def closeEvent(self, event):
        self.closing = True
        if self.recorder and self.recorder.is_recording:
            self.recorder.is_recording = False
        event.accept()

    def showEvent(self, event):
        # 窗口显示时定位到右上角
        screen_geo = QApplication.desktop().availableGeometry()
        x = screen_geo.right() - self.width()
        y = screen_geo.top()
        self.move(x, y)
        super().showEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if paths:
                # 为每个拖拽的项目创建快捷方式文件
                for path in paths:
                    self.create_shortcut(path)

                self.label.setText(f"✅ 放置了 {len(paths)} 个项目\n(右上角沙盒)")
                self.refresh_file_list()
            else:
                self.label.setText("⚠️ 无效路径\n(右上角沙盒)")

    def create_shortcut(self, src_path):
        """创建快捷方式文件"""
        try:
            filename = os.path.basename(src_path)
            shortcut_name = f"{filename}.lnk"
            shortcut_path = os.path.join(self.sandbox_dir, shortcut_name)

            # 如果快捷方式已存在，添加数字后缀
            counter = 1
            original_shortcut = shortcut_path
            while os.path.exists(shortcut_path):
                name, ext = os.path.splitext(original_shortcut)
                shortcut_path = f"{name}_{counter}{ext}"
                counter += 1

            # 创建包含源路径的文本文件作为快捷方式
            with open(shortcut_path, 'w', encoding='utf-8') as f:
                f.write(f"SOURCE_PATH={src_path}\n")
                f.write(f"TYPE={'directory' if os.path.isdir(src_path) else 'file'}\n")

        except Exception as e:
            print(f"创建快捷方式失败: {e}")

    def open_item(self, item):
        """点击列表项时打开对应的源文件/文件夹"""
        item_text = item.text()
        if item_text.startswith("🔗"):  # 快捷方式
            shortcut_name = item_text[2:].strip()  # 去掉 "🔗 " 前缀
            shortcut_path = os.path.join(self.sandbox_dir, shortcut_name)

            if os.path.exists(shortcut_path):
                try:
                    with open(shortcut_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        source_path = None
                        for line in lines:
                            if line.startswith("SOURCE_PATH="):
                                source_path = line[len("SOURCE_PATH="):].strip()
                                break

                    if source_path and os.path.exists(source_path):
                        # 根据操作系统打开文件/文件夹
                        if sys.platform.startswith('darwin'):  # macOS
                            os.system(f'open "{source_path}"')
                        elif sys.platform.startswith('win'):  # Windows
                            os.startfile(source_path)
                        else:  # Linux
                            os.system(f'xdg-open "{source_path}"')
                    else:
                        QMessageBox.warning(self, "错误", "源文件/文件夹不存在或已移动")
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"打开失败: {e}")
        else:
            QMessageBox.warning(self, "错误", "无法打开此项目")

    def refresh_file_list(self):
        """刷新文件列表（仅显示快捷方式）"""
        self.file_list.clear()

        # 只添加快捷方式文件
        for item in os.listdir(self.sandbox_dir):
            if item.endswith('.lnk'):  # 快捷方式文件
                item_widget = QListWidgetItem(f"🔗 {item}")
                self.file_list.addItem(item_widget)

    def clear_sandbox(self):
        """清空沙盒目录"""
        for item in os.listdir(self.sandbox_dir):
            item_path = os.path.join(self.sandbox_dir, item)
            try:
                if os.path.isdir(item_path):
                    import shutil
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception as e:
                print(f"删除失败: {e}")
        self.refresh_file_list()
        self.label.setText("📁 拖拽文件/文件夹到此区域\n(右上角沙盒)")


if __name__ == "__main__":
    # 检查 pyaudio 是否安装
    try:
        import pyaudio
    except ImportError:
        print("请先安装 pyaudio: pip install pyaudio")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = SandboxWindow()
    window.show()
    sys.exit(app.exec_())



