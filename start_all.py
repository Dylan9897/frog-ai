"""
同时启动 Flask 主服务和 FastAPI ASR 服务
"""
import subprocess
import sys
import time
import os

def start_services():
    """启动所有服务"""
    processes = []
    
    try:
        # 启动 Flask 主服务
        print("[启动] Flask 主服务...")
        flask_process = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        processes.append(("Flask", flask_process))
        print(f"[启动] Flask 服务已启动 (PID: {flask_process.pid})")
        
        # 等待一下确保 Flask 启动
        time.sleep(2)
        
        # 启动 ASR 服务
        print("[启动] ASR 服务...")
        asr_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.agent.asr_server:app", "--host", "0.0.0.0", "--port", "5001"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        processes.append(("ASR", asr_process))
        print(f"[启动] ASR 服务已启动 (PID: {asr_process.pid})")

        # 启动桌面悬浮 Frog 助手（可选，不影响主服务）
        try:
            print("[启动] 桌面 Frog 助手...")
            frog_process = subprocess.Popen(
                [sys.executable, "desktop_frog.py"],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            processes.append(("FrogDesktop", frog_process))
            print(f"[启动] 桌面助手已启动 (PID: {frog_process.pid})")
        except Exception as e:
            print(f"[警告] 无法启动桌面 Frog 助手: {e}")
        
        print("\n" + "=" * 60)
        print("✅ 所有服务已启动")
        print("=" * 60)
        print("📡 Flask 主服务: http://127.0.0.1:5000")
        print("🎤 ASR WebSocket: ws://127.0.0.1:5001/ws")
        print("🐸 桌面助手: 已尝试启动（支持拖动，点击打开浏览器）")
        print("=" * 60)
        print("\n按 Ctrl+C 停止所有服务\n")
        
        # 等待进程
        while True:
            time.sleep(1)
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"[错误] {name} 服务意外退出 (退出码: {proc.returncode})")
                    return
    
    except KeyboardInterrupt:
        print("\n[停止] 正在关闭所有服务...")
        for name, proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"[停止] {name} 服务已关闭")
            except subprocess.TimeoutExpired:
                proc.kill()
                print(f"[强制停止] {name} 服务")
            except Exception as e:
                print(f"[错误] 停止 {name} 服务时出错: {e}")
        print("[停止] 所有服务已关闭")

if __name__ == "__main__":
    start_services()

