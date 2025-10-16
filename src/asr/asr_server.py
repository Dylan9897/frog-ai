"""
FastAPI ASR WebSocket 服务器
独立运行，提供实时语音识别服务
"""
import asyncio
import base64
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from .asr_service import ASRService

app = FastAPI(title="ASR Service", version="1.0.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "service": "ASR WebSocket Service"}


@app.websocket("/ws")
async def websocket_asr(websocket: WebSocket):
    """WebSocket ASR 端点"""
    await websocket.accept()
    print("[ASR WebSocket] 客户端已连接")
    
    asr_service = None
    loop = asyncio.get_event_loop()
    
    try:
        # 创建 ASR 服务
        asr_service = ASRService()
        
        # 定义回调函数
        async def on_partial(text: str):
            try:
                await websocket.send_text(json.dumps({
                    'type': 'partial',
                    'text': text
                }, ensure_ascii=False))
                print(f"[ASR] 发送部分结果: {text[:50]}...")
            except Exception as e:
                print(f"[ASR] 发送部分结果失败: {e}")
        
        async def on_final(text: str):
            try:
                await websocket.send_text(json.dumps({
                    'type': 'final',
                    'text': text
                }, ensure_ascii=False))
                print(f"[ASR] 发送最终结果: {text}")
            except Exception as e:
                print(f"[ASR] 发送最终结果失败: {e}")
        
        async def on_error(error_msg: str):
            try:
                await websocket.send_text(json.dumps({
                    'type': 'error',
                    'message': error_msg
                }, ensure_ascii=False))
            except Exception as e:
                print(f"[ASR] 发送错误消息失败: {e}")
        
        # WebSocket 状态标志
        ws_active = True
        
        # 创建线程安全的回调包装器
        def sync_on_partial(text: str):
            if ws_active:
                try:
                    asyncio.run_coroutine_threadsafe(on_partial(text), loop)
                except Exception as e:
                    print(f"[ASR] 调度 partial 回调失败: {e}")
        
        def sync_on_final(text: str):
            if ws_active:
                try:
                    asyncio.run_coroutine_threadsafe(on_final(text), loop)
                except Exception as e:
                    print(f"[ASR] 调度 final 回调失败: {e}")
        
        def sync_on_error(error_msg: str):
            if ws_active:
                try:
                    asyncio.run_coroutine_threadsafe(on_error(error_msg), loop)
                except Exception as e:
                    print(f"[ASR] 调度 error 回调失败: {e}")
        
        # 启动识别
        asr_service.start_recognition(
            on_partial=sync_on_partial,
            on_final=sync_on_final,
            on_error=sync_on_error
        )
        
        # 接收并处理音频数据
        while True:
            try:
                message = await websocket.receive_text()
                
                # 解析消息
                try:
                    data = json.loads(message)
                    if data.get('type') == 'audio':
                        # base64 解码音频数据
                        audio_b64 = data.get('data', '')
                        audio_bytes = base64.b64decode(audio_b64)
                        asr_service.send_audio(audio_bytes)
                    elif data.get('type') == 'stop':
                        print("[ASR WebSocket] 收到停止信号，准备结束识别并发送最终结果…")
                        # 优雅停止识别，等待最终结果回调发送完成
                        try:
                            asr_service.stop_recognition()
                        except Exception as e:
                            print(f"[ASR] stop_recognition 出错: {e}")
                        # 等待回调线程把最终结果通过 websocket 发送出去
                        await asyncio.sleep(0.8)
                        # 关闭前阻止继续发送
                        ws_active = False
                        try:
                            await websocket.close()
                        except Exception:
                            pass
                        print("[ASR WebSocket] 已关闭连接")
                        break
                except json.JSONDecodeError:
                    # 兼容直接发送 base64 字符串的情况
                    audio_bytes = base64.b64decode(message)
                    asr_service.send_audio(audio_bytes)
                    
            except WebSocketDisconnect:
                print("[ASR WebSocket] 客户端断开连接")
                break
            except Exception as e:
                print(f"[ASR WebSocket] 接收消息错误: {e}")
                break
    
    except Exception as e:
        print(f"[ASR WebSocket] 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 标记 WebSocket 为非活动状态
        ws_active = False
        
        # 清理
        if asr_service:
            asr_service.stop_recognition()
        print("[ASR WebSocket] 连接已关闭")


def start_server(host: str = "0.0.0.0", port: int = 5001):
    """启动 ASR 服务器"""
    print("=" * 60)
    print("🎤 ASR WebSocket 服务启动")
    print("=" * 60)
    print(f"WebSocket 地址: ws://{host}:{port}/ws")
    print(f"健康检查: http://{host}:{port}/")
    print("=" * 60)
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()

