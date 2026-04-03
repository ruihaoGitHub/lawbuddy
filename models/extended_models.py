"""
扩展数据模型 - 支持多场景Agent系统
"""
from typing import Optional, List, Dict, Any, TypedDict, Literal
from pydantic import BaseModel, Field
import uuid


# ============================================================
# 场景定义
# ============================================================

SCENARIO_TYPES = Literal[
    "salary_arrears",      # 拖欠工资
    "injury_compensation", # 工伤赔偿
    "contract_dispute",    # 合同纠纷
    "labor_dismissal",     # 劳动解雇
    "overtime_pay",        # 加班费
]

SCENARIO_DESCRIPTIONS = {
    "salary_arrears": "拖欠工资纠纷",
    "injury_compensation": "工伤赔偿纠纷",
    "contract_dispute": "劳动合同纠纷",
    "labor_dismissal": "劳动解雇赔偿",
    "overtime_pay": "加班费追索",
}

# ============================================================
# LangGraph Agent State（统一状态定义）
# ============================================================

class AgentState(TypedDict, total=False):
    """
    统一的多场景Agent状态定义
    """
    # 会话标识
    session_id: str
    scenario: str  # 场景类型：salary_arrears, injury_compensation等
    
    # 用户最新输入
    user_input: str
    
    # LLM 对话历史
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
    api_query: Optional[Dict[str, Any]]
    
    # 场景专用字段
    scenario_data: Optional[Dict[str, Any]]  # 场景特定数据


# ============================================================
# 场景路由相关模型
# ============================================================

class ScenarioDetection(BaseModel):
    """场景检测结果"""
    detected_scenario: SCENARIO_TYPES
    confidence: float = Field(ge=0.0, le=1.0, description="检测置信度")
    explanation: str = Field(default="", description="检测理由")
    requires_clarification: bool = Field(default=False, description="是否需要澄清")
    clarification_question: Optional[str] = Field(default=None, description="澄清问题")


class RouterState(TypedDict, total=False):
    """
    路由器Agent的状态定义
    """
    session_id: str
    user_input: str
    messages: List[Dict[str, str]]
    current_scenario: Optional[SCENARIO_TYPES]  # 当前场景
    scenario_detection_history: List[ScenarioDetection]  # 场景检测历史
    sub_agent_session_id: Optional[str]  # 子Agent的session_id
    requires_scenario_confirmation: bool  # 是否需要确认场景


# ============================================================
# Pydantic 数据模型（用于API/CLI交互）
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
    scenario: Optional[str] = None  # 新增：当前场景


# ============================================================
# 场景配置
# ============================================================

class ScenarioConfig(BaseModel):
    """场景配置"""
    scenario_id: SCENARIO_TYPES
    display_name: str
    description: str
    required_fields: List[str]
    field_descriptions: Dict[str, str]
    api_service_name: Optional[str] = None  # 对应的API服务名称


# ============================================================
# 工具函数
# ============================================================

def generate_session_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"


def generate_scenario_session_id(scenario: str) -> str:
    """生成带场景标识的session_id"""
    return f"{scenario}_{uuid.uuid4().hex[:8]}"


# ============================================================
# 默认场景配置
# ============================================================

DEFAULT_SCENARIOS = {
    "salary_arrears": ScenarioConfig(
        scenario_id="salary_arrears",
        display_name="拖欠工资纠纷",
        description="处理工资拖欠、迟发、少发等问题",
        required_fields=[
            "employment_duration",
            "monthly_salary",
            "arrears_months",
            "arrears_amount",
            "employer_name",
            "work_location",
        ],
        field_descriptions={
            "employment_duration": "工作期限（月）",
            "monthly_salary": "月薪（元）",
            "arrears_months": "拖欠月数",
            "arrears_amount": "拖欠金额（元）",
            "employer_name": "雇主公司名称",
            "work_location": "工作地点",
        },
        api_service_name="deli_api_service",
    ),
    "injury_compensation": ScenarioConfig(
        scenario_id="injury_compensation",
        display_name="工伤赔偿纠纷",
        description="处理工伤认定、医疗费、伤残补助等工伤赔偿问题",
        required_fields=[
            "injury_date",
            "injury_type",
            "hospitalization_days",
            "medical_expenses",
            "work_ability_loss",
            "employer_name",
        ],
        field_descriptions={
            "injury_date": "受伤日期",
            "injury_type": "伤害类型（如骨折、烧伤等）",
            "hospitalization_days": "住院天数",
            "medical_expenses": "医疗费用（元）",
            "work_ability_loss": "劳动能力损失比例（%）",
            "employer_name": "雇主公司名称",
        },
        api_service_name="deli_api_service",
    ),
}