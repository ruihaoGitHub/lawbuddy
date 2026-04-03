"""
Models 模块包

包含所有数据模型定义：
- simple_models: 基础数据模型（工资场景专用）
- extended_models: 扩展数据模型（多场景支持）
"""

from .simple_models import (
    AgentResponse as SimpleAgentResponse,
    SalaryArrearsInfo,
    LegalAnalysis,
    LLMCollectOutput,
    REQUIRED_FIELDS,
    FIELD_DESCRIPTIONS,
    generate_session_id,
)

from .extended_models import (
    AgentState,
    AgentResponse,
    RouterState,
    ScenarioDetection,
    ScenarioConfig,
    SCENARIO_TYPES,
    SCENARIO_DESCRIPTIONS,
    DEFAULT_SCENARIOS,
    generate_session_id as generate_extended_session_id,
    generate_scenario_session_id,
)

__all__ = [
    # 从simple_models导出的
    "SimpleAgentResponse",
    "SalaryArrearsInfo",
    "LegalAnalysis",
    "LLMCollectOutput",
    "REQUIRED_FIELDS",
    "FIELD_DESCRIPTIONS",
    "generate_session_id",
    
    # 从extended_models导出的
    "AgentState",
    "AgentResponse",
    "RouterState",
    "ScenarioDetection",
    "ScenarioConfig",
    "SCENARIO_TYPES",
    "SCENARIO_DESCRIPTIONS",
    "DEFAULT_SCENARIOS",
    "generate_extended_session_id",
    "generate_scenario_session_id",
]