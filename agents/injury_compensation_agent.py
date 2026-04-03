"""
工伤赔偿Agent - 示例：如何基于模板创建新场景
"""
import json
import logging
import asyncio
from typing import Dict, Any

from .template_scenario_agent import TemplateScenarioAgent
from models.extended_models import SCENARIO_TYPES, AgentState
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class InjuryCompensationAgent(TemplateScenarioAgent):
    """
    工伤赔偿Agent
    
    基于模板创建的具体场景Agent
    """
    
    # ====================== 场景配置 ======================
    SCENARIO_ID: SCENARIO_TYPES = "injury_compensation"
    SCENARIO_NAME: str = "工伤赔偿"
    
    # 需要收集的字段
    REQUIRED_FIELDS = [
        "injury_date",          # 受伤日期
        "injury_type",          # 伤害类型
        "hospitalization_days", # 住院天数
        "medical_expenses",     # 医疗费用
        "work_ability_loss",    # 劳动能力损失比例
        "employer_name",        # 雇主名称
        "work_location",        # 工作地点
        "has_insurance",        # 是否有工伤保险
    ]
    
    FIELD_DESCRIPTIONS = {
        "injury_date": "受伤日期（格式：YYYY-MM-DD）",
        "injury_type": "伤害类型（如：骨折、烧伤、扭伤、职业病等）",
        "hospitalization_days": "住院天数",
        "medical_expenses": "已产生的医疗费用（元）",
        "work_ability_loss": "劳动能力损失比例（0-100%）",
        "employer_name": "雇主公司名称",
        "work_location": "工作地点（城市）",
        "has_insurance": "是否有工伤保险（是/否）",
    }
    
    # API服务配置（可选）
    API_SERVICE = None  # 可以配置得理API或其他工伤赔偿API
    
    def __init__(self, llm: LLMClient, use_mock_api: bool = True):
        super().__init__(llm, use_mock_api)
    
    def _analyze_node(self, state: AgentState) -> AgentState:
        """分析节点：工伤赔偿案件分析"""
        logger.info("执行工伤赔偿 analyze_node")
        
        collected_fields = state.get("collected_fields", {})
        
        # 构建分析提示词
        analyze_prompt = self._build_analysis_prompt(collected_fields)
        
        # 调用 LLM 生成分析报告
        try:
            analysis_report = self.llm.chat_completion([
                {"role": "system", "content": "你是一位专业的工伤赔偿法律顾问。"},
                {"role": "user", "content": analyze_prompt},
            ])
        except Exception as e:
            logger.error(f"分析报告生成失败: {e}")
            analysis_report = self._create_fallback_analysis(collected_fields)
        
        # 如果有API服务，可以调用
        if self.api_service and hasattr(self.api_service, 'analyze_injury_case'):
            try:
                api_result = self._call_injury_api(collected_fields)
                state["api_result"] = api_result
            except Exception as e:
                logger.error(f"工伤API调用失败: {e}")
        
        # 更新状态
        state["analysis_complete"] = True
        state["analysis_result"] = analysis_report
        
        return state
    
    def _build_analysis_prompt(self, collected_fields: Dict[str, Any]) -> str:
        """构建分析提示词"""
        injury_date = collected_fields.get("injury_date", "未知日期")
        injury_type = collected_fields.get("injury_type", "未知伤害类型")
        hospitalization = collected_fields.get("hospitalization_days", 0)
        medical_expenses = collected_fields.get("medical_expenses", 0)
        work_loss = collected_fields.get("work_ability_loss", 0)
        has_insurance = collected_fields.get("has_insurance", "未知")
        
        prompt = f"""你是一位工伤赔偿法律专家，需要基于以下信息为一位工伤受害者提供专业分析：

## 案件信息
受伤日期：{injury_date}
伤害类型：{injury_type}
住院天数：{hospitalization}天
医疗费用：{medical_expenses}元
劳动能力损失：{work_loss}%
工伤保险：{has_insurance}

## 你的任务
请生成完整的工伤赔偿分析报告，包括：
1. **案件摘要**：简要概述案件基本情况
2. **法律适用**：适用的法律法规（《工伤保险条例》等）
3. **赔偿项目**：可以主张的赔偿项目清单
4. **赔偿计算**：各项赔偿的估算金额
5. **维权建议**：具体的维权步骤和建议
6. **风险提示**：可能面临的风险和应对策略

请用专业但易懂的语言，给出具体可行的建议。"""
        
        return prompt
    
    def _create_fallback_analysis(self, collected_fields: Dict[str, Any]) -> str:
        """创建降级分析报告"""
        injury_type = collected_fields.get("injury_type", "工伤")
        medical_expenses = collected_fields.get("medical_expenses", 0)
        
        return f"""# 工伤赔偿分析报告

## 案件摘要
基于您提供的信息，这是一起{injury_type}工伤案件，涉及医疗费用{medical_expenses}元。

## 法律适用
主要适用《工伤保险条例》等相关法律法规。

## 赔偿项目
根据《工伤保险条例》，工伤赔偿通常包括：
1. 医疗费用：实际发生的医疗费、康复费等
2. 住院伙食补助费
3. 交通食宿费
4. 停工留薪期工资
5. 护理费
6. 一次性伤残补助金
7. 伤残津贴
8. 一次性工伤医疗补助金和伤残就业补助金

## 维权建议
1. **收集证据**：医院诊断证明、医疗费票据、工资单、劳动合同等
2. **工伤认定**：向当地人社局申请工伤认定（30日内）
3. **劳动能力鉴定**：伤情稳定后申请劳动能力鉴定
4. **协商赔偿**：与用人单位协商赔偿事宜
5. **法律途径**：协商不成可申请劳动仲裁或提起诉讼

## 风险提示
- 注意工伤认定申请时效（30日内）
- 保留所有医疗费用票据原件
- 及时申请劳动能力鉴定
- 咨询专业律师获取具体指导

以上分析仅供参考，具体赔偿金额需根据劳动能力鉴定结果和当地标准计算。"""
    
    def _call_injury_api(self, collected_fields: Dict[str, Any]) -> Dict[str, Any]:
        """调用工伤API服务（示例）"""
        # 这里可以根据实际API服务实现
        # 示例：模拟API调用
        
        import inspect
        if inspect.iscoroutinefunction(self.api_service.analyze_injury_case):
            # 异步调用
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                api_result = loop.run_until_complete(
                    self.api_service.analyze_injury_case(collected_fields)
                )
                return api_result
            finally:
                loop.close()
        else:
            # 同步调用
            return self.api_service.analyze_injury_case(collected_fields)


# ============================================================
# 使用示例
# ============================================================
def create_injury_compensation_agent(llm: LLMClient, use_mock_api: bool = True) -> InjuryCompensationAgent:
    """创建工伤赔偿Agent的工厂函数"""
    return InjuryCompensationAgent(llm, use_mock_api)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    try:
        from agents.llm_client import create_llm_client
        llm = create_llm_client()
        agent = InjuryCompensationAgent(llm=llm, use_mock_api=True)
        
        # 测试启动对话
        response = agent.start_conversation()
        print(f"Agent启动成功: {response.message}")
        print(f"场景: {agent.SCENARIO_NAME}")
        
    except Exception as e:
        print(f"测试失败: {e}")