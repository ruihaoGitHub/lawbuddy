"""
场景Agent模板 - 用于创建新的法律咨询场景
"""
import json
import logging
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END

from .base_agent import BaseLegalAgent
from models.extended_models import (
    AgentState,
    AgentResponse,
    SCENARIO_TYPES,
)
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


# ============================================================
# 系统提示词模板（根据场景自定义）
# ============================================================

WELCOME_SYSTEM_PROMPT_TEMPLATE = """你是一位专业的{scenario_name}咨询律师。

请用简短、亲切的方式自我介绍，并引导用户描述他们的情况。
不要一次性列出所有问题，先让用户用自己的话描述遇到了什么问题。"""

COLLECT_SYSTEM_PROMPT_TEMPLATE = """你是一位专业的{scenario_name}咨询律师，正在帮助一位用户收集案件信息。

## 你的任务
1. 理解用户的输入，从中提取案件相关信息
2. 判断还缺少哪些必要信息
3. 用自然、专业的语言追问缺失的信息（不要机械式逐字段提问）
4. 如果用户提供了模糊信息，引导其补充具体细节

## 需要收集的字段
{field_descriptions_json}

## 输出格式
你只能输出一个有效的 JSON 对象，格式如下：
{{
  "extracted_fields": {{}},
  "missing_fields": [],
  "response": "你的回复文本（中文）",
  "should_continue": true|false
}}

说明：
- extracted_fields: 从用户输入中提取到的字段（键值对）
- missing_fields: 仍然缺少的字段列表（从 {required_fields_list} 中选择）
- response: 你给用户的回复文本（用自然语言追问或确认）
- should_continue: 是否还需要继续追问更多信息（true=继续追问，false=已收集足够信息）
"""


