"""
桌面悬浮小助手（Frog）

功能：
- 启动时在桌面右下角悬浮一枚青蛙图标
- 鼠标可拖动位置（始终置顶，支持跨窗口拖拽）
- 单击时播放一个轻微的放大/缩小动画，并在默认浏览器中打开 http://127.0.0.1:5000

依赖：
- PyQt5

图标：
- 优先使用项目根目录下的 frog.png
- 如果不存在，则回退使用 big_eye_robot.png（仓库已有）
"""

import os
import sys
import webbrowser

from PyQt5.QtCore import Qt, QPoint, QPropertyAnimation, QRect
from PyQt5.QtGui import QPixmap, QCursor
from PyQt5.QtWidgets import QApplication, QWidget, QLabel


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


class FloatingFrog(QWidget):
    def __init__(self, url: str = "http://127.0.0.1:5000"):
        super().__init__()
        self.target_url = url

        # 无边框、透明背景、始终置顶的小窗口
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 加载图标
        icon_path = os.path.join(PROJECT_ROOT, "config", "templates", "frog.png")
        fallback_path = os.path.join(PROJECT_ROOT, "big_eye_robot.png")
        if not os.path.exists(icon_path):
            icon_path = fallback_path

        pix = QPixmap(icon_path)
        if pix.isNull():
            # 安全兜底：创建一个占位图像
            pix = QPixmap(120, 120)
            pix.fill(Qt.green)

        # 控制显示大小（缩放但保持清晰）
        target_size = 120
        pix = pix.scaled(
            target_size,
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        self.label = QLabel(self)
        self.label.setPixmap(pix)
        self.label.setScaledContents(False)
        self.label.setAlignment(Qt.AlignCenter)

        self.resize(pix.width(), pix.height())

        # 初始位置：右下角稍微往上
        screen = QApplication.primaryScreen().availableGeometry()
        margin = 40
        x = screen.right() - self.width() - margin
        y = screen.bottom() - self.height() - margin
        self.move(x, y)

        self._drag_pos: QPoint | None = None
        self._click_pos: QPoint | None = None

        # 简单的缩放动画
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(220)

    # ---------- 拖动逻辑 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._click_pos = event.globalPos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 判定是“点击”还是“拖动”：移动距离很小则认为是点击
            if (
                self._click_pos is not None
                and (self._click_pos - event.globalPos()).manhattanLength() < 6
            ):
                self._on_click()
            self._drag_pos = None
            self._click_pos = None
            event.accept()

    # ---------- 点击动画 + 打开网页 ----------
    def _on_click(self):
        # 打开网页
        try:
            webbrowser.open(self.target_url)
        except Exception as e:
            print(f"[desktop_frog] 打开浏览器失败: {e}")

        # 播放一个轻量级的放大/缩小动画
        geo = self.geometry()
        scale = 1.15
        new_w = int(geo.width() * scale)
        new_h = int(geo.height() * scale)
        new_x = geo.center().x() - new_w // 2
        new_y = geo.center().y() - new_h // 2

        enlarged = QRect(new_x, new_y, new_w, new_h)

        self._anim.stop()
        self._anim.setStartValue(geo)
        self._anim.setKeyValueAt(0.5, enlarged)
        self._anim.setEndValue(geo)
        self._anim.start()


def main():
    # 保证只创建一个 QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Frog Desktop Assistant")

    frog = FloatingFrog()
    frog.show()

    # 改一下鼠标指针样式，提示可点击
    frog.setCursor(QCursor(Qt.PointingHandCursor))

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


