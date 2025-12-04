"""
使用 PyInstaller 将项目打包成 exe 可执行文件

使用方法:
    python build.py

打包后的文件将输出到 dist/ 目录
"""
import os
import sys
import shutil
import subprocess
import traceback
import io

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_ROOT, 'dist')
BUILD_DIR = os.path.join(PROJECT_ROOT, 'build')
SPEC_DIR = os.path.join(PROJECT_ROOT, 'spec')

def check_pyinstaller():
    """检查 PyInstaller 是否已安装"""
    try:
        import PyInstaller
        print("✅ PyInstaller 已安装")
        return True
    except ImportError:
        print("❌ PyInstaller 未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller 安装完成")
        return True

def clean_build_dirs():
    """清理之前的构建目录"""
    print("\n🧹 清理构建目录...")
    for dir_path in [DIST_DIR, BUILD_DIR, SPEC_DIR]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"   已删除: {dir_path}")
    print("✅ 清理完成\n")

def create_packaged_start_script():
    """创建专门用于打包环境的启动脚本"""
    script_content = '''"""
打包环境专用启动脚本
在打包后的 exe 中，直接导入并运行服务，避免 subprocess 递归调用
"""
import sys
import os
import time
import threading
import multiprocessing
import traceback
import io

def fix_stdout_stderr():
    """修复无窗口模式下的 stdout/stderr 问题"""
    if sys.stdout is None:
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
    if sys.stderr is None:
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')

def setup_packaged_environment():
    """设置打包环境（路径和输出流）"""
    fix_stdout_stderr()
    if hasattr(sys, '_MEIPASS'):
        if sys._MEIPASS not in sys.path:
            sys.path.insert(0, sys._MEIPASS)

def get_base_path():
    """获取基础路径（支持打包环境）"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后，exe 所在目录（用于存储用户数据）
        exe_dir = os.path.dirname(sys.executable)
        os.makedirs(exe_dir, exist_ok=True)
        return exe_dir
    else:
        # 开发环境，脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """获取资源文件路径（支持 PyInstaller 打包环境）"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def write_error_log(error_msg, error_type="error"):
    """写入错误日志到文件"""
    try:
        log_file = os.path.join(get_base_path(), f'{error_type}_error.log')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {error_msg}\\n")
            traceback.print_exc(file=f)
    except:
        pass

def start_flask_server():
    """在独立线程中启动 Flask 服务"""
    try:
        import server
        from flask import send_from_directory
        # 修复模板路径
        if hasattr(sys, '_MEIPASS'):
            template_dir = os.path.join(sys._MEIPASS, 'config', 'templates')
            server.app.template_folder = template_dir
            # 替换 index 函数的实现（不重新定义路由，避免冲突）
            def patched_index():
                """根路由：返回 index.html 文件（打包环境版本）"""
                return send_from_directory(template_dir, 'index.html')
            server.index = patched_index
            server.app.view_functions['index'] = patched_index
        base_path = get_base_path()
        os.chdir(base_path)
        server.app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        error_msg = f"[错误] Flask 服务启动失败: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "flask")

def start_asr_server():
    """在线程中启动 ASR 服务"""
    try:
        setup_packaged_environment()
        
        import uvicorn
        import asyncio
        from src.agent.asr_server import app
        
        base_path = get_base_path()
        os.chdir(base_path)
        
        print(f"[ASR] 准备启动服务，工作目录: {base_path}")
        
        # 在线程中运行 uvicorn，需要创建新的事件循环
        # 禁用 uvicorn 的日志配置，避免 stdout/stderr 问题
        config = uvicorn.Config(
            app, 
            host="0.0.0.0", 
            port=5001, 
            log_level="info",
            log_config=None  # 禁用默认日志配置，避免 stdout/stderr 问题
        )
        server = uvicorn.Server(config)
        
        # 创建新的事件循环（线程中需要）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        print("[ASR] 事件循环已创建，开始运行服务器...")
        loop.run_until_complete(server.serve())
    except ImportError as e:
        error_msg = f"[错误] ASR 服务导入失败: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "asr")
        time.sleep(5)
    except Exception as e:
        error_msg = f"[错误] ASR 服务启动失败: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "asr")
        time.sleep(5)

def start_desktop_frog():
    """在独立进程中启动桌面助手"""
    try:
        import desktop_frog
        # 修复图标路径
        if hasattr(sys, '_MEIPASS'):
            def get_icon_path():
                icon_path = get_resource_path("config/templates/frog.png")
                fallback_path = get_resource_path("big_eye_robot.png")
                if not os.path.exists(icon_path):
                    icon_path = fallback_path
                return icon_path
            # 临时替换 PROJECT_ROOT 的查找逻辑
            desktop_frog.PROJECT_ROOT = os.path.dirname(sys.executable)
            # 在 FloatingFrog.__init__ 中修复图标路径
            original_init = desktop_frog.FloatingFrog.__init__
            def patched_init(self, url="http://127.0.0.1:5000"):
                original_init(self, url)
                # 重新加载图标
                icon_path = get_icon_path()
                pix = desktop_frog.QPixmap(icon_path)
                if not pix.isNull():
                    target_size = 120
                    pix = pix.scaled(
                        target_size, target_size,
                        desktop_frog.Qt.KeepAspectRatio,
                        desktop_frog.Qt.SmoothTransformation,
                    )
                    self.label.setPixmap(pix)
                    self.resize(pix.width(), pix.height())
            desktop_frog.FloatingFrog.__init__ = patched_init
        base_path = get_base_path()
        os.chdir(base_path)
        desktop_frog.main()
    except Exception as e:
        error_msg = f"[错误] 桌面助手启动失败: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "desktop_frog")

def start_services():
    """启动所有服务"""
    try:
        base_path = get_base_path()
        os.chdir(base_path)
    except Exception as e:
        print(f"[错误] 设置工作目录失败: {e}")
        traceback.print_exc()
        # 即使失败也继续，使用默认目录
    
    threads = []
    processes = []
    
    try:
        # 启动 Flask 主服务（在线程中运行）
        print("[启动] Flask 主服务...")
        flask_thread = threading.Thread(target=start_flask_server, daemon=False)  # 改为非 daemon，确保主线程等待
        flask_thread.start()
        threads.append(("Flask", flask_thread))
        print(f"[启动] Flask 服务已启动 (线程)")
        
        # 等待一下确保 Flask 启动
        time.sleep(2)
        
        # 启动 ASR 服务（在线程中运行，避免无窗口模式下 multiprocessing 的问题）
        print("[启动] ASR 服务...")
        try:
            asr_thread = threading.Thread(target=start_asr_server, daemon=False)
            asr_thread.start()
            threads.append(("ASR", asr_thread))
            print(f"[启动] ASR 服务已启动 (线程)")
        except Exception as e:
            error_msg = f"[错误] ASR 服务启动失败: {e}"
            print(error_msg)
            traceback.print_exc()
            write_error_log(error_msg, "asr")

        # 启动桌面悬浮 Frog 助手（可选，不影响主服务）
        try:
            print("[启动] 桌面 Frog 助手...")
            frog_process = multiprocessing.Process(target=start_desktop_frog, daemon=False)
            frog_process.start()
            processes.append(("FrogDesktop", frog_process))
            print(f"[启动] 桌面助手已启动 (PID: {frog_process.pid})")
        except Exception as e:
            error_msg = f"[警告] 无法启动桌面 Frog 助手: {e}"
            print(error_msg)
            traceback.print_exc()
            write_error_log(error_msg, "desktop_frog")
        
        print("\\n" + "=" * 60)
        print("✅ 所有服务已启动")
        print("=" * 60)
        print("📡 Flask 主服务: http://127.0.0.1:5000")
        print("🎤 ASR WebSocket: ws://127.0.0.1:5001/ws")
        print("🐸 桌面助手: 已尝试启动（支持拖动，点击打开浏览器）")
        print("=" * 60)
        print("\\n程序正在运行中...\\n")
        
        # 主循环：保持程序运行，监控线程和进程状态
        try:
            while True:
                time.sleep(5)  # 每5秒检查一次
                # 检查进程状态（桌面助手等）
                for name, proc in processes[:]:  # 使用切片复制列表，避免迭代时修改
                    if not proc.is_alive():
                        print(f"[警告] {name} 服务意外退出，但程序继续运行")
                        processes.remove((name, proc))
                # 检查线程状态（Flask、ASR 等）
                for name, thread in threads[:]:
                    if not thread.is_alive():
                        print(f"[警告] {name} 线程已停止，但程序继续运行")
                        threads.remove((name, thread))
        except KeyboardInterrupt:
            print("\\n[停止] 收到停止信号，正在关闭所有服务...")
        except Exception as e:
            error_msg = f"\\n[错误] 主循环异常: {e}"
            print(error_msg)
            traceback.print_exc()
            write_error_log(error_msg, "main_loop")
    
    except Exception as e:
        error_msg = f"\\n[严重错误] 启动服务时发生异常: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "startup")
        print("\\n程序将在10秒后退出...")
        time.sleep(10)
    finally:
        # 清理资源
        print("\\n[停止] 正在关闭所有服务...")
        for name, proc in processes:
            try:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=5)
                    if proc.is_alive():
                        proc.kill()
                        print(f"[强制停止] {name} 服务")
                    else:
                        print(f"[停止] {name} 服务已关闭")
            except Exception as e:
                print(f"[错误] 停止 {name} 服务时出错: {e}")
        print("[停止] 所有服务已关闭")

if __name__ == "__main__":
    try:
        setup_packaged_environment()
        multiprocessing.freeze_support()
        start_services()
    except Exception as e:
        error_msg = f"\\n[致命错误] 程序启动失败: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "fatal")
        # 等待一段时间，避免立即退出（无窗口模式下看不到错误）
        time.sleep(30)
'''
    script_path = os.path.join(PROJECT_ROOT, 'start_all_packaged.py')
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    print(f"✅ 已创建打包启动脚本: {script_path}")
    return script_path

