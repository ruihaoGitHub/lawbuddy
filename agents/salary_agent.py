"""
拖欠工资案件 Agent

使用 LangGraph 构建 4 节点工作流：
  welcome → collect ⇄ collect → analyze → END

- welcome:  LLM 生成欢迎语
- collect:  LLM 分析用户输入、提取字段、生成追问
- analyze:  调用得理 API + LLM 生成法律分析报告
"""
import json
import logging
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END

from .base_agent import BaseLegalAgent
from models.simple_models import (
    REQUIRED_FIELDS,
    FIELD_DESCRIPTIONS,
    LLMCollectOutput,
)
from models.extended_models import AgentState
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

# 顶部导入
from services.deli import DeliAPIClient

# ============================================================
# System Prompt 模板
# ============================================================

WELCOME_SYSTEM_PROMPT = """你是一位专业的劳动法律咨询律师。你的专长是帮助被拖欠工资的劳动者维权。

请用简短、亲切的方式自我介绍，并引导用户描述他们的情况。
不要一次性列出所有问题，先让用户用自己的话描述遇到了什么问题。"""

COLLECT_SYSTEM_PROMPT = f"""你是一位专业的劳动法律咨询律师，正在帮助一位被拖欠工资的劳动者收集案件信息。

## 你的任务
1. 理解用户的输入，从中提取案件相关信息
2. 判断还缺少哪些必要信息
3. 用自然、专业的语言追问缺失的信息（不要机械式逐字段提问）
4. 如果用户提供了模糊信息，引导其补充具体细节

## 需要收集的字段
{json.dumps(FIELD_DESCRIPTIONS, ensure_ascii=False, indent=2)}

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
- missing_fields: 仍然缺少的字段列表（从 {list(FIELD_DESCRIPTIONS.keys())} 中选择）
- response: 你给用户的回复文本（用自然语言追问或确认）
- should_continue: 是否还需要继续追问更多信息（true=继续追问，false=已收集足够信息）
"""



# =====================
# API 查询构建 Prompt
# =====================
API_QUERY_PROMPT = """
你是一个法律案件查询专家，根据用户提供的拖欠工资信息，自动生成得理API需要的查询条件。

用户信息：
{collected_fields}

请输出**严格JSON**，格式如下：
{{
  "pageNo": 1,
  "pageSize": 3,
  "sortField": "correlation",
  "sortOrder": "desc",
  "condition": {{
    "caseYearStart": "2025-01-01",
    "caseYearEnd": "2025-12-31",
    "courtLevelArr": ["3"],
    "keywordArr": ["拖欠工资案例", "劳动争议"]
  }}
}}

注意：
- keywordArr 必须是法律专业关键词
- 不要输出任何多余文字
"""


