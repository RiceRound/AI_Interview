import asyncio
import json
import logging
import re
import ssl
import time
import uuid
import certifi
import websockets
from datetime import datetime
from typing import Optional, List, Dict, Any
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.lke.v20231130 import lke_client, models
from config_manager import ConfigManager

class TencentAIManager:
    def __init__(self, bot_app_key: Optional[str] = None, visitor_biz_id: Optional[str] = None,
                 secret_id: Optional[str] = None, secret_key: Optional[str] = None):
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
        config = ConfigManager().get_service_config('tencent')
        self.bot_app_key = bot_app_key or config['bot_app_key']
        self.visitor_biz_id = visitor_biz_id or config['visitor_biz_id']
        self.secret_id = secret_id or config['secret_id']
        self.secret_key = secret_key or config['secret_key']
        self.region = config['region']
        self.conn_type_api = 5

        # SSL配置
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.load_verify_locations(certifi.where())

        # 会话相关
        self.messages = []
        self._should_stop = False
        self._max_attempts = 5
        self._initial_retry_delay = 1.0
        self._max_retry_delay = 16.0
        self._timeout = 60.0

    def _get_session(self):
        return str(uuid.uuid1())

    def _get_request_id(self):
        return str(uuid.uuid1())

    def _get_api_token(self) -> Optional[str]:
        """获取API Token"""
        try:
            cred = credential.Credential(self.secret_id, self.secret_key)
            httpProfile = HttpProfile()
            httpProfile.endpoint = "lke.tencentcloudapi.com"

            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            
            client = lke_client.LkeClient(cred, self.region, clientProfile)

            req = models.GetWsTokenRequest()
            params = {
                "Type": self.conn_type_api,
                "BotAppKey": self.bot_app_key,
                "VisitorBizId": self.visitor_biz_id
            }
            req.from_json_string(json.dumps(params))
            
            resp = client.GetWsToken(req)
            self.logger.info(f"Successfully obtained API token")
            return resp.Token
        except Exception as e:
            self.logger.error(f"Failed to get API token: {e}")
            return None

    async def _websocket_chat(self, token: str, message: str) -> str:
        """通过WebSocket进行对话"""
        url = f"wss://wss.lke.cloud.tencent.com/v1/qbot/chat/conn/?EIO=4&transport=websocket"
        pattern = r'\d+(.*)'
        response_content = ""

        try:
            async with websockets.connect(url, ssl=self.ssl_context) as ws:
                # 建立连接
                response = await ws.recv()
                self.logger.info(f"Connection established: {response}")

                # 发送认证
                auth = {"token": token}
                auth_message = f"40{json.dumps(auth)}"
                await ws.send(auth_message)
                
                # 接收认证响应
                response = await ws.recv()
                self.logger.info(f"Authentication result: {response}")

                # 发送消息
                session_id = self._get_session()
                request_id = self._get_request_id()
                payload = {
                    "payload": {
                        "request_id": request_id,
                        "session_id": session_id,
                        "content": message,
                    }
                }
                req_data = ["send", payload]
                send_data = f"42{json.dumps(req_data, ensure_ascii=False)}"
                await ws.send(send_data)

                # 接收响应
                while True:
                    if self._should_stop:
                        return "操作已取消"

                    rsp = await ws.recv()
                    if rsp == '2':
                        await ws.send("3")  # 心跳响应
                        continue
                    
                    rsp_re_result = re.search(pattern, rsp)
                    if not rsp_re_result:
                        continue
                        
                    rsp_dict = json.loads(rsp_re_result.group(1))
                    
                    if rsp_dict[0] == "error":
                        self.logger.error(f"Error response: {rsp_dict}")
                        return f"错误: {rsp_dict}"
                    
                    elif rsp_dict[0] == "reply":
                        payload = rsp_dict[1]["payload"]
                        if payload["is_from_self"]:
                            continue
                            
                        if payload["is_final"]:
                            response_content = payload["content"]
                            break

                return response_content

        except Exception as e:
            self.logger.error(f"WebSocket chat failed: {e}")
            return f"对话失败: {str(e)}"

    def chat(self, input: str) -> str:
        """主要的对话接口"""
        try:
            # 获取token
            token = self._get_api_token()
            if not token:
                return "获取 API token 失败"

            # 执行异步WebSocket对话
            response = asyncio.run(self._websocket_chat(token, input))
            
            self.logger.info(f"\n📥 Tencent AI Response:")
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
        """重置停止标志"""
        self._should_stop = False 