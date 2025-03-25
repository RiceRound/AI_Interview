import os
import numpy as np
from funasr import AutoModel
from typing import Optional, Callable
import time

class ASRManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ASRManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # 配置参数
        self.chunk_size = [0, 10, 5]  # 600ms
        self.encoder_chunk_look_back = 4
        self.decoder_chunk_look_back = 1
        
        # 初始化状态
        self.running = False
        self.result_callback: Optional[Callable[[str], None]] = None
        self.silence_callback: Optional[Callable[[], None]] = None  # 新增空白回调
        
        # 初始化模型
        os.environ['MODELSCOPE_OFFLINE'] = '1'  # 启用离线模式
        self.model = AutoModel(model="paraformer-zh-streaming", disable_update=True)
        self.punc_model = AutoModel(model="ct-punc", disable_update=True)
        
        # 缓存识别结果
        self.cache = {}
        self.temp_result = []
        self.last_speech_time = time.time()  # 添加最后检测到语音的时间
        
        self._initialized = True
    
    def set_result_callback(self, callback: Callable[[str], None]):
        """设置结果回调函数"""
        self.result_callback = callback
    
    def set_silence_callback(self, callback: Callable[[], None]):
        """设置空白检测回调函数"""
        self.silence_callback = callback
    
    def process_audio(self, audio_chunk: np.ndarray):
        """处理音频数据"""
        if not self.running or not self.result_callback:
            return
            
        print(f"ASR开始处理音频块，数据大小: {len(audio_chunk)}")
        start_time = time.time()
        current_time = time.time()
        
        # ASR识别
        asr_start = time.time()
        res = self.model.generate(
            input=audio_chunk,
            cache=self.cache,
            is_final=False,
            chunk_size=self.chunk_size,
            encoder_chunk_look_back=self.encoder_chunk_look_back,
            decoder_chunk_look_back=self.decoder_chunk_look_back
        )
        print(f"ASR识别耗时: {(time.time() - asr_start)*1000:.2f}ms")
        
        if res[0]["text"].strip():
            print(f"识别到文本: {res[0]['text']}")
            self.temp_result.append(res[0]["text"])
            self.last_speech_time = current_time  # 更新最后检测到文本的时间
        elif current_time - self.last_speech_time > 5.0:  # 超过5秒没有新文本
            print("检测到5秒无新文本，触发断句")
            self.handle_silence()  # 直接调用空白处理函数，让handle_silence来判断是否需要处理
        
        print(f"本次音频处理总耗时: {(time.time() - start_time)*1000:.2f}ms")
    
    def handle_silence(self):
        """处理检测到的空白"""
        current_text = "".join(self.temp_result)
        # 去除空白字符，统计实际文字数量
        word_count = len("".join(current_text.split()))
        
        if word_count >= 10:  # 检查实际单词数量
            try:
                # 标点处理
                punc_start = time.time()
                punc_res = self.punc_model.generate(input=current_text)
                print(f"标点处理耗时: {(time.time() - punc_start)*1000:.2f}ms")
                
                final_text = punc_res[0]["text"]
                print(f"最终文本: {final_text}")
                self.result_callback(final_text)
            except Exception as e:
                print(f"标点处理出错: {e}")
                self.result_callback(current_text)
            self.temp_result = []
            self.cache = {}  # 重置 ASR 缓存
    
    def start(self):
        """开始识别"""
        self.running = True
        self.cache = {}
        self.temp_result = []
    
    def stop(self):
        """停止识别"""
        self.running = False
    
    def force_generate(self):
        """强制生成当前累积的文本结果"""
        if not self.temp_result:
            return
        
        raw_text = "".join(self.temp_result)
        try:
            # 标点处理
            punc_start = time.time()
            punc_res = self.punc_model.generate(input=raw_text)
            print(f"标点处理耗时: {(time.time() - punc_start)*1000:.2f}ms")
            
            final_text = punc_res[0]["text"]
            print(f"最终文本: {final_text}")
            if self.result_callback:
                self.result_callback(final_text)
        except Exception as e:
            print(f"标点处理出错: {e}")
            if self.result_callback:
                self.result_callback(raw_text)
        self.temp_result = []
        self.cache = {}  # 重置 ASR 缓存 