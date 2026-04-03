"""
百炼平台 LLM 客户端

通过 OpenAI SDK（v1.x）接入阿里云百炼平台（OpenAI 兼容模式）。
配置通过 .env 文件管理。
"""
import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-plus"
    temperature: float = 0.3
    max_tokens: int = 1024


class LLMClient:
    """简单的 LLM 客户端，通过 OpenAI SDK 调用百炼平台"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url
            )
        except ImportError:
            raise ImportError(
                "请安装 openai 包: pip install 'openai>=1.13.3,<2.0.0'"
            )
    
    def chat_completion(self, messages: list[Dict[str, str]], **kwargs) -> str:
        """
        发送聊天补全请求
        
        Args:
            messages: 消息列表，格式如 [{"role": "user", "content": "..."}]
            **kwargs: 额外参数，如 temperature, max_tokens
            
        Returns:
            LLM 回复的文本内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.config.temperature),
                max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise RuntimeError(f"LLM 调用失败: {e}")


def create_llm_client(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> LLMClient:
    """
    创建百炼平台 LLM 客户端
    
    优先使用传入参数，否则从环境变量读取：
      - DASHSCOPE_API_KEY  或  OPENAI_API_KEY
      - DASHSCOPE_BASE_URL 或  OPENAI_BASE_URL
      - LLM_MODEL_NAME
    
    Args:
        model: 模型名称，默认 qwen-plus
        api_key: API Key
        base_url: API 基础 URL
        temperature: 生成温度
        max_tokens: 最大生成 token 数
    
    Returns:
        LLMClient 实例
    """
    _model = model or os.getenv("LLM_MODEL_NAME", "qwen-plus")
    _key = api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    _url = base_url or os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    
    if not _key:
        raise ValueError(
            "未配置 API Key。请在 .env 文件中设置 DASHSCOPE_API_KEY 或 OPENAI_API_KEY"
        )
    
    config = LLMConfig(
        api_key=_key,
        base_url=_url,
        model=_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    return LLMClient(config)