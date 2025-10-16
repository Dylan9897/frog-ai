"""
统一启动脚本
同时启动 Flask 主服务和 FastAPI ASR 服务
"""
import subprocess
import sys
import time
import os

if __name__ == "__main__":
    print("=" * 70)
    print("🐸 Frog AI 完整服务启动")
    print("=" * 70)
    print("正在启动两个服务：")
    print("  1. Flask 主服务 (http://localhost:5000)")
    print("  2. FastAPI ASR 服务 (ws://localhost:5001/ws)")
    print("=" * 70)
    print()
    
    processes = []
    
    # 添加 src 到 Python 路径
    src_dir = os.path.join(os.path.dirname(__file__), 'src')
    
    try:
        # 启动 Flask 主服务
        print("[启动] Flask 主服务...")
        flask_process = subprocess.Popen(
            [sys.executable, os.path.join(src_dir, "main.py")]
        )
        processes.append(("Flask", flask_process))
        time.sleep(2)  # 等待 Flask 启动
        
        # 启动 ASR 服务
        print("[启动] ASR 服务...")
        asr_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "asr.asr_server:app", 
             "--host", "0.0.0.0", "--port", "5001"],
            cwd=src_dir
        )
        processes.append(("ASR", asr_process))
        
        print("\n" + "=" * 70)
        print("✅ 所有服务已启动！")
        print("=" * 70)
        print("访问: http://localhost:5000/tianwa")
        print("按 Ctrl+C 停止所有服务")
        print("=" * 70)
        
        # 持续监控进程
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n[错误] {name} 服务异常退出 (返回码: {proc.returncode})")
                    # 输出错误日志
                    stderr = proc.stderr.read()
                    if stderr:
                        print(f"[{name} 错误日志]:\n{stderr}")
                    # 停止所有服务
                    raise KeyboardInterrupt
            time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("⏹️  正在停止所有服务...")
        print("=" * 70)
        for name, proc in processes:
            if proc.poll() is None:
                print(f"[停止] {name} 服务...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"[强制停止] {name} 服务...")
                    proc.kill()
        print("✅ 所有服务已关闭")
    except Exception as e:
        print(f"\n[错误] 启动失败: {e}")
        for name, proc in processes:
            if proc.poll() is None:
                proc.terminate()

