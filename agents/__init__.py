"""
Agents 模块包

包含所有法律场景的Agent类：
- BaseLegalAgent: 基础Agent类
- RouterAgent: 路由器Agent
- SalaryArrearsAgent: 拖欠工资Agent
- InjuryCompensationAgent: 工伤赔偿Agent
- TemplateScenarioAgent: 场景Agent模板
- LLMClient: LLM客户端
"""

from .base_agent import BaseLegalAgent
from .router_agent import RouterAgent, create_router_agent
from .salary_agent import SalaryArrearsAgent
from .injury_compensation_agent import InjuryCompensationAgent
from .template_scenario_agent import TemplateScenarioAgent
from .llm_client import LLMClient, create_llm_client

__all__ = [
    "BaseLegalAgent",
    "RouterAgent",
    "create_router_agent",
    "SalaryArrearsAgent",
    "InjuryCompensationAgent",
    "TemplateScenarioAgent",
    "LLMClient",
    "create_llm_client",
]