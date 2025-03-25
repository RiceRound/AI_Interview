import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
from asr_manager import ASRManager
from audio_capture import SystemAudioCapture
from ai_service_manager import AIServiceManager
import queue
import time

class ASRApp:
    def __init__(self, root):
        self.root = root
        root.title("实时语音识别")
        
        # 添加窗体关闭事件处理
        root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化组件
        self.asr_manager = ASRManager()
        self.audio_capture = SystemAudioCapture()
        self.ai_service_manager = AIServiceManager()
        self.is_paused = False  # 添加暂停标志位
        
        # 设置回调链
        self.asr_manager.set_result_callback(self.handle_result)
        self.asr_manager.set_silence_callback(self.asr_manager.handle_silence)  # 设置空白检测回调
        self.audio_capture.set_callback(self.asr_manager.process_audio)
        self.audio_capture.set_silence_callback(self.asr_manager.handle_silence)  # 设置空白检测回调
        
        # 创建UI组件
        self._init_ui()
        
        # 音频采集线程
        self.capture_thread = None
        
        self.ai_queue = queue.Queue()  # 添加AI处理队列
        self.ai_thread = threading.Thread(target=self._process_ai_responses)
        self.ai_thread.daemon = True
        self.ai_thread.start()
    
    def _init_ui(self):
        # 创建主分栏容器
        self.paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.pack(expand=True, fill='both', padx=10, pady=10)
        
        # 左侧面板 - 语音识别结果
        self.left_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.left_frame)
        
        # 左侧文本显示区域
        self.text_area = scrolledtext.ScrolledText(self.left_frame, width=60, height=20, wrap=tk.WORD)
        self.text_area.pack(expand=True, fill='both')
        
        # 创建按钮框架，放在左侧面板底部
        self.button_frame = tk.Frame(self.left_frame)
        self.button_frame.pack(side=tk.BOTTOM, pady=5)
        
        self.start_button = tk.Button(self.button_frame, text="开始识别", command=self.start_recognition)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(self.button_frame, text="暂停", command=self.pause_recognition, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.force_button = tk.Button(self.button_frame, text="断句", command=self.force_generate, state=tk.DISABLED)
        self.force_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = tk.Button(self.button_frame, text="清空文本", command=self.clear_text)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # 右侧面板 - AI对话结果
        self.right_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.right_frame)
        
        # 创建AI服务选择框架
        self.ai_select_frame = tk.Frame(self.right_frame)
        self.ai_select_frame.pack(side=tk.BOTTOM, pady=5)
        
        # 创建AI服务复选框
        self.ai_checkboxes = {}
        self.ai_vars = {}
        for service_name in self.ai_service_manager.get_available_services():
            var = tk.BooleanVar(value=True)  # 默认选中
            self.ai_vars[service_name] = var
            cb = tk.Checkbutton(self.ai_select_frame, text=service_name, variable=var)
            cb.pack(side=tk.LEFT, padx=5)
            self.ai_checkboxes[service_name] = cb
        
        # 创建AI服务文本区域容器
        self.ai_container = tk.Frame(self.right_frame)
        self.ai_container.pack(expand=True, fill='both')
        
        # 为每个AI服务创建一个带标题的文本区域
        self.ai_text_areas = {}
        for service_name in self.ai_service_manager.get_available_services():
            # 为每个服务创建一个Frame
            service_frame = tk.Frame(self.ai_container)
            service_frame.pack(expand=True, fill='both', pady=(0, 10))
            
            # 添加标题标签
            title_label = tk.Label(service_frame, text=service_name, font=('Arial', 10, 'bold'))
            title_label.pack(anchor='w', padx=5, pady=(5, 0))
            
            # 创建文本区域
            text_area = scrolledtext.ScrolledText(service_frame, height=10, wrap=tk.WORD)
            text_area.pack(expand=True, fill='both')
            self.ai_text_areas[service_name] = text_area
    
    def handle_result(self, text: str):
        """处理识别结果"""
        if self.is_paused:  # 如果暂停状态，直接返回
            return
            
        self.text_area.insert(tk.END, text + "\n")
        self.text_area.see(tk.END)
        
        # 将AI处理任务放入队列
        task = {
            'text': text,
            'timestamp': time.time()
        }
        self.ai_queue.put(task)
    
    def _process_ai_responses(self):
        """在单独的线程中处理AI响应"""
        while True:
            try:
                task = self.ai_queue.get()
                # 检查任务是否超时（5秒）
                if time.time() - task['timestamp'] > 5.0:
                    print(f"任务超时，丢弃文本: {task['text']}")
                    continue
                
                # 处理未超时的任务
                text = task['text']
                # 对所有选中的AI服务进行处理
                for service_name, var in self.ai_vars.items():
                    if var.get():  # 如果该服务被选中
                        ai_service = self.ai_service_manager.get_service(service_name)
                        ai_response = ai_service.chat(text)
                        
                        # 使用after方法在主线程中更新UI
                        self.root.after(0, self._update_ai_text, service_name, ai_response)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理AI响应时出错: {e}")

    def _update_ai_text(self, service_name, ai_response):
        """在主线程中更新AI文本框"""
        text_area = self.ai_text_areas[service_name]
        text_area.delete(1.0, tk.END)
        text_area.insert(tk.END, f"{ai_response}\n")
        text_area.see("1.0")
    
    def start_recognition(self):
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.force_button.config(state=tk.NORMAL)  # 启用断句按钮
        
        # 启动ASR管理器
        self.asr_manager.start()
        
        # 启动音频采集
        self.capture_thread = threading.Thread(target=self.audio_capture.start)
        self.capture_thread.start()
    
    def pause_recognition(self):
        self.is_paused = not self.is_paused  # 切换暂停状态
        self.stop_button.config(text="继续" if self.is_paused else "暂停")
    
    def on_closing(self):
        """窗体关闭时的处理函数"""
        # 停止音频采集
        if self.audio_capture.running:
            self.audio_capture.stop()  # 确保 audio_capture 有 stop 方法
        
        # 停止 ASR 管理器
        if self.asr_manager:
            self.asr_manager.stop()
        
        # 停止所有 AI 服务
        for service_name in self.ai_service_manager.get_available_services():
            service = self.ai_service_manager.get_service(service_name)
            if hasattr(service, 'stop'):
                service.stop()
            
        # 等待音频采集线程结束
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)  # 等待最多2秒
        
        # 关闭窗口
        self.root.destroy()
        self.root.quit()

    def clear_text(self):
        self.text_area.delete(1.0, tk.END)
        # 清空所有AI对话框
        for text_area in self.ai_text_areas.values():
            text_area.delete(1.0, tk.END)

    def force_generate(self):
        """强制生成当前文本"""
        if not self.is_paused:  # 只在非暂停状态下生效
            self.asr_manager.force_generate()

if __name__ == "__main__":
    root = tk.Tk()
    # 设置窗口初始大小
    root.geometry("1200x600")
    app = ASRApp(root)
    root.mainloop()
