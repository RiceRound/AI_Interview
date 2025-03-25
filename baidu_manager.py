import json
import logging
import time
import requests
from datetime import datetime
from typing import Optional, Dict
from config_manager import ConfigManager

class BaiduAIManager:
    def __init__(self, app_key: Optional[str] = None, app_id: Optional[str] = None):
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
        config = ConfigManager().get_service_config('baidu')
        self.app_key = app_key or config['app_key']
        self.app_id = app_id or config['app_id']
        self.base_url = config['base_url']
        self.system_prompt = config['system_prompt']
        
        # 会话相关
        self.conversation_id = None
        self.message_id = None
        self.request_id = None
        self.run_id = None
        self._should_stop = False
        self._max_attempts = 5
        self._initial_retry_delay = 1.0
        self._max_retry_delay = 16.0
        self._timeout = 60.0

    def _create_conversation(self) -> bool:
        """创建新的对话"""
        try:
            url = f"{self.base_url}/conversation"
            
            payload = json.dumps({
                "app_id": self.app_id
            }, ensure_ascii=False)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.app_key}'
            }
            
            response = requests.post(url, headers=headers, data=payload.encode("utf-8"))
            response_data = response.json()
            
            if response.status_code == 200 and 'conversation_id' in response_data:
                self.conversation_id = response_data['conversation_id']
                self.logger.info(f"Created new conversation with ID: {self.conversation_id}")
                return True
            else:
                self.logger.error(f"Failed to create conversation: {response_data}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error creating conversation: {e}")
            return False

    def _create_run(self, input: str) -> Optional[str]:
        """创建新的对话轮次"""
        try:
            url = f"{self.base_url}/conversation/runs"
            
            # 如果是第一次对话（message_id为None），添加角色设定
            if not self.message_id:
                input = (self.system_prompt + "\n\n" + input)
            
            payload = json.dumps({
                "app_id": self.app_id,
                "conversation_id": self.conversation_id,
                "stream": False,
                "query": input
            }, ensure_ascii=False)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.app_key}'
            }
            
            response = requests.post(url, headers=headers, data=payload.encode("utf-8"))
            response_data = response.json()
            
            if response.status_code == 200:
                # 更新 conversation_id（如果返回了新的）
                if 'conversation_id' in response_data:
                    self.conversation_id = response_data['conversation_id']
                
                # 更新其他重要字段并打印
                self.message_id = response_data.get('message_id')
                self.request_id = response_data.get('request_id')
                
                # 打印 message_id
                self.logger.info(f"Message ID: {self.message_id}")
                
                # 记录完整的响应内容（用于调试）
                self.logger.debug(f"Full response: {response_data}")
                
                return response_data.get('answer')
            else:
                self.logger.error(f"Failed to get answer: {response_data}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in conversation run: {e}")
            return None

    def chat(self, input: str) -> str:
        """主要的对话接口"""
        try:
            if not self.conversation_id:
                # 第一次对话，先创建会话
                if not self._create_conversation():
                    return "创建对话失败"
                # 创建成功后立即发送第一条消息
            
            # 发送消息并获取响应
            response = self._create_run(input)
            if response is None:
                return "获取回复失败"
            
            self.logger.info(f"\n📥 Baidu AI Response:")
            self.logger.info(f"     {response}")
            self.logger.info("="*80 + "\n")
            
            return response

        except Exception as e:
            self.logger.error(f"对话出错: {e}")
            return f"对话出错: {str(e)}"

    def stop(self):
        """停止所有操作"""
        self._should_stop = True
        
    def reset(self):
        """重置停止标志和会话状态"""
        self._should_stop = False
        self.conversation_id = None
        self.run_id = None 