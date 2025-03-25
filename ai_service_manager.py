from kimi_manager import AIManager as KimiManager
from tencent_manager import TencentAIManager
from baidu_manager import BaiduAIManager
from chatgpt_manager import ChatGPTManager
from config_manager import ConfigManager
# 后续可以导入其他AI管理器
# from claude_manager import ClaudeManager

class AIServiceManager:
    def __init__(self):
        # 确保配置已加载
        ConfigManager()
        self.ai_services = {
            'Kimi': KimiManager(),
            'TencentAI': TencentAIManager(),
            'BaiduAI': BaiduAIManager(),
            # 'ChatGPT': ChatGPTManager(),
            # 后续可以添加其他AI服务
            # 'Claude': ClaudeManager(),
        }
    
    def get_available_services(self):
        """返回所有可用的AI服务名称"""
        return list(self.ai_services.keys())
    
    def get_service(self, name):
        """获取指定的AI服务实例"""
        return self.ai_services.get(name) 