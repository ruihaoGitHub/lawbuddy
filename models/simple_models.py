"""
数据模型定义

包含 LangGraph State、Pydantic 数据模型、字段常量定义。
"""
from typing import Optional, List, Dict, Any, TypedDict
from pydantic import BaseModel, Field
import uuid


# ============================================================
# 字段常量 — 拖欠工资案件需要收集的信息
# ============================================================

REQUIRED_FIELDS = [
    "employment_duration",  # 工作期限（月）
    "monthly_salary",       # 月薪（元）
    "arrears_months",       # 拖欠月数
    "arrears_amount",       # 拖欠金额（元）
    "employer_name",        # 雇主公司名称
    "work_location",        # 工作地点
]

FIELD_DESCRIPTIONS = {
    "employment_duration": "工作期限（月）",
    "monthly_salary": "月薪（元）",
    "arrears_months": "拖欠月数",
    "arrears_amount": "拖欠金额（元）",
    "employer_name": "雇主公司名称",
    "work_location": "工作地点",
}


# ============================================================
# LangGraph Agent State（TypedDict）
# ============================================================

class AgentState(TypedDict, total=False):
    """
    LangGraph 工作流的状态定义。

    每个节点读取/更新这些字段，MemorySaver 负责持久化。
    """
    # 会话标识
    session_id: str
    scenario: str

    # 用户最新输入
    user_input: str

    # LLM 对话历史（BaseMessage 列表的 dict 表示）
    messages: List[Dict[str, str]]

    # 已收集的案情数据
    collected_fields: Dict[str, Any]

    # LLM 输出（用于条件判断）
    llm_output: Dict[str, Any]
    
    # 工作流状态
    welcome_done: bool
    analysis_complete: bool
    workflow_complete: bool
    
    # 最终分析结果
    analysis_result: Optional[str]
    api_result: Optional[Dict[str, Any]]


# ============================================================
# LLM 输出结构体（用于结构化输出解析）
# ============================================================

class LLMCollectOutput(BaseModel):
    """
    collect_node 中 LLM 的结构化输出。
    LLM 需要从用户输入中提取字段，并决定下一步追问内容。
    """
    # 从用户输入中提取/更新的字段（可为空）
    extracted_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="从用户输入中提取到的案情字段，key 为字段名，value 为值"
    )
    # 还缺少哪些字段
    missing_fields: List[str] = Field(
        default_factory=list,
        description="仍然缺失的字段名列表"
    )
    # 要展示给用户的消息（追问或确认）
    response: str = Field(
        default="",
        description="要展示给用户的回复消息，自然语言，像律师一样"
    )
    # 是否应该继续追问
    should_continue: bool = Field(
        default=True,
        description="是否还需要继续追问更多信息"
    )


# ============================================================
# Pydantic 数据模型（用于 API/CLI 交互）
# ============================================================

class AgentResponse(BaseModel):
    """Agent 响应"""
    session_id: str
    message: str
    current_step: str
    requires_input: bool = True
    completed: bool = False
    collected_fields: List[str] = Field(default_factory=list)
    progress: float = 0.0


class SalaryArrearsInfo(BaseModel):
    """拖欠工资案件信息"""
    employment_duration: int
    monthly_salary: float
    arrears_months: int
    arrears_amount: float
    employer_name: str
    work_location: str = "深圳"
    has_contract: bool = False
    evidence: List[str] = Field(default_factory=list)


class LegalAnalysis(BaseModel):
    """法律分析结果"""
    summary: str
    applicable_laws: List[Dict[str, str]]
    similar_cases: List[Dict[str, str]]
    recommendations: List[str]
    action_steps: List[str]


# ============================================================
# 工具函数
# ============================================================

def generate_session_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"
