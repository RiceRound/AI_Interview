from openai import OpenAI
import json
from datetime import datetime
import time
import logging
from typing import Optional, List, Dict, Any
from config_manager import ConfigManager

class ChatGPTManager:
    # 常量定义
    TOKEN_LIMITS = {
        "4k": 4000,
        "8k": 8000,
        "16k": 16000,
        "32k": 32000
    }
    MAX_HISTORY_TOKENS = 16000  # 设置历史消息的token上限
    DEFAULT_MAX_TOKENS = 1024
    MIN_MAX_TOKENS = 1
    MAX_MAX_TOKENS = 32000  # GPT-4的最大限制
    MIN_RETRY_DELAY = 0.1
    DEFAULT_TIMEOUT = 60.0
    
    def __init__(self, api_key: Optional[str] = None):
        # 配置日志
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            print(f"Warning: Logger initialization failed: {e}")
            self.logger = None

        # 获取配置
        config = ConfigManager().get_service_config('chatgpt')
        if not api_key:
            api_key = config['api_key']
        
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url=config['base_url']
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            raise RuntimeError("OpenAI client initialization failed")
        
        self.system_messages = [
            {"role": "system", "content": config['system_prompt']}
        ]
        
        self.messages = []
        
        # 重试相关配置
        self._max_attempts = 5
        self._initial_retry_delay = max(self.MIN_RETRY_DELAY, 1.0)
        self._max_retry_delay = max(self._initial_retry_delay, 16.0)
        self._timeout = max(1.0, self.DEFAULT_TIMEOUT)
        
        # 模型配置
        self._default_max_tokens = self._validate_max_tokens(self.DEFAULT_MAX_TOKENS)
        self.model = "gpt-3.5-turbo"  # 默认使用 gpt-3.5-turbo
        
        self.current_total_tokens = 0
        self._should_stop = False

    # ... 保持其他方法与 kimi_manager.py 相同 ...

    def chat(self, input: str) -> str:
        start_time = time.time()
        attempt = 0
        retry_delay = self._initial_retry_delay
        last_error = None
        self._should_stop = False

        try:
            messages = self.make_messages(input)
        except Exception as e:
            return f"消息准备失败: {str(e)}"

        while attempt < self._max_attempts and not self._should_stop:
            attempt += 1
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,  # ChatGPT 默认温度
                    max_tokens=self._default_max_tokens
                )
                
                # 更新token计数
                if hasattr(completion, 'usage'):
                    new_tokens = completion.usage.total_tokens
                    self.current_total_tokens += completion.usage.completion_tokens
                    self.logger.info(f"📊 Updated total tokens: {self.current_total_tokens}")
                
                try:
                    used_model = getattr(completion, 'model', 'unknown')
                    usage = getattr(completion, 'usage', None)
                    
                    if usage:
                        self.logger.info(
                            f"📊 Token usage - Prompt: {usage.prompt_tokens}, "
                            f"Completion: {usage.completion_tokens}, "
                            f"Total: {usage.total_tokens}"
                        )
                    self.logger.info(f"🤖 Selected model: {used_model}")
                except Exception as e:
                    self.logger.warning(f"Failed to log usage information: {e}")
                
                if not completion.choices or not completion.choices[0].message:
                    raise ValueError("Invalid response format from API")
                
                assistant_message = {
                    "role": "assistant",
                    "content": completion.choices[0].message.content
                }
                
                if self._validate_message(assistant_message):
                    self.messages.append(assistant_message)
                
                elapsed_time = time.time() - start_time
                self.logger.info(f"\n📥 ChatGPT Response (attempt {attempt}, time: {elapsed_time:.2f}s):")
                self.logger.info(f"     {assistant_message['content']}")
                self.logger.info("="*80 + "\n")
                
                return assistant_message['content']

            except Exception as e:
                if self._should_stop:
                    self.logger.info("Stopping retry loop due to exit request")
                    return "操作已取消"
                    
                last_error = e
                elapsed_time = time.time() - start_time
                
                if elapsed_time >= self._timeout:
                    self.logger.error(f"\n❌ 总尝试时间超过 {self._timeout} 秒，停止重试")
                    break
                
                self.logger.warning(f"\n⚠️ 第 {attempt} 次尝试失败: {str(e)}")
                
                if attempt < self._max_attempts and not self._should_stop:
                    self.logger.info(f"📡 等待 {retry_delay:.1f} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, self._max_retry_delay)
        
        error_msg = f"ChatGPT 响应失败 (尝试 {attempt} 次): {str(last_error)}"
        self.logger.error(f"\n❌ Error: {error_msg}")
        self.logger.error("="*80 + "\n")
        return error_msg 