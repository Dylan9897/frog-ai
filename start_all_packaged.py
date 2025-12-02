"""
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
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {error_msg}\n")
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
            template_dir = os.path.join(sys._MEIPASS, 'templates')
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
        from agent.asr_server import app
        
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
                icon_path = get_resource_path("templates/frog.png")
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
        
        print("\n" + "=" * 60)
        print("✅ 所有服务已启动")
        print("=" * 60)
        print("📡 Flask 主服务: http://127.0.0.1:5000")
        print("🎤 ASR WebSocket: ws://127.0.0.1:5001/ws")
        print("🐸 桌面助手: 已尝试启动（支持拖动，点击打开浏览器）")
        print("=" * 60)
        print("\n程序正在运行中...\n")
        
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
            print("\n[停止] 收到停止信号，正在关闭所有服务...")
        except Exception as e:
            error_msg = f"\n[错误] 主循环异常: {e}"
            print(error_msg)
            traceback.print_exc()
            write_error_log(error_msg, "main_loop")
    
    except Exception as e:
        error_msg = f"\n[严重错误] 启动服务时发生异常: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "startup")
        print("\n程序将在10秒后退出...")
        time.sleep(10)
    finally:
        # 清理资源
        print("\n[停止] 正在关闭所有服务...")
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
        error_msg = f"\n[致命错误] 程序启动失败: {e}"
        print(error_msg)
        traceback.print_exc()
        write_error_log(error_msg, "fatal")
        # 等待一段时间，避免立即退出（无窗口模式下看不到错误）
        time.sleep(30)
