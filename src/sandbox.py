import sys
import os
import shutil
import webbrowser
import uuid
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout,
    QMessageBox, QMenu
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from src.database.operate import manager_database

class SandboxWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("沙盒快捷方式管理器")
        self.setGeometry(0, 0, 450, 580)  # 增加高度以适应新按钮
        self.setWindowFlags(Qt.Window)

        # 微服务地址
        self.microservice_url = "http://localhost:5000/tianwa"

        # 沙盒存储目录
        self.sandbox_dir = os.path.abspath("../sandbox_files")
        os.makedirs(self.sandbox_dir, exist_ok=True)
        
        # 生成会话ID（用于数据库记录）
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        # 拖拽区域标签
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

        # 微服务按钮
        self.microservice_btn = QPushButton("🐸 打开蕉绿蛙助手")
        self.microservice_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.microservice_btn.clicked.connect(self.open_microservice)
        layout.addWidget(self.microservice_btn)

        # 树形文件列表
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.itemDoubleClicked.connect(self.open_item)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.tree_widget)

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

        # 初始化文件列表
        self.refresh_file_list()

    def open_microservice(self):
        """在默认浏览器中打开蕉绿蛙助手"""
        try:
            webbrowser.open(self.microservice_url)
            self.microservice_btn.setText("✅ 已打开蕉绿蛙助手")
            # 3秒后恢复按钮文本
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(3000, lambda: self.microservice_btn.setText("🐸 打开蕉绿蛙助手"))
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开蕉绿蛙助手: {e}")

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

            counter = 1
            original_shortcut = shortcut_path
            while os.path.exists(shortcut_path):
                name, ext = os.path.splitext(original_shortcut)
                shortcut_path = f"{name}_{counter}{ext}"
                counter += 1

            with open(shortcut_path, 'w', encoding='utf-8') as f:
                f.write(f"SOURCE_PATH={src_path}\n")
                f.write(f"TYPE={'directory' if os.path.isdir(src_path) else 'file'}\n")

            # ✅ 在这里触发“添加到沙盒”的事件
            self.on_item_added_to_sandbox(src_path, shortcut_path)

        except Exception as e:
            print(f"创建快捷方式失败: {e}")

    ####
    def on_item_added_to_sandbox(self, source_path: str, shortcut_path: str):
        """
        当有新项目被添加到沙盒时触发。
        同步更新到数据库中。
        """
        print(f"[EVENT] 新项目加入沙盒: {source_path} -> {shortcut_path}")
        
        # 同步到数据库
        try:
            # 获取文件标题（文件名）
            file_title = os.path.basename(source_path)
            
            # 调用数据库管理函数添加记录
            result = manager_database(
                action='add',
                sessionId=self.session_id,
                file_path=source_path,
                shortcut_path=shortcut_path,
                file_title=file_title
            )
            
            if result:
                print(f"[DB] 成功同步到数据库: {shortcut_path}")
            else:
                print(f"[DB] 数据库同步失败: {shortcut_path}")
        except Exception as e:
            print(f"[DB] 数据库同步异常: {e}")

    def create_folder_shortcut(self, folder_path, entry_name, parent_shortcut_name):
        """为文件夹内的项目创建快捷方式，使用父级快捷方式名称作为前缀"""
        try:
            entry_full_path = os.path.join(folder_path, entry_name)
            # 使用父级快捷方式名称作为前缀，避免命名冲突
            prefix = parent_shortcut_name.replace('.lnk', '')
            shortcut_name = f"{prefix}__{entry_name}.lnk"
            shortcut_path = os.path.join(self.sandbox_dir, shortcut_name)

            counter = 1
            original_shortcut = shortcut_path
            while os.path.exists(shortcut_path):
                name, ext = os.path.splitext(original_shortcut)
                shortcut_path = f"{name}_{counter}{ext}"
                counter += 1

            with open(shortcut_path, 'w', encoding='utf-8') as f:
                f.write(f"SOURCE_PATH={entry_full_path}\n")
                f.write(f"TYPE={'directory' if os.path.isdir(entry_full_path) else 'file'}\n")

            return os.path.basename(shortcut_path)
        except Exception as e:
            print(f"创建文件夹内快捷方式失败: {e}")
            return None

    def open_item(self, item, column):
        """双击打开项目"""
        item_text = item.text(0)

        # 移除图标前缀
        if item_text.startswith("📁 "):
            item_name = item_text[2:]
        elif item_text.startswith("📄 "):
            item_name = item_text[2:]
        else:
            item_name = item_text

        # 构建快捷方式路径
        shortcut_path = os.path.join(self.sandbox_dir, item_name)
        if not os.path.exists(shortcut_path):
            QMessageBox.warning(self, "错误", "快捷方式文件不存在")
            return

        try:
            with open(shortcut_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                source_path = None
                for line in lines:
                    if line.startswith("SOURCE_PATH="):
                        source_path = line[len("SOURCE_PATH="):].strip()
                        break

            if source_path and os.path.exists(source_path):
                if sys.platform.startswith('darwin'):
                    os.system(f'open "{source_path}"')
                elif sys.platform.startswith('win'):
                    os.startfile(source_path)
                else:
                    os.system(f'xdg-open "{source_path}"')
            else:
                QMessageBox.warning(self, "错误", "源文件/文件夹不存在或已移动")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开失败: {e}")

    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.tree_widget.itemAt(position)
        if item is None:
            return

        # 获取项目名称
        item_text = item.text(0)
        if item_text.startswith("📁 "):
            item_name = item_text[2:]
        elif item_text.startswith("📄 "):
            item_name = item_text[2:]
        else:
            item_name = item_text

        # 创建右键菜单
        menu = QMenu()
        delete_action = menu.addAction("🗑️ 删除")

        # 连接删除动作
        delete_action.triggered.connect(lambda: self.delete_item(item_name))

        # 显示菜单
        menu.exec_(self.tree_widget.mapToGlobal(position))

    def delete_item(self, item_name):
        """删除指定的快捷方式文件"""
        shortcut_path = os.path.join(self.sandbox_dir, item_name)
        if os.path.exists(shortcut_path):
            # 询问用户确认
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除 '{item_name}' 吗？\n\n此操作将删除快捷方式，不会影响原始文件。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                try:
                    os.remove(shortcut_path)
                    # 如果是文件夹，还要删除其相关的子快捷方式
                    self.delete_related_shortcuts(item_name)

                    # ✅ 在这里触发“从沙盒删除”的事件
                    self.on_item_removed_from_sandbox(item_name, shortcut_path)
                    # 保存当前展开状态
                    expanded_items = self.get_expanded_items()
                    # 重新刷新列表
                    self.refresh_file_list()
                    # 恢复之前展开的项目
                    self.set_expanded_items(expanded_items)
                    self.label.setText("📁 拖拽文件/文件夹到此区域\n(右上角沙盒)")
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"删除失败: {e}")
        else:
            QMessageBox.warning(self, "错误", "快捷方式文件不存在")

    ######
    def on_item_removed_from_sandbox(self, item_name: str, shortcut_path: str):
        """
        当沙盒中的项目被删除时触发。
        同步更新到数据库中。
        """
        print(f"[EVENT] 项目从沙盒移除: {item_name} ({shortcut_path})")
        
        # 同步到数据库
        try:
            # 调用数据库管理函数删除记录
            result = manager_database(
                action='delete',
                shortcut_path=shortcut_path
            )
            
            if result:
                print(f"[DB] 成功从数据库删除: {shortcut_path}")
            else:
                print(f"[DB] 数据库删除失败: {shortcut_path}")
        except Exception as e:
            print(f"[DB] 数据库删除异常: {e}")

    def delete_related_shortcuts(self, parent_shortcut_name):
        """删除与父级快捷方式相关的子快捷方式"""
        prefix = parent_shortcut_name.replace('.lnk', '')
        related_files = []

        for item in os.listdir(self.sandbox_dir):
            if item.endswith('.lnk') and item.startswith(f"{prefix}__"):
                related_files.append(item)

        # 删除所有相关的子快捷方式
        for related_file in related_files:
            related_path = os.path.join(self.sandbox_dir, related_file)
            try:
                # 从数据库删除
                manager_database(action='delete', shortcut_path=related_path)
                # 删除文件
                os.remove(related_path)
            except Exception as e:
                print(f"[DB] 删除相关快捷方式失败 {related_file}: {e}")

    def get_expanded_items(self):
        """获取当前展开的项目路径列表"""
        expanded_items = []

        # 获取顶级项目
        for i in range(self.tree_widget.topLevelItemCount()):
            top_item = self.tree_widget.topLevelItem(i)
            if top_item.isExpanded():
                expanded_items.append(top_item.text(0))

            # 获取子项目（如果有的话）
            for j in range(top_item.childCount()):
                child_item = top_item.child(j)
                if child_item.isExpanded():
                    expanded_items.append(child_item.text(0))

        return expanded_items

    def set_expanded_items(self, expanded_items):
        """设置展开的项目"""
        # 遍历所有项目并设置展开状态
        for i in range(self.tree_widget.topLevelItemCount()):
            top_item = self.tree_widget.topLevelItem(i)
            if top_item.text(0) in expanded_items:
                top_item.setExpanded(True)

            # 遍历子项目
            for j in range(top_item.childCount()):
                child_item = top_item.child(j)
                if child_item.text(0) in expanded_items:
                    child_item.setExpanded(True)

    def sort_items(self, items):
        """排序函数：文件夹优先，然后是文件，都按首字母排序"""
        folders = []
        files = []

        for item in items:
            # 从快捷方式内容判断类型
            shortcut_path = os.path.join(self.sandbox_dir, item)
            if os.path.exists(shortcut_path):
                try:
                    with open(shortcut_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith("TYPE="):
                                item_type = line[len("TYPE="):].strip()
                                if item_type == 'directory':
                                    folders.append(item)
                                else:
                                    files.append(item)
                                break
                except:
                    # 如果无法读取类型，默认为文件
                    files.append(item)
            else:
                # 如果快捷方式不存在，默认为文件
                files.append(item)

        # 按首字母排序
        folders.sort()
        files.sort()

        return folders + files

    def refresh_file_list(self):
        """刷新文件列表，支持文件夹展开"""
        self.tree_widget.clear()
        items = os.listdir(self.sandbox_dir)

        # 只处理根级快捷方式（不包含父级前缀的）
        root_items = [item for item in items if item.endswith('.lnk') and '__' not in item]

        # 排序根级项目
        sorted_root_items = self.sort_items(root_items)

        for item in sorted_root_items:
            shortcut_path = os.path.join(self.sandbox_dir, item)
            if not os.path.exists(shortcut_path):
                continue

            try:
                with open(shortcut_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    source_path = None
                    is_dir = False
                    for line in lines:
                        if line.startswith("SOURCE_PATH="):
                            source_path = line[len("SOURCE_PATH="):].strip()
                        elif line.startswith("TYPE="):
                            is_dir = line[len("TYPE="):].strip() == 'directory'

                    if source_path:
                        if is_dir and os.path.exists(source_path):
                            # 创建文件夹节点
                            folder_item = QTreeWidgetItem([f"📁 {item}"])
                            # 填充文件夹内容（创建子快捷方式，递归两层）
                            self.populate_folder(folder_item, source_path, item, depth=0)
                            self.tree_widget.addTopLevelItem(folder_item)
                        else:
                            # 创建文件节点
                            file_item = QTreeWidgetItem([f"📄 {item}"])
                            self.tree_widget.addTopLevelItem(file_item)
            except Exception as e:
                print(f"读取快捷方式失败 {item}: {e}")

    def populate_folder(self, parent_item, folder_path, parent_shortcut_name, depth=0):
        """填充文件夹内容（创建子快捷方式，递归两层）"""
        if depth >= 2:  # 限制递归深度为2层
            return

        try:
            # 获取文件夹内容
            entries = os.listdir(folder_path)

            # 排序：文件夹优先，然后是文件，都按首字母排序
            sorted_entries = self.sort_items_in_folder(folder_path, entries)

            for entry in sorted_entries:
                full_path = os.path.join(folder_path, entry)

                # 为文件夹内的每个项目创建快捷方式，使用父级名称作为前缀
                shortcut_name = self.create_folder_shortcut(folder_path, entry, parent_shortcut_name)
                if shortcut_name:
                    if os.path.isdir(full_path):
                        child_item = QTreeWidgetItem([f"📁 {shortcut_name}"])
                        # 如果是文件夹且未达到递归深度限制，继续填充其内容
                        if depth < 1:
                            self.populate_folder(child_item, full_path, shortcut_name, depth + 1)
                    else:
                        child_item = QTreeWidgetItem([f"📄 {shortcut_name}"])
                    parent_item.addChild(child_item)
        except PermissionError:
            # 权限不足时显示警告
            warning_item = QTreeWidgetItem(["🔒 权限不足"])
            parent_item.addChild(warning_item)
        except Exception as e:
            error_item = QTreeWidgetItem([f"❌ 错误: {str(e)[:30]}"])
            parent_item.addChild(error_item)

    def sort_items_in_folder(self, folder_path, entries):
        """对文件夹中的项目进行排序：文件夹优先，然后是文件，都按首字母排序"""
        folders = []
        files = []

        for entry in entries:
            full_path = os.path.join(folder_path, entry)
            if os.path.isdir(full_path):
                folders.append(entry)
            else:
                files.append(entry)

        # 按首字母排序
        folders.sort()
        files.sort()

        return folders + files

    def clear_sandbox(self):
        """清空沙盒目录"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空整个沙盒吗？\n\n此操作将删除所有快捷方式，不会影响原始文件。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 先获取所有快捷方式路径，用于数据库删除
            shortcut_paths = []
            for item in os.listdir(self.sandbox_dir):
                item_path = os.path.join(self.sandbox_dir, item)
                if item.endswith('.lnk'):
                    shortcut_paths.append(item_path)
            
            # 删除文件和文件夹
            for item in os.listdir(self.sandbox_dir):
                item_path = os.path.join(self.sandbox_dir, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except Exception as e:
                    print(f"删除失败: {e}")
            
            # 批量从数据库删除所有快捷方式记录
            for shortcut_path in shortcut_paths:
                try:
                    manager_database(action='delete', shortcut_path=shortcut_path)
                except Exception as e:
                    print(f"[DB] 清空沙盒时删除数据库记录失败 {shortcut_path}: {e}")
            
            self.refresh_file_list()
            self.label.setText("📁 拖拽文件/文件夹到此区域\n(右上角沙盒)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SandboxWindow()
    window.show()
    sys.exit(app.exec_())