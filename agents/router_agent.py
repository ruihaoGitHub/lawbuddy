"""
Router Agent - Supervisor 模式的路由器
采用 LangGraph 标准的 Supervisor 模式实现场景识别和分发
"""
import logging
import json
from typing import Dict, Any, Optional, List, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .base_agent import BaseLegalAgent
from models.extended_models import (
    RouterState,
    ScenarioDetection,
    SCENARIO_TYPES,
    SCENARIO_DESCRIPTIONS,
    DEFAULT_SCENARIOS,
    AgentResponse,
    generate_session_id,
)

logger = logging.getLogger(__name__)


# ============================================================
# Supervisor 系统提示词
# ============================================================

SUPERVISOR_SYSTEM_PROMPT = f"""你是一个法律咨询场景识别专家。你的任务是根据用户的描述，识别他们需要哪种法律咨询服务。

## 可识别的场景类型
{json.dumps(SCENARIO_DESCRIPTIONS, ensure_ascii=False, indent=2)}

## 可用的工具（路由决策）
1. **salary_agent**: 当用户需要咨询**拖欠工资**问题时使用
2. **injury_agent**: 当用户需要咨询**工伤赔偿**问题时使用
3. **respond_directly**: 直接回复用户（用于澄清问题或处理简单询问）

## 决策规则
1. 如果用户描述涉及工资拖欠、欠薪、不发工资 → 选择 salary_agent
2. 如果用户描述涉及工伤、工作受伤、工伤赔偿 → 选择 injury_agent  
3. 如果描述不清楚、需要澄清、或者询问一般法律问题 → 使用 respond_directly 直接回复澄清问题
4. 如果用户只是问候或简单交流 → 使用 respond_directly 礼貌回复

## 输出格式
{{
  "decision": "salary_agent|injury_agent|respond_directly",
  "reason": "选择该路由的原因说明",
  "confidence": 0.9,
  "next_action": "下一步要执行的操作说明"
}}
"""

DIRECT_RESPONSE_SYSTEM_PROMPT = """你是一个专业的法律咨询助手，负责澄清问题或回答简单的法律咨询。

当用户的问题不够清晰时，你需要：
1. 礼貌地要求用户提供更多信息
2. 明确说明需要哪些关键信息
3. 给出具体的提问示例

如果用户只是问候，礼貌回应即可。
"""

WELCOME_MESSAGE = """欢迎使用法律咨询助手！

我可以为您提供以下法律咨询服务：
{supported_scenarios}

请您描述您遇到的法律问题，例如：拖欠工资、工伤赔偿、合同纠纷、劳动解雇或加班费追索等问题。

我会先分析您的问题属于哪个场景，然后为您提供专业的咨询服务。
"""


