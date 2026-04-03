"""
Services 模块包

包含外部服务集成：
- DeliAPIClient: 得理法律API客户端
"""

from .deli import DeliAPIClient

__all__ = [
    "DeliAPIClient",
]