def build_exe():
    """使用 PyInstaller 打包"""
    print("🔨 开始打包...\n")
    
    # 创建打包专用启动脚本
    packaged_script = create_packaged_start_script()
    
    # 是否显示控制台窗口（True=显示，False=隐藏）
    # 打包后不显示控制台窗口（隐藏控制台）
    SHOW_CONSOLE = False
    
    # PyInstaller 命令参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=frog-ai",                    # 生成的 exe 名称
        "--onefile",                         # 打包成单个 exe 文件
    ]
    
    # 根据配置决定是否显示控制台
    # 如果需要调试，可以将 SHOW_CONSOLE 改为 True
    if not SHOW_CONSOLE:
        cmd.append("--windowed")             # Windows 下不显示控制台窗口
        cmd.append("--noconsole")            # 不显示控制台
    
    # 添加数据文件
    cmd.append("--add-data")
    cmd.append(f"config/templates{os.pathsep}config/templates")           # HTML 模板
    cmd.append("--add-data")
    cmd.append(f"config/templates/frog.png{os.pathsep}config/templates")  # 桌面助手图标
    
    # 添加隐藏导入（PyInstaller 可能无法自动检测到的模块）
    cmd.extend([
        "--hidden-import=flask",
        "--hidden-import=flask_cors",
        "--hidden-import=dashscope",
        "--hidden-import=fastapi",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=PyQt5",
        "--hidden-import=PyQt5.QtCore",
        "--hidden-import=PyQt5.QtGui",
        "--hidden-import=PyQt5.QtWidgets",
        "--hidden-import=docx",
        "--hidden-import=openpyxl",
        "--hidden-import=src.agent",
        "--hidden-import=src.agent.chat",
        "--hidden-import=src.agent.file_parser",
        "--hidden-import=src.agent.asr_server",
        "--hidden-import=src.agent.asr_service",
        "--hidden-import=src.agent.config",
        "--hidden-import=src.agent.intent_tools",
        "--hidden-import=src.databases",
        "--hidden-import=src.databases.user_db",
        "--hidden-import=config.app_config",
    ])
    
    # 收集所有子模块
    cmd.extend([
        "--collect-all=flask",
        "--collect-all=fastapi",
        "--collect-all=uvicorn",
        "--collect-all=PyQt5",
    ])
    
    # 使用打包专用启动脚本
    cmd.append(packaged_script)
    
    # 如果 big_eye_robot.png 存在，也添加到资源中
    big_eye_robot_path = os.path.join(PROJECT_ROOT, "big_eye_robot.png")
    if os.path.exists(big_eye_robot_path):
        idx = cmd.index(packaged_script)
        cmd.insert(idx, f"big_eye_robot.png{os.pathsep}.")
        cmd.insert(idx, "--add-data")
    
    try:
        subprocess.check_call(cmd, cwd=PROJECT_ROOT)
        print("\n✅ 打包完成！")
        print(f"📦 可执行文件位置: {os.path.join(DIST_DIR, 'frog-ai.exe')}")
        
        # 清理临时脚本（可选，也可以保留用于调试）
        # os.remove(packaged_script)
        # print(f"🧹 已清理临时脚本: {packaged_script}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包失败: {e}")
        return False