class RouterAgent(BaseLegalAgent):
    """
    路由器Agent：采用 LangGraph Supervisor 模式
    
    标准 Supervisor 模式架构：
    1. supervisor 节点通过 LLM 决策路由
    2. 子 Agent 作为图内节点（salary_agent, injury_agent, respond_directly）
    3. 统一的 RouterState 管理会话状态
    
    工作流程：
    1. 用户进入 → supervisor 展示欢迎信息
    2. 用户描述问题 → supervisor 调用 LLM 决策路由
    3. 根据决策路由到相应子 Agent
    4. 子 Agent 处理完成后结束
    """
    
    def __init__(self, llm_client, available_agents: Dict[str, BaseLegalAgent]):
        super().__init__()
        self.llm = llm_client
        self.available_agents = available_agents  # {场景名: Agent实例}
        self._build_workflow()
    
    def _build_workflow(self):
        workflow = StateGraph(RouterState)
        
        # 添加节点
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("salary_agent", self._salary_agent_node)
        workflow.add_node("injury_agent", self._injury_agent_node)
        workflow.add_node("respond_directly", self._respond_directly_node)
        
        # 入口：welcome → supervisor
        workflow.set_entry_point("supervisor")
        
        # Supervisor 条件边
        workflow.add_conditional_edges(
            "supervisor", self._route_decision,
            {
                "salary_agent": "salary_agent",
                "injury_agent": "injury_agent",
                "respond_directly": "respond_directly",
            }
        )
        
        # 子节点 → END
        workflow.add_edge("salary_agent", END)
        workflow.add_edge("injury_agent", END)
        workflow.add_edge("respond_directly", END)
        
        self.app = workflow.compile(checkpointer=self.checkpointer)

    def start_conversation(self, session_id: Optional[str] = None) -> AgentResponse:
        """启动 Supervisor 对话"""
        if session_id is None:
            session_id = generate_session_id()

        # 构建支持场景列表
        supported_scenarios = "\n".join([
            f"- {description}" for scenario_id, description in SCENARIO_DESCRIPTIONS.items()
            if scenario_id in self.available_agents
        ])

        welcome_msg = WELCOME_MESSAGE.format(supported_scenarios=supported_scenarios)

        # 初始状态
        initial_state: RouterState = {
            "session_id": session_id,
            "user_input": "",
            "messages": [
                {"role": "assistant", "content": welcome_msg}
            ],
            "current_scenario": None,
            "scenario_detection_history": [],
            "sub_agent_session_id": None,
            "requires_scenario_confirmation": False,
            "workflow_complete": False,
            "expecting_user_input": True,
        }

        # ✅ 修复：不手动写入 checkpoint，直接调用 app.invoke
        config = {"configurable": {"thread_id": session_id}}
        result = self.app.invoke(initial_state, config=config)

        return self._to_response(result, session_id)
    

    def _supervisor_node(self, state: RouterState) -> RouterState:
        """Supervisor 节点：LLM 决策路由"""
        logger.info("执行 supervisor_node")
        messages = state.get("messages", [])
        user_input = state.get("user_input", "").strip()

        # 没有用户输入 → 欢迎阶段，转到respond_directly但不结束工作流
        if not user_input:
            state["current_scenario"] = "respond_directly"
            state["expecting_user_input"] = True
            state["workflow_complete"] = False  # 欢迎阶段不结束工作流
            return state

        # 添加用户消息
        messages.append({"role": "user", "content": user_input})

        try:
            # LLM 路由决策
            decision_result = self.llm.chat_completion([
                {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT},
                {"role": "user", "content": f"用户描述：{user_input}"}
            ])

            decision = self._parse_decision_result(decision_result)
            logger.info(f"Supervisor 决策: {decision}")

            # ✅ 核心修复：无论选什么，都标记完成
            state["current_scenario"] = decision["decision"]
            state["workflow_complete"] = True

            if decision["decision"] in ["salary_agent", "injury_agent"]:
                state["sub_agent_session_id"] = f"{decision['decision']}_{generate_session_id()}"

        except Exception as e:
            logger.error(f"Supervisor 决策失败: {e}")
            state["current_scenario"] = "respond_directly"
            state["workflow_complete"] = True  # ✅ 异常也要结束

        # 清空输入
        state["user_input"] = ""
        return state
    
    def _salary_agent_node(self, state: RouterState) -> RouterState:
        """拖欠工资子 Agent 节点"""
        logger.info("执行 salary_agent_node")
        
        # 调用 salary_agent
        if "salary_arrears" in self.available_agents:
            sub_agent = self.available_agents["salary_arrears"]
            sub_agent_session_id = state.get("sub_agent_session_id")
            
            if not sub_agent_session_id:
                sub_agent_session_id = f"salary_arrears_{generate_session_id()}"
                state["sub_agent_session_id"] = sub_agent_session_id
            
            # 获取用户最后一条消息
            messages = state.get("messages", [])
            user_input = ""
            for msg in reversed(messages):
                if msg["role"] == "user":
                    user_input = msg["content"]
                    break
            
            # 启动或继续子 Agent 对话
            try:
                # 直接调用 process_message，它会自动处理会话不存在的情况
                response = sub_agent.process_message(sub_agent_session_id, user_input)
                
                # 添加子 Agent 的响应到消息历史
                messages.append({"role": "assistant", "content": response.message})
                state["messages"] = messages
                
                # 重要：工作流不要完成，让后续消息直接路由到子Agent
                state["workflow_complete"] = False
                # 标记期望用户输入
                state["expecting_user_input"] = response.requires_input if hasattr(response, 'requires_input') else True
                
            except Exception as e:
                logger.error(f"Salary Agent 处理失败: {e}")
                error_msg = f"处理拖欠工资咨询时出现错误：{str(e)}"
                messages.append({"role": "assistant", "content": error_msg})
                state["messages"] = messages
        
        else:
            logger.error("Salary Agent 不可用")
            messages = state.get("messages", [])
            messages.append({"role": "assistant", "content": "抱歉，拖欠工资咨询服务暂时不可用。"})
            state["messages"] = messages
        
        return state
    
    def _injury_agent_node(self, state: RouterState) -> RouterState:
        """工伤赔偿子 Agent 节点"""
        logger.info("执行 injury_agent_node")
        
        # 调用 injury_agent
        if "injury_compensation" in self.available_agents:
            sub_agent = self.available_agents["injury_compensation"]
            sub_agent_session_id = state.get("sub_agent_session_id")
            
            if not sub_agent_session_id:
                sub_agent_session_id = f"injury_compensation_{generate_session_id()}"
                state["sub_agent_session_id"] = sub_agent_session_id
            
            # 获取用户最后一条消息
            messages = state.get("messages", [])
            user_input = ""
            for msg in reversed(messages):
                if msg["role"] == "user":
                    user_input = msg["content"]
                    break
            
            # 启动或继续子 Agent 对话
            try:
                # 首先尝试获取子Agent的当前状态，检查会话是否存在
                try:
                    # 尝试获取会话状态
                    sub_state = sub_agent._get_current_state(sub_agent_session_id)
                    if not sub_state:
                        # 会话不存在，先创建
                        start_response = sub_agent.start_conversation(sub_agent_session_id)
                        if user_input:
                            response = sub_agent.process_message(sub_agent_session_id, user_input)
                        else:
                            response = start_response
                    else:
                        # 会话存在，直接处理消息
                        response = sub_agent.process_message(sub_agent_session_id, user_input)
                except Exception as e:
                    logger.warning(f"检查子Agent会话状态失败: {e}")
                    # 作为后备方案，先创建会话
                    start_response = sub_agent.start_conversation(sub_agent_session_id)
                    if user_input:
                        response = sub_agent.process_message(sub_agent_session_id, user_input)
                    else:
                        response = start_response
                
                # 添加子 Agent 的响应到消息历史
                messages.append({"role": "assistant", "content": response.message})
                state["messages"] = messages
                
                # 重要：工作流不要完成，让后续消息直接路由到子Agent
                state["workflow_complete"] = False
                # 标记期望用户输入
                state["expecting_user_input"] = response.requires_input if hasattr(response, 'requires_input') else True
                
            except Exception as e:
                logger.error(f"Injury Agent 处理失败: {e}")
                error_msg = f"处理工伤赔偿咨询时出现错误：{str(e)}"
                messages.append({"role": "assistant", "content": error_msg})
                state["messages"] = messages
        
        else:
            logger.error("Injury Agent 不可用")
            messages = state.get("messages", [])
            messages.append({"role": "assistant", "content": "抱歉，工伤赔偿咨询服务暂时不可用。"})
            state["messages"] = messages
        
        return state
    
    def _respond_directly_node(self, state: RouterState) -> RouterState:
        """直接回复节点：用于澄清或简单回复"""
        logger.info("执行 respond_directly_node")
        
        messages = state.get("messages", [])
        user_input = ""
        
        # 获取用户最后一条消息
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_input = msg["content"]
                break
        
        # 检查是否是欢迎阶段（没有用户消息，但有助手消息）
        has_user_message = any(msg["role"] == "user" for msg in messages)
        has_assistant_message = any(msg["role"] == "assistant" for msg in messages)
        
        # 如果是欢迎阶段（没有用户消息，但已有助手消息），直接返回
        if not has_user_message and has_assistant_message:
            logger.info("欢迎阶段，不生成额外回复")
            state["expecting_user_input"] = True
            state["workflow_complete"] = True
            return state
        
        try:
            # 调用 LLM 生成澄清或回复
            response = self.llm.chat_completion([
                {"role": "system", "content": DIRECT_RESPONSE_SYSTEM_PROMPT},
                {"role": "user", "content": user_input} if user_input else {"role": "user", "content": "你好"}
            ])
            
            messages.append({"role": "assistant", "content": response})
            state["messages"] = messages
            
            # 标记需要继续用户输入（澄清后需要用户回复）
            state["expecting_user_input"] = True
            state["workflow_complete"] = True
            
        except Exception as e:
            logger.error(f"直接回复生成失败: {e}")
            fallback_msg = "请问您需要咨询什么法律问题？例如：拖欠工资、工伤赔偿等。"
            messages.append({"role": "assistant", "content": fallback_msg})
            state["messages"] = messages
            state["expecting_user_input"] = True
        
        return state
    
    def _parse_decision_result(self, llm_response: str) -> Dict[str, Any]:
        """解析 Supervisor 决策结果"""
        try:
            # 提取 JSON 部分
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                data = json.loads(json_str)
                
                # 验证决策类型
                decision = data.get("decision", "respond_directly")
                if decision not in ["salary_agent", "injury_agent", "respond_directly"]:
                    decision = "respond_directly"
                
                return {
                    "decision": decision,
                    "reason": data.get("reason", ""),
                    "confidence": data.get("confidence", 0.5),
                    "next_action": data.get("next_action", "")
                }
        except Exception as e:
            logger.warning(f"决策结果解析失败: {e}")
        
        # 解析失败时的默认值
        return {
            "decision": "respond_directly",
            "reason": "解析失败，使用默认回复",
            "confidence": 0.5,
            "next_action": "直接回复用户澄清问题"
        }
    
    def _route_decision(self, state: RouterState) -> str:
        """路由决策：返回要转到的节点"""
        # 检查是否已经有决策结果（由 supervisor_node 设置）
        current_scenario = state.get("current_scenario")
        
        # Supervisor 输出的 decision 可能是 "salary_agent" 或 "injury_agent"
        # 这些需要映射到图内的节点名称
        if current_scenario == "salary_agent":
            return "salary_agent"
        elif current_scenario == "injury_agent":
            return "injury_agent"
        elif current_scenario == "respond_directly":
            return "respond_directly"
        else:
            # 默认走 respond_directly（用户未描述问题时的兜底）
            return "respond_directly"
    
    def _to_response(self, state: Dict[str, Any], session_id: str) -> AgentResponse:
        """将 RouterState 转换为 AgentResponse"""
        # 从 messages 中提取最后一条助手消息
        messages = state.get("messages", [])
        last_message = ""
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                last_message = msg["content"]
                break
        
        # 确定当前场景
        current_scenario = state.get("current_scenario")
        scenario_name = SCENARIO_DESCRIPTIONS.get(current_scenario, "") if current_scenario else ""
        
        # 确定工作流状态
        is_complete = state.get("workflow_complete", False)
        expecting_user_input = state.get("expecting_user_input", False)
        requires_input = not is_complete or expecting_user_input
        
        # 确定当前步骤
        if not messages:
            current_step = "欢迎阶段"
        elif not current_scenario or current_scenario == "respond_directly":
            current_step = "场景识别与澄清"
        else:
            current_step = f"{scenario_name}咨询"
        
        # 构建响应
        return AgentResponse(
            session_id=session_id,
            message=last_message or "我是法律咨询助手，请描述您遇到的法律问题。",
            current_step=current_step,
            requires_input=requires_input,
            completed=is_complete and not expecting_user_input,
            collected_fields=[],  # 路由器不收集字段
            progress=0.0,
            scenario=current_scenario
        )
    
    def process_message(self, session_id: str, message: str) -> AgentResponse:
        """处理用户消息 —— 【稳定版：子Agent永远不会重置】"""
        # 1. 获取当前路由状态
        state = self._get_current_state(session_id)
        if not state:
            return self.start_conversation(session_id)

        current_scenario = state.get("current_scenario")
        sub_agent_session_id = state.get("sub_agent_session_id")

        # 2. 【核心】如果已经路由到子Agent → 直接转发，绝不重新初始化
        if current_scenario in ["salary_agent", "injury_agent"] and sub_agent_session_id:
            agent_map = {
                "salary_agent": "salary_arrears",
                "injury_agent": "injury_compensation"
            }
            agent_key = agent_map.get(current_scenario)

            if agent_key in self.available_agents:
                sub_agent = self.available_agents[agent_key]
                # ✅ 只调用 process，永远不 start_conversation
                response = sub_agent.process_message(sub_agent_session_id, message)
                return response

        # 3. 第一次进入：执行路由逻辑
        config = {"configurable": {"thread_id": session_id}}
        result = self.app.invoke({"user_input": message}, config)
        return self._to_response(result, session_id)
    
    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """获取进度"""
        state = self._get_current_state(session_id)
        if not state:
            return {"error": "会话不存在"}
        
        current_scenario = state.get("current_scenario")
        sub_agent_session_id = state.get("sub_agent_session_id")
        
        if current_scenario and sub_agent_session_id:
            # 查询子 Agent 进度
            sub_agent = None
            if current_scenario == "salary_agent" and "salary_arrears" in self.available_agents:
                sub_agent = self.available_agents["salary_arrears"]
            elif current_scenario == "injury_agent" and "injury_compensation" in self.available_agents:
                sub_agent = self.available_agents["injury_compensation"]
            
            if sub_agent:
                try:
                    progress = sub_agent.get_progress(sub_agent_session_id)
                    progress["scenario"] = current_scenario
                    return progress
                except Exception:
                    pass
        
        # 返回路由器自身的进度
        return {
            "session_id": session_id,
            "progress": 0,
            "current_step": "场景识别中",
            "scenario": current_scenario or "未确定",
        }


def create_router_agent(llm_client, agent_registry: Dict[str, BaseLegalAgent]) -> RouterAgent:
    """创建路由器Agent"""
    return RouterAgent(llm_client, agent_registry)