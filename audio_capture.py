import pyaudio
import numpy as np
from typing import Optional, Callable, Protocol
import time

class AudioSourceProtocol(Protocol):
    """音频源接口协议"""
    def start(self) -> None:
        """开始采集音频"""
        pass
    
    def stop(self) -> None:
        """停止采集音频"""
        pass
    
    def set_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """设置音频数据回调"""
        pass

class SystemAudioCapture(AudioSourceProtocol):
    def __init__(self, rate: int = 16000, chunk_size: int = 9600):
        self.rate = rate
        self.chunk = chunk_size
        self.running = False
        self.callback: Optional[Callable[[np.ndarray], None]] = None
        self.last_voice_time = time.time()
        self.silence_callback = None
        
    def set_callback(self, callback: Callable[[np.ndarray], None]):
        """设置音频数据回调函数"""
        self.callback = callback
    
    def set_silence_callback(self, callback):
        """设置空白检测回调"""
        self.silence_callback = callback
    
    def _find_stereo_mix_device(self, p: pyaudio.PyAudio) -> int:
        """查找立体声混音设备"""
        target = '立体声混音'
        for i in range(p.get_device_count()):
            dev_info = p.get_device_info_by_index(i)
            if dev_info['name'].find(target) >= 0 and dev_info['hostApi'] == 0:
                return i
        return -1
    
    def start(self):
        """开始采集系统音频"""
        if self.running or not self.callback:
            return
            
        self.running = True
        p = pyaudio.PyAudio()
        device_index = self._find_stereo_mix_device(p)
        
        if device_index < 0:
            raise RuntimeError("未找到立体声混音设备！")
        
        try:
            print(f"开始音频采集，采样率: {self.rate}, 块大小: {self.chunk}")
            stream = p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk
            )
            
            frame_count = 0
            last_log_time = time.time()
            
            while self.running:
                try:
                    audio_data = stream.read(self.chunk, exception_on_overflow=False)
                    audio_array = np.frombuffer(audio_data, dtype=np.float32)
                    
                    # 计算音量，只记录有声音的帧
                    volume = np.abs(audio_array).mean()
                    frame_count += 1
                    
                    current_time = time.time()
                    
                    # 每5秒打印一次状态
                    if current_time - last_log_time >= 5:
                        print(f"音频采集状态 - 已处理帧数: {frame_count}, 当前音量: {volume:.6f}")
                        last_log_time = current_time
                    
                    # 如果音量太小，可能是静音
                    if volume > 0.001:  # 可以调整这个阈值
                        print(f"检测到声音，音量: {volume:.6f}")
                        self.last_voice_time = current_time
                        self.callback(audio_array)
                    elif current_time - self.last_voice_time > 3.0:  # 超过3秒没有声音
                        if self.silence_callback:
                            print("检测到3秒静音，触发回调")
                            self.silence_callback()
                            self.last_voice_time = current_time  # 重置计时器
                    
                except Exception as e:
                    print(f"音频处理出错: {e}")
                    time.sleep(0.1)
                
        except Exception as e:
            print(f"音频流创建或处理时出错: {e}")
        finally:
            print("停止音频采集")
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    def stop(self):
        """停止音频采集"""
        self.running = False
        # 如果有其他资源需要清理，在这里处理 