def create_runtime_dirs():
    """在 dist 目录中创建运行时需要的目录结构"""
    print("\n📁 创建运行时目录...")
    exe_dir = os.path.join(DIST_DIR, 'frog-ai')
    if not os.path.exists(exe_dir):
        exe_dir = DIST_DIR  # 如果 onefile 模式，exe 直接在 dist 目录
    
    # 创建必要的目录（这些目录会在运行时由程序自动创建，但提前创建也没问题）
    data_dir = os.path.join(exe_dir, 'data')
    dirs_to_create = ['uploads', 'cache', 'sandbox_shortcuts']
    for dir_name in dirs_to_create:
        dir_path = os.path.join(data_dir, dir_name)
        os.makedirs(dir_path, exist_ok=True)
        print(f"   ✅ data/{dir_name}/")
    
    # 复制 shortcuts.json 如果存在
    shortcuts_src = os.path.join(PROJECT_ROOT, 'data', 'sandbox_shortcuts', 'shortcuts.json')
    shortcuts_dst = os.path.join(data_dir, 'sandbox_shortcuts', 'shortcuts.json')
    if os.path.exists(shortcuts_src):
        os.makedirs(os.path.dirname(shortcuts_dst), exist_ok=True)
        shutil.copy2(shortcuts_src, shortcuts_dst)
        print(f"   ✅ 已复制 shortcuts.json")
    
    print("✅ 目录创建完成\n")