class TemplateScenarioAgent(BaseLegalAgent):
    """
    场景Agent模板类
    
    使用方式：
    1. 继承此类，重写类变量
    2. 实现 _analyze_node() 方法
    3. 可选：重写其他节点方法
    """
    
    # ====================== 子类必须设置的类变量 ======================
    SCENARIO_ID: SCENARIO_TYPES = "template_scenario"  # 场景标识
    SCENARIO_NAME: str = "模板场景"  # 场景显示名称
    
    # 需要收集的字段
    REQUIRED_FIELDS: List[str] = ["field1", "field2"]
    FIELD_DESCRIPTIONS: Dict[str, str] = {
        "field1": "字段1描述",
        "field2": "字段2描述",
    }
    
    # API服务配置
    API_SERVICE = None  # 可选的API服务
    
    # ============================================================
    
    def __init__(self, llm: LLMClient, use_mock_api: bool = True):
        super().__init__()
        self.llm = llm
        
        # 初始化API服务
        if self.API_SERVICE:
            self.api_service = self.API_SERVICE(use_mock=use_mock_api)
        else:
            self.api_service = None
        
        # 生成系统提示词
        self.welcome_system_prompt = WELCOME_SYSTEM_PROMPT_TEMPLATE.format(
            scenario_name=self.SCENARIO_NAME
        )
        
        self.collect_system_prompt = COLLECT_SYSTEM_PROMPT_TEMPLATE.format(
            scenario_name=self.SCENARIO_NAME,
            field_descriptions_json=json.dumps(self.FIELD_DESCRIPTIONS, ensure_ascii=False, indent=2),
            required_fields_list=self.REQUIRED_FIELDS
        )
        
        self._build_workflow()
    
    def _build_workflow(self):
        """构建工作流 - 标准模板，通常不需要修改"""
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("welcome", self._welcome_node)
        workflow.add_node("collect", self._collect_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("done", self._done_node)
        
        # 定义流程
        workflow.set_entry_point("welcome")
        workflow.add_edge("welcome", "collect")
        
        # collect节点后根据info_complete状态决定下一步
        workflow.add_conditional_edges(
            "collect",
            self._route_after_collect,
            {
                "continue": END,       # 继续收集，等待用户输入
                "analyze": "analyze",  # 进入分析阶段
            }
        )
        
        workflow.add_edge("analyze", "done")
        workflow.add_edge("done", END)
        
        # 编译
        self.app = workflow.compile(checkpointer=self.checkpointer)
    
    # ====================== 标准节点方法 ======================
    
    def _welcome_node(self, state: AgentState) -> AgentState:
        """欢迎节点：生成欢迎语"""
        logger.info(f"执行 {self.SCENARIO_NAME} welcome_node")
        
        messages = state.get("messages", [])
        
        # 调用 LLM 生成欢迎语
        try:
            response_text = self.llm.chat_completion([
                {"role": "system", "content": self.welcome_system_prompt},
                {"role": "user", "content": "你好"}
            ])
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            response_text = f"你好！我是{self.SCENARIO_NAME}咨询助手，可以帮助您处理相关问题。请告诉我您遇到了什么情况？"
        
        # 更新状态
        state["scenario"] = self.SCENARIO_ID
        state["welcome_done"] = True
        state["messages"] = messages + [
            {"role": "assistant", "content": response_text}
        ]
        
        return state
    
    def _collect_node(self, state: AgentState) -> AgentState:
        """收集节点：处理用户输入，提取信息 - 标准实现"""
        logger.info(f"执行 {self.SCENARIO_NAME} collect_node")
        
        messages = state.get("messages", [])
        user_input = state.get("user_input", "")
        
        # 检查是否已经收集了足够信息
        collected_fields = state.get("collected_fields", {})
        required_count = len(self.REQUIRED_FIELDS)
        collected_count = sum(1 for field in self.REQUIRED_FIELDS if field in collected_fields)
        
        # 如果已经收集了足够信息（80%），设置状态进入分析
        if collected_count >= required_count * 0.8:
            logger.info(f"信息收集完成 ({collected_count}/{required_count})，标记为可进入分析")
            state["info_complete"] = True
            return state
        
        # 检查是否有用户输入需要处理
        if user_input:
            logger.info(f"处理用户输入: {user_input[:50]}...")
            
            # 将用户消息添加到历史中
            messages.append({"role": "user", "content": user_input})
            last_user_message = user_input
            
            # 构建对话历史（只取最近6条消息）
            conversation_history = []
            for msg in messages[-6:]:
                conversation_history.append({"role": msg["role"], "content": msg["content"]})
            
            # 调用 LLM 进行结构化处理
            try:
                system_content = self.collect_system_prompt
                user_content = f"用户最新消息：{last_user_message}\n\n请根据对话历史分析："
                
                if len(conversation_history) > 1:
                    user_content += "\n对话历史：\n"
                    for i, msg in enumerate(conversation_history[:-1]):
                        user_content += f"{i+1}. {msg['role']}: {msg['content']}\n"
                
                llm_response = self.llm.chat_completion([
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ])
                
                # 解析 JSON 响应
                result = self._parse_json_response(llm_response)
                
            except Exception as e:
                logger.error(f"收集节点处理失败: {e}")
                # 降级处理
                result = self._create_fallback_output()
            
            # 更新收集的字段
            collected_fields.update(result.extracted_fields or {})
            state["collected_fields"] = collected_fields
            
            # 更新消息
            response_text = result.response
            state["messages"] = messages + [
                {"role": "assistant", "content": response_text}
            ]
            
            # 保存 LLM 输出
            state["llm_output"] = {
                "extracted_fields": result.extracted_fields,
                "missing_fields": result.missing_fields,
                "response": result.response,
                "should_continue": result.should_continue
            }
            
            # 检查是否需要继续
            if not result.should_continue:
                new_collected_count = sum(1 for field in self.REQUIRED_FIELDS if field in collected_fields)
                if new_collected_count >= required_count * 0.8:
                    state["info_complete"] = True
                    logger.info(f"LLM认为信息足够，确实足够 ({new_collected_count}/{required_count})")
                else:
                    logger.info(f"LLM认为信息足够，但实际不足 ({new_collected_count}/{required_count})，继续追问")
        
        else:
            # 没有用户输入：检查是否是从welcome节点过来
            has_assistant_message = any(msg["role"] == "assistant" for msg in messages)
            if not has_assistant_message:
                # 如果是第一次，且没有任何assistant消息，才需要输出默认提示
                logger.info("没有用户输入，且无历史对话，询问第一个问题")
                response_text = f"请描述一下您的{self.SCENARIO_NAME}相关情况。"
                state["messages"] = messages + [
                    {"role": "assistant", "content": response_text}
                ]
                
                # 设置一个默认的LLM输出
                state["llm_output"] = {
                    "extracted_fields": {},
                    "missing_fields": self.REQUIRED_FIELDS[:],
                    "response": response_text,
                    "should_continue": True
                }
            else:
                # 已经有过对话，只是用户没输入，不重复输出
                logger.info("没有用户输入，但已有对话历史，等待用户输入")
                state["llm_output"] = {
                    "should_continue": True
                }
        
        return state
    
    def _parse_json_response(self, llm_response: str) -> Dict[str, Any]:
        """解析 LLM 的 JSON 响应 - 标准实现"""
        try:
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                data = json.loads(json_str)
                
                return {
                    "extracted_fields": data.get("extracted_fields", {}),
                    "missing_fields": data.get("missing_fields", []),
                    "response": data.get("response", ""),
                    "should_continue": data.get("should_continue", True)
                }
        except Exception as e:
            logger.warning(f"JSON 解析失败: {e}")
        
        # 如果解析失败，创建默认输出
        return self._create_fallback_output()
    
    def _create_fallback_output(self) -> Dict[str, Any]:
        """创建降级输出 - 标准实现"""
        return {
            "extracted_fields": {},
            "missing_fields": self.REQUIRED_FIELDS[:],
            "response": f"请描述一下您的{self.SCENARIO_NAME}相关情况。",
            "should_continue": True
        }
    
    def _route_after_collect(self, state: AgentState) -> str:
        """collect节点后的路由判断 - 标准实现"""
        if state.get("info_complete", False):
            logger.info("信息收集完成，进入分析阶段")
            return "analyze"
        else:
            logger.info("需要更多信息，等待用户输入")
            return "continue"
    
    # ====================== 子类必须实现的方法 ======================
    
    def _analyze_node(self, state: AgentState) -> AgentState:
        """
        分析节点：必须由子类实现
        
        子类需要：
        1. 调用API服务（如果有）
        2. 生成分析报告
        3. 更新state中的analysis_result
        """
        raise NotImplementedError("子类必须实现 _analyze_node 方法")
    
    def _done_node(self, state: AgentState) -> AgentState:
        """
        完成节点：可选的，子类可以重写
        
        默认实现：格式化输出分析结果
        """
        logger.info(f"执行 {self.SCENARIO_NAME} done_node")
        
        analysis_report = state.get("analysis_result", "")
        
        # 创建最终回复
        final_response = f"""## {self.SCENARIO_NAME}分析报告

{analysis_report}

---
*本分析仅供参考，具体操作请咨询专业律师。*
"""
        
        # 更新消息
        messages = state.get("messages", [])
        state["messages"] = messages + [
            {"role": "assistant", "content": final_response}
        ]
        state["workflow_complete"] = True
        
        return state
    
    # ====================== 进度查询 ======================
    
    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """获取当前会话的收集进度"""
        state = self._get_current_state(session_id)
        if not state:
            return {
                "progress": 0,
                "collected_fields": [],
                "current_step": "未开始",
                "scenario": self.SCENARIO_ID
            }
        
        collected_fields = state.get("collected_fields", {})
        required_fields = set(self.REQUIRED_FIELDS)
        collected_fields_set = set(collected_fields.keys())
        
        collected_count = len(collected_fields_set & required_fields)
        total_count = len(required_fields)
        progress = int((collected_count / total_count) * 100) if total_count > 0 else 0
        
        # 判断当前步骤
        if state.get("workflow_complete"):
            current_step = "已完成"
        elif state.get("analysis_complete"):
            current_step = "分析中"
        else:
            current_step = "信息收集中"
        
        return {
            "progress": progress,
            "collected_fields": list(collected_fields_set & required_fields),
            "current_step": current_step,
            "scenario": self.SCENARIO_ID
        }