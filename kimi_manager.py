from openai import OpenAI
import json
from datetime import datetime
import time
import logging
from typing import Optional, List, Dict, Any
from config_manager import ConfigManager

class AIManager:
    # 常量定义
    TOKEN_LIMITS = {
        "8k": 8000,
        "32k": 32000,
        "128k": 128000
    }
    MAX_HISTORY_TOKENS = 30000  # 设置历史消息的token上限
    DEFAULT_MAX_TOKENS = 1024
    MIN_MAX_TOKENS = 1
    MAX_MAX_TOKENS = 128000  # 128k模型的最大限制
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
        config = ConfigManager().get_service_config('kimi')
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
        
        # 重试相关配置（添加参数验证）
        self._max_attempts = 5
        self._initial_retry_delay = max(self.MIN_RETRY_DELAY, 1.0)
        self._max_retry_delay = max(self._initial_retry_delay, 16.0)
        self._timeout = max(1.0, self.DEFAULT_TIMEOUT)
        
        # 模型配置
        self._default_max_tokens = self._validate_max_tokens(self.DEFAULT_MAX_TOKENS)
        self.model = "moonshot-v1-auto"
        
        self.current_total_tokens = 0  # 添加token计数器
        self._should_stop = False  # 添加停止标志

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    @max_attempts.setter
    def max_attempts(self, value: int):
        self._max_attempts = max(1, int(value))

    def _validate_max_tokens(self, tokens: int) -> int:
        """验证并规范化max_tokens参数"""
        try:
            tokens = int(tokens)
            return max(self.MIN_MAX_TOKENS, min(tokens, self.MAX_MAX_TOKENS))
        except (TypeError, ValueError):
            self.logger.warning(f"Invalid max_tokens value: {tokens}, using default")
            return self.DEFAULT_MAX_TOKENS

    def _validate_message(self, message: Dict[str, str]) -> bool:
        """验证消息格式是否正确"""
        required_keys = {"role", "content"}
        valid_roles = {"system", "user", "assistant"}
        
        try:
            if not all(key in message for key in required_keys):
                return False
            if not message["role"] in valid_roles:
                return False
            if not isinstance(message["content"], str):
                return False
            if not message["content"].strip():
                return False
            return True
        except Exception:
            return False

    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """估算token数量，添加安全检查"""
        try:
            # 过滤无效消息
            valid_messages = [msg for msg in messages if self._validate_message(msg)]
            total_chars = sum(len(msg["content"]) for msg in valid_messages)
            # 粗略估算：假设平均每个字符占用1.5个token
            estimated_tokens = int(total_chars * 1.5)
            return max(1, estimated_tokens)  # 确保至少返回1
        except Exception as e:
            self.logger.error(f"Token estimation failed: {e}")
            return self.DEFAULT_MAX_TOKENS

    def _should_trim_history(self, new_tokens: int) -> bool:
        """检查是否需要裁剪历史消息"""
        return (self.current_total_tokens + new_tokens) > self.MAX_HISTORY_TOKENS

    def _trim_history(self, required_tokens: int) -> None:
        """
        裁剪历史消息以确保不超过token限制
        保留system message和最新的消息，从最早的历史消息开始删除
        """
        if not self.messages:
            return

        # 保留system messages
        system_messages = [msg for msg in self.messages if msg["role"] == "system"]
        history_messages = [msg for msg in self.messages if msg["role"] != "system"]

        while (self.current_total_tokens > self.MAX_HISTORY_TOKENS - required_tokens
               and history_messages):
            # 移除最早的消息
            removed_msg = history_messages.pop(0)
            removed_tokens = self.estimate_tokens([removed_msg])
            self.current_total_tokens -= removed_tokens
            self.logger.warning(f"🔄 Removing old message to stay within token limit "
                              f"(removed {removed_tokens} tokens)")

        # 重建消息列表
        self.messages = system_messages + history_messages

    def make_messages(self, input: str, n: int = 20) -> list[dict]:
        try:
            # 输入验证
            if not isinstance(input, str) or not input.strip():
                raise ValueError("Invalid input: empty or not a string")
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info("="*80)
            self.logger.info(f"🕒 {timestamp}")
            self.logger.info(f"📝 New User Input: {input}")
            
            # 创建新消息
            new_message = {
                "role": "user",
                "content": input.strip(),
            }
            
            if not self._validate_message(new_message):
                raise ValueError("Invalid message format")
            
            # 构建完整的消息列表（包括新消息）
            new_messages = []
            new_messages.extend(self.system_messages)
            new_messages.extend(self.messages)
            new_messages.append(new_message)
            
            # 计算整个对话的token数量
            total_tokens = self.estimate_tokens(new_messages)
            self.logger.info(f"📊 Total conversation tokens: {total_tokens}")
            
            # 如果超过限制，开始裁剪历史消息
            while total_tokens > self.MAX_HISTORY_TOKENS and len(self.messages) > 0:
                # 跳过system messages，从最早的历史消息开始删除
                removed_msg = self.messages.pop(0)
                removed_tokens = self.estimate_tokens([removed_msg])
                total_tokens -= removed_tokens
                self.logger.warning(
                    f"🔄 Removing old message to stay within token limit "
                    f"(removed {removed_tokens} tokens, remaining {total_tokens} tokens)"
                )
            
            # 添加新消息到历史记录
            self.messages.append(new_message)
            
            # 重新构建最终的消息列表
            final_messages = []
            final_messages.extend(self.system_messages)
            final_messages.extend(self.messages)
            
            # 记录最终的token使用情况
            final_tokens = self.estimate_tokens(final_messages)
            self.logger.info(f"📊 Final conversation tokens: {final_tokens}")
            
            # 记录消息内容
            self._log_messages(final_messages)
            
            return final_messages
            
        except Exception as e:
            self.logger.error(f"Message preparation failed: {e}")
            # 返回最小可用的消息列表
            return self.system_messages + [new_message]

    def _log_messages(self, messages: List[Dict[str, str]]) -> None:
        """安全地记录消息"""
        try:
            self.logger.info("\n📤 Sending context to Kimi:")
            for idx, msg in enumerate(messages):
                if not self._validate_message(msg):
                    continue
                    
                role = msg["role"]
                content = msg["content"]
                prefix = {
                    "system": "  🔧 System:",
                    "user": f"  👤 User {idx}:",
                    "assistant": f"  🤖 Assistant {idx}:"
                }.get(role, f"  ❓ Unknown {idx}:")
                
                self.logger.info(f"\n{prefix}")
                truncated_content = content[:100] + "..." if len(content) > 100 else content
                self.logger.info(f"     {truncated_content}")
        except Exception as e:
            self.logger.error(f"Message logging failed: {e}")

    def stop(self):
        """停止所有操作"""
        self._should_stop = True
        
    def reset(self):
        """重置停止标志"""
        self._should_stop = False

    def chat(self, input: str) -> str:
        start_time = time.time()
        attempt = 0
        retry_delay = self._initial_retry_delay
        last_error = None
        self._should_stop = False  # 重置停止标志

        try:
            messages = self.make_messages(input)
        except Exception as e:
            return f"消息准备失败: {str(e)}"

        while attempt < self._max_attempts and not self._should_stop:  # 添加停止条件
            attempt += 1
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=self._default_max_tokens
                )
                
                # 更新token计数
                if hasattr(completion, 'usage'):
                    new_tokens = completion.usage.total_tokens
                    self.current_total_tokens += completion.usage.completion_tokens
                    self.logger.info(f"📊 Updated total tokens: {self.current_total_tokens}")
                
                try:
                    # 获取使用信息
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
                
                # 验证响应格式
                if not completion.choices or not completion.choices[0].message:
                    raise ValueError("Invalid response format from API")
                
                assistant_message = {
                    "role": "assistant",
                    "content": completion.choices[0].message.content
                }
                
                if self._validate_message(assistant_message):
                    self.messages.append(assistant_message)
                
                elapsed_time = time.time() - start_time
                self.logger.info(f"\n📥 Kimi's Response (attempt {attempt}, time: {elapsed_time:.2f}s):")
                self.logger.info(f"     {assistant_message['content']}")
                self.logger.info("="*80 + "\n")
                
                return assistant_message['content']

            except Exception as e:
                if self._should_stop:  # 检查是否需要立即停止
                    self.logger.info("Stopping retry loop due to exit request")
                    return "操作已取消"
                    
                last_error = e
                elapsed_time = time.time() - start_time
                
                if elapsed_time >= self._timeout:
                    self.logger.error(f"\n❌ 总尝试时间超过 {self._timeout} 秒，停止重试")
                    break
                
                self.logger.warning(f"\n⚠️ 第 {attempt} 次尝试失败: {str(e)}")
                
                if attempt < self._max_attempts and not self._should_stop:  # 添加停止条件
                    self.logger.info(f"📡 等待 {retry_delay:.1f} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, self._max_retry_delay)
        
        error_msg = f"AI 响应失败 (尝试 {attempt} 次): {str(last_error)}"
        self.logger.error(f"\n❌ Error: {error_msg}")
        self.logger.error("="*80 + "\n")
        return error_msg 