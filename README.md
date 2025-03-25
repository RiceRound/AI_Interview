# Interview Assistant System

[中文文档](README_CN.md)

![image](demo.jpg)

## Overview
The Interview Assistant System is an AI-powered tool designed to help with interview scenarios by converting interviewer's audio to text and providing appropriate responses in real-time. The system integrates multiple AI services including Baidu, Tencent, and Kimi AI for optimal performance.

## Quick Start

1. Clone the project
```bash
git clone https://github.com/RiceRound/AI_Interview.git
cd AI_Interview
```

2. Configuration Setup
- Rename `config.yaml.example` to `config.yaml`
- Configure the following AI service parameters as needed:

### Baidu AI Configuration
```yaml
baidu:
  app_key: "your-baidu-app-key"  # API Key from Baidu Qianfan Platform
  app_id: "your-baidu-app-id"    # App ID from Baidu Qianfan Platform
```

### Kimi AI Configuration
```yaml
kimi:
  api_key: "your-kimi-api-key"   # API Key from Moonshot Platform
```

### Tencent Cloud Configuration
```yaml
tencent:
  bot_app_key: "your-tencent-bot-app-key"     # Tencent Cloud Bot App Key
  visitor_biz_id: "your-tencent-visitor-biz-id" # Visitor Business ID
  secret_id: "your-tencent-secret-id"         # Tencent Cloud SecretId
  secret_key: "your-tencent-secret-key"       # Tencent Cloud SecretKey
```

### ChatGPT Configuration
```yaml
chatgpt:
  api_key: "your-openai-api-key"  # API Key from OpenAI Platform
  base_url: "https://api.openai.com/v1"  # API Base URL, can be modified if using a proxy
```

3. Obtaining API Keys
- Baidu Qianfan Platform: Create an application in the management console to get API Key and App ID
- Kimi AI: Get API Key from the Moonshot platform settings
- Tencent Cloud: Obtain SecretId and SecretKey from the access management console, and Bot-related keys from the bot platform
- ChatGPT: Get API Key from the OpenAI platform API settings page

Note:
- Keep your API keys secure and never commit them to the code repository
- For ChatGPT, if using in mainland China, you may need to configure a proxy or modify the base_url

## Project Repository
GitHub: [https://github.com/RiceRound/AI_Interview](https://github.com/RiceRound/AI_Interview)

## AI Service Platforms
- Tencent Cloud AI: [https://lke.cloud.tencent.com/lke#/app/home](https://lke.cloud.tencent.com/lke#/app/home)
- Baidu Qianfan: [https://qianfan.cloud.baidu.com/appbuilder/](https://qianfan.cloud.baidu.com/appbuilder/)
- Kimi AI: [https://platform.moonshot.cn/](https://platform.moonshot.cn/)
- ChatGPT: [https://platform.openai.com/](https://platform.openai.com/)
- Claude: [https://claude.ai/](https://claude.ai/)
- Google AI (Gemini): [https://ai.google.dev/](https://ai.google.dev/)
- Azure OpenAI: [https://azure.microsoft.com/products/ai-services/openai-service](https://azure.microsoft.com/products/ai-services/openai-service)

## Support
For issues and feature requests, please create an issue in our [GitHub repository](https://github.com/RiceRound/AI_Interview/issues).

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Contact
![image](wechat.jpg) 