def create_readme():
    """在 dist 目录创建使用说明"""
    readme_content = """# Frog AI 使用说明

## 运行方式

直接双击 `frog-ai.exe` 即可启动所有服务。

## 服务说明

启动后会自动运行以下服务：
- Flask 主服务: http://127.0.0.1:5000
- ASR WebSocket 服务: ws://127.0.0.1:5001/ws
- 桌面悬浮助手（可选）

## 配置要求

1. 确保已配置 DashScope API Key（在 src/agent/config.py 中）
2. 首次运行会自动创建以下目录：
   - data/uploads/ - 沙盒文件存储
   - data/cache/ - 对话附件存储
   - data/sandbox_shortcuts/ - 快捷方式配置

## 注意事项

- 如果遇到防火墙提示，请允许程序访问网络
- 确保端口 5000 和 5001 未被占用
- 关闭程序时请使用 Ctrl+C 或直接关闭窗口

## 故障排除

如果程序无法启动：
1. 检查是否有杀毒软件拦截
2. 查看是否有错误日志输出
3. 确认 Python 环境依赖已正确打包

"""
    readme_path = os.path.join(DIST_DIR, 'README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"📄 已创建使用说明: {readme_path}\n")

def main():
    """主函数"""
    print("=" * 60)
    print("🐸 Frog AI 打包工具")
    print("=" * 60)
    
    # 检查 PyInstaller
    if not check_pyinstaller():
        print("❌ PyInstaller 安装失败，请手动安装: pip install pyinstaller")
        return
    
    # 清理构建目录
    clean_build_dirs()
    
    # 打包
    if not build_exe():
        print("❌ 打包失败，请检查错误信息")
        return
    
    # 创建运行时目录
    create_runtime_dirs()
    
    # 创建使用说明
    create_readme()
    
    print("=" * 60)
    print("🎉 打包流程完成！")
    print("=" * 60)
    print(f"📦 输出目录: {DIST_DIR}")
    print(f"🚀 可执行文件: {os.path.join(DIST_DIR, 'frog-ai.exe')}")
    print("\n💡 提示: 如果需要在打包时显示控制台窗口（方便调试），")
    print("   请修改 build.py 中的 SHOW_CONSOLE = True")
    print("=" * 60)

if __name__ == "__main__":
    main()

