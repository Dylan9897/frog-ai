"""
DashScope 实时语音识别服务
使用 paraformer-realtime-v2 模型
"""
import os
from typing import Optional, Callable
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult


class ASRService:
    """语音识别服务类"""
    
    # ASR 配置
    MODEL = 'paraformer-realtime-v2'
    FORMAT = 'pcm'
    SAMPLE_RATE = 16000
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化ASR服务
        
        Args:
            api_key: DashScope API Key，不提供则从环境变量或配置文件读取
        """
        self.api_key = api_key or self._load_api_key()
        if self.api_key:
            import dashscope
            dashscope.api_key = self.api_key
        
        self.recognition = None
        self.is_running = False
        self._callback_handler = None
    
    def _load_api_key(self) -> Optional[str]:
        """加载API Key（优先级：环境变量 > tianwa/config.py）"""
        # 1. 环境变量
        env_key = os.environ.get('DASHSCOPE_API_KEY')
        if env_key:
            return env_key.strip()
        from src.config.config import DASHSCOPE_API_KEY
        return DASHSCOPE_API_KEY
    
    def start_recognition(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        """启动语音识别会话
        
        Args:
            on_partial: 部分结果回调函数
            on_final: 最终结果回调函数
            on_error: 错误回调函数
        """
        if self.is_running:
            return
        
        if not self.api_key:
            if on_error:
                on_error('未配置 DashScope API Key')
            return
        
        self._callback_handler = ASRCallbackHandler(
            on_partial=on_partial,
            on_final=on_final,
            on_error=on_error
        )
        
        try:
            self.recognition = Recognition(
                model=self.MODEL,
                format=self.FORMAT,
                sample_rate=self.SAMPLE_RATE,
                semantic_punctuation_enabled=True,
                intermediate_result_enabled=True,
                callback=self._callback_handler
            )
            self.recognition.start()
            self.is_running = True
        except Exception as e:
            if on_error:
                on_error(f'ASR启动失败: {str(e)}')
    
    def send_audio(self, audio_data: bytes):
        """发送音频数据
        
        Args:
            audio_data: PCM 格式音频数据（16kHz, 16bit, mono）
        """
        if not self.is_running or not self.recognition:
            return
        
        try:
            self.recognition.send_audio_frame(audio_data)
        except Exception as e:
            print(f'[ASR] 发送音频失败: {e}')
            # 尝试重启
            if self.is_running:
                try:
                    self.recognition.start()
                except Exception:
                    pass
    
    def stop_recognition(self):
        """停止语音识别"""
        self.is_running = False
        if self.recognition:
            try:
                self.recognition.stop()
            except Exception:
                pass
            self.recognition = None


class ASRCallbackHandler(RecognitionCallback):
    """ASR 回调处理器"""
    
    def __init__(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error
    
    def on_open(self):
        pass
    
    def on_close(self):
        pass
    
    def on_complete(self):
        pass
    
    def on_error(self, message):
        if self.on_error:
            error_msg = f'Request ID: {message.request_id}, Message: {message.message}'
            self.on_error(error_msg)
    
    def on_event(self, result: RecognitionResult):
        """处理识别结果"""
        sentence = result.get_sentence()
        if 'text' in sentence:
            text = sentence['text']
            if text:
                if RecognitionResult.is_sentence_end(sentence):
                    # 最终结果
                    if self.on_final:
                        self.on_final(text)
                else:
                    # 部分结果
                    if self.on_partial:
                        self.on_partial(text)