class SalaryArrearsAgent(BaseLegalAgent):
    """拖欠工资案件 Agent"""
    
    def __init__(self, llm: LLMClient, use_mock_api: bool = True):
        super().__init__()
        self.llm = llm
        # self.api_service = create_deli_api_service(use_mock=use_mock_api)
        self.deli_client = DeliAPIClient()
        self._build_workflow()
    
    def _build_workflow(self):
        """构建 LangGraph 工作流 - 支持条件路由"""
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("welcome", self._welcome_node)
        workflow.add_node("collect", self._collect_node)
        workflow.add_node("build_api_query", self._build_api_query)  # 新增
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("done", self._done_node)
        
        # 定义流程
        workflow.set_entry_point("welcome")
        workflow.add_edge("welcome", "collect")
        
        # collect节点后根据info_complete状态决定下一步
        workflow.add_conditional_edges(
            "collect",
            self._should_continue_collect,
            {
                "continue": END,              # 继续收集，结束等待用户输入
                "analyze": "build_api_query",  # 进入构建API查询阶段
            }
        )
        workflow.add_edge("build_api_query", "analyze")
        workflow.add_edge("analyze", "done")
        workflow.add_edge("done", END)
        
        # 编译
        self.app = workflow.compile(checkpointer=self.checkpointer)
    
    def _welcome_node(self, state: AgentState) -> AgentState:
        """欢迎节点：生成欢迎语"""
        if state.get("welcome_done", False):
            return state

        logger.info("执行 welcome_node")  # 👈 现在只会打印 1 次！

        # 获取系统消息
        messages = state.get("messages", [])
        
        # 调用 LLM 生成欢迎语
        try:
            response_text = self.llm.chat_completion([
                {"role": "system", "content": WELCOME_SYSTEM_PROMPT},
                {"role": "user", "content": "你好"}
            ])
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            response_text = "你好！我是法律咨询助手，可以帮助您处理拖欠工资的问题。请告诉我您遇到了什么情况？"
        
        # 更新状态
        state["welcome_done"] = True
        state["messages"] = messages + [
            {"role": "assistant", "content": response_text}
        ]
        
        return state
    
    def _collect_node(self, state: AgentState) -> AgentState:
        """收集节点：处理用户输入，提取信息，决定下一步"""
        logger.info("执行 collect_node")
        
        messages = state.get("messages", [])
        user_input = state.get("user_input", "")
        collected_fields = state.get("collected_fields", {})
        required_count = len(REQUIRED_FIELDS)
        
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
                system_content = COLLECT_SYSTEM_PROMPT
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
                result = LLMCollectOutput(
                    extracted_fields={},
                    missing_fields=REQUIRED_FIELDS[:],
                    response="请描述一下您的工资拖欠情况，包括拖欠时间、金额、公司名称等信息。",
                    should_continue=True
                )
            
            # 更新收集的字段
            collected_fields.update(result.extracted_fields or {})
            state["collected_fields"] = collected_fields
            
            # 更新消息
            response_text = result.response
            state["messages"] = messages + [
                {"role": "assistant", "content": response_text}
            ]
            
            # 保存 LLM 输出
            state["llm_output"] = result.model_dump()
            
            # 检查是否需要继续
            if not result.should_continue:
                # 如果LLM认为不需要继续，检查是否真的收集了足够信息
                new_collected_count = sum(1 for field in REQUIRED_FIELDS if field in collected_fields)
                if new_collected_count >= required_count * 0.8:
                    state["info_complete"] = True
                    logger.info(f"LLM认为信息足够，确实足够 ({new_collected_count}/{required_count})")
                else:
                    logger.info(f"LLM认为信息足够，但实际不足 ({new_collected_count}/{required_count})，继续追问")
            
            # 无论LLM怎么说，只要收集了足够信息，就标记为完成
            final_collected_count = sum(1 for field in REQUIRED_FIELDS if field in collected_fields)
            if final_collected_count >= required_count * 0.8:
                state["info_complete"] = True
                logger.info(f"收集了足够信息 ({final_collected_count}/{required_count})，标记为完成")
            else:
                logger.info(f"信息不足 ({final_collected_count}/{required_count})，继续追问")
            
        else:
            # 没有用户输入：检查是否是从welcome节点过来
            has_assistant_message = any(msg["role"] == "assistant" for msg in messages)
            if not has_assistant_message:
                # 如果是第一次，且没有任何assistant消息，才需要输出默认提示
                logger.info("没有用户输入，且无历史对话，询问第一个问题")
                response_text = "请描述一下您的工资拖欠情况，包括拖欠时间、金额、公司名称等信息。"
                state["messages"] = messages + [
                    {"role": "assistant", "content": response_text}
                ]
                
                # 设置一个默认的LLM输出
                state["llm_output"] = {
                    "extracted_fields": {},
                    "missing_fields": REQUIRED_FIELDS[:],
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
    
    def _parse_json_response(self, llm_response: str) -> LLMCollectOutput:
        """解析 LLM 的 JSON 响应"""
        try:
            # 尝试提取 JSON 部分
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                data = json.loads(json_str)
                
                # 确保格式正确
                return LLMCollectOutput(
                    extracted_fields=data.get("extracted_fields", {}),
                    missing_fields=data.get("missing_fields", []),
                    response=data.get("response", ""),
                    should_continue=data.get("should_continue", True)
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"JSON 解析失败: {e}")
        
        # 如果解析失败，创建默认输出
        return LLMCollectOutput(
            extracted_fields={},
            missing_fields=REQUIRED_FIELDS[:],
            response="请提供更多关于拖欠工资的详细信息。",
            should_continue=True
        )
    
    def _should_continue_collect(self, state: AgentState) -> str:
        """判断是否继续收集信息"""
        llm_output = state.get("llm_output")
        messages = state.get("messages", [])
        
        # 检查是否有用户消息
        has_user_message = any(msg["role"] == "user" for msg in messages)
        
        if not has_user_message:
            # 如果没有用户消息，结束工作流等待输入
            logger.info("没有用户消息，结束工作流等待输入")
            return "continue"
        
        # 检查是否收集了足够信息
        collected_fields = state.get("collected_fields", {})
        required_count = len(REQUIRED_FIELDS)
        collected_count = sum(1 for field in REQUIRED_FIELDS if field in collected_fields)
        
        # 如果已收集足够信息（80%），进入分析阶段
        if collected_count >= required_count * 0.8:  # 80% 已收集
            logger.info(f"信息收集完成 ({collected_count}/{required_count})，进入分析阶段")
            return "analyze"
        
        # 如果没有 llm_output 或者 llm_output 不是字典，检查是否有用户消息
        if not llm_output or not isinstance(llm_output, dict):
            # 如果有用户消息但处理失败，继续追问
            if has_user_message:
                logger.info(f"LLM输出无效，但用户已回复 ({collected_count}/{required_count})，继续处理")
                return "continue"
            else:
                logger.info("没有LLM输出且没有用户消息，结束")
                return "continue"
            
        should_continue = llm_output.get("should_continue", True)
        
        # 如果LLM明确表示不需要继续追问
        if not should_continue:
            if collected_count >= required_count * 0.8:
                logger.info(f"LLM认为信息足够 ({collected_count}/{required_count})，进入分析阶段")
                return "analyze"
            else:
                logger.info(f"LLM认为信息足够，但实际不足 ({collected_count}/{required_count})，继续追问")
                return "continue"
        
        # 检查缺失字段是否还很多
        missing_fields = llm_output.get("missing_fields", [])
        if missing_fields and len(missing_fields) <= 2:  # 如果只剩2个或更少字段
            if collected_count >= required_count * 0.6:  # 如果已经收集了60%
                logger.info(f"剩余字段少 ({len(missing_fields)}个)，信息已足够 ({collected_count}/{required_count})")
                return "analyze"
        
        # 默认继续追问
        logger.info(f"继续追问更多信息 ({collected_count}/{required_count})")
        return "continue"
    
    # ------------------------------
    # 【新增】自动构建 API 查询参数
    # ------------------------------
    def _build_api_query(self, state: AgentState) -> AgentState:
        logger.info("执行 build_api_query: 自动生成API查询条件")
        
        collected = state.get("collected_fields", {})
        
        # 改进的API查询构建Prompt - 更智能地利用收集的信息
        prompt = API_QUERY_PROMPT.format(collected_fields=json.dumps(collected, ensure_ascii=False, indent=2))
        
        response = self.llm.chat_completion([
            {"role": "system", "content": "你是一个法律案件查询专家，擅长根据案件信息生成精准的API查询条件。"},
            {"role": "user", "content": prompt}
        ])

        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            query_json = json.loads(response[json_start:json_end])
            state["api_query"] = query_json
            logger.info(f"API查询条件构建完成: {json.dumps(query_json, ensure_ascii=False)}")
        except Exception as e:
            logger.error(f"API参数构建失败: {e}")
            # 降级策略：根据收集到的信息构建查询
            state["api_query"] = self._build_fallback_query(collected)
        
        logger.info(f"最终API查询条件: {json.dumps(state['api_query'], ensure_ascii=False)}")
        return state
    
    def _build_fallback_query(self, collected: Dict[str, Any]) -> Dict[str, Any]:
        """构建降级查询 - 根据收集到的信息智能生成"""
        keyword_arr = ["拖欠工资", "劳动争议"]
        
        # 根据收集到的信息动态添加关键词
        if collected.get("company_name"):
            keyword_arr.append(collected["company_name"])
        if collected.get("industry"):
            keyword_arr.append(collected["industry"])
        if collected.get("position"):
            keyword_arr.append(collected["position"])
        
        # 构建时间范围
        case_year_start = "2025-01-01"
        case_year_end = "2025-12-31"
        
        if collected.get("arrears_start_date"):
            case_year_start = collected["arrears_start_date"]
        if collected.get("arrears_end_date"):
            case_year_end = collected["arrears_end_date"]
        
        return {
            "pageNo": 1,
            "pageSize": 3,
            "sortField": "correlation",
            "sortOrder": "desc",
            "condition": {
                "caseYearStart": case_year_start,
                "caseYearEnd": case_year_end,
                "courtLevelArr": ["3"],
                "keywordArr": keyword_arr
            }
        }


    def _analyze_node(self, state: AgentState) -> AgentState:
        """分析节点：调用得理 API，生成法律分析报告"""
        logger.info("执行 analyze_node")
        
        collected_fields = state.get("collected_fields", {})
        api_query = state.get("api_query", {})

        # -------------------------------------------------------------------------
        # ✅ 正确调用得理API（与你测试代码完全一致）
        # -------------------------------------------------------------------------
        try:
            api_result = self.deli_client.query_list_case(
                page_no=api_query.get("pageNo", 1),
                page_size=api_query.get("pageSize", 3),
                condition=api_query.get("condition", {
                    "caseYearStart": "2025-01-01",
                    "caseYearEnd": "2025-12-31",
                    "courtLevelArr": ["3"],
                    "keywordArr": ["拖欠工资", "劳动争议"]
                })
            )
            logger.info("✅ 得理 API 调用成功")
        except Exception as e:
            logger.error(f"❌ 得理 API 调用失败: {e}")
            api_result = {"error": str(e)}

        # -------------------------------------------------------------------------
        # ✅ 【适配你真实的API返回格式】
        # -------------------------------------------------------------------------
        case_list = []
        if api_result.get("success") is True and api_result.get("body"):
            case_list = api_result["body"].get("data", [])

        # -------------------------------------------------------------------------
        # ✅ 生成正确的法律分析报告
        # -------------------------------------------------------------------------
        analyze_prompt = f"""你是一位专业劳动法律师，请根据用户案件信息与相似法院判例，生成一份完整、易懂、可操作的法律分析报告。

用户案件信息：
{json.dumps(collected_fields, ensure_ascii=False, indent=2)}

相似法院判例：
{json.dumps(case_list, ensure_ascii=False, indent=2)}

请生成报告，包含：
1. 案件事实摘要
2. 法律争议焦点
3. 相似法院判决要点
4. 维权建议
5. 具体操作步骤
"""

        try:
            analysis_report = self.llm.chat_completion([
                {"role": "system", "content": "你是专业劳动法律师，擅长处理拖欠工资纠纷，根据相似案例生成法律分析报告。"},
                {"role": "user", "content": analyze_prompt},
            ])
        except Exception as e:
            logger.error(f"分析报告生成失败: {e}")
            analysis_report = "报告生成失败，请稍后重试。"

        # 存入状态
        state["analysis_complete"] = True
        state["analysis_result"] = analysis_report
        state["api_result"] = api_result
        
        return state


    def _done_node(self, state: AgentState) -> AgentState:
        """完成节点：输出最终法律报告"""
        logger.info("执行 done_node")
        
        # 获取分析结果
        analysis_report = state.get("analysis_result", "未生成报告")
        
        # 拼接最终消息
        final_msg = f"""
    ## ✅ 法律分析报告

    {analysis_report}

    ---
    *本回答仅供参考，具体操作请以专业律师意见为准*
    """
        
        # 添加到对话消息
        state["messages"].append({
            "role": "assistant",
            "content": final_msg
        })
        
        state["workflow_complete"] = True
        return state
    
    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """获取当前会话的收集进度"""
        state = self._get_current_state(session_id)
        if not state:
            return {
                "progress": 0,
                "collected_fields": [],
                "current_step": "未开始"
            }
        
        collected_fields = state.get("collected_fields", {})
        required_fields = set(REQUIRED_FIELDS)
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
            "current_step": current_step
        }
