"""
基础 Agent 类

提供 LangGraph 工作流的生命周期管理：
- start_conversation(): 初始化会话，执行 welcome 节点
- process_message(): 接收用户输入，推进工作流
- get_progress(): 查看当前进度

子类只需实现 _build_workflow() 来定义具体的节点和边。
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)

from models.simple_models import (
    AgentResponse,
    REQUIRED_FIELDS,
    generate_session_id,
)
from models.extended_models import AgentState


class BaseLegalAgent(ABC):
    """基础法律 Agent 抽象类"""

    def __init__(self):
        self.checkpointer = MemorySaver()
        self.app = None  # 由子类设置

    # ----------------------------------------------------------
    # 子类必须实现
    # ----------------------------------------------------------

    @abstractmethod
    def _build_workflow(self) -> CompiledStateGraph:
        """
        构建 LangGraph 工作流并编译。

        子类在此方法中：
        1. 创建 StateGraph(AgentState)
        2. 添加节点（add_node）
        3. 添加边（add_edge / add_conditional_edges）
        4. 设置入口点（set_entry_point）
        5. 编译并返回（compile(checkpointer=self.checkpointer)）
        """
        ...

    # ----------------------------------------------------------
    # 公共接口（CLI 调用）
    # ----------------------------------------------------------

    def start_conversation(self, user_id: Optional[str] = None) -> AgentResponse:
        """
        开始新对话。

        创建初始状态并调用 workflow 的第一步（welcome 节点）。
        """
        session_id = user_id if user_id else generate_session_id()

        initial_state: AgentState = {
            "session_id": session_id,
            "scenario": "salary_arrears",
            "user_input": "",
            "messages": [],
            "collected_fields": {},
        }

        config = {"configurable": {"thread_id": session_id}, "recursion_limit": 25}
        result = self.app.invoke(initial_state, config)
        return self._to_response(result, session_id)

    def process_message(self, session_id: str, message: str) -> AgentResponse:
        """
        处理用户消息，推进工作流。

        通过 MemorySaver + thread_id 恢复上次状态，
        将用户输入注入 state 后调用 workflow 的下一个节点。
        """
        config = {"configurable": {"thread_id": session_id}}

        # 获取当前状态
        current_state = self._get_current_state(session_id)
        if not current_state:
            logger.warning(f"会话 {session_id} 不存在，创建新会话")
            return self.start_conversation(user_id=session_id)
        
        logger.info(f"process_message: 恢复状态 from checkpoint - 当前节点: {current_state.get('__langgraph_node__', 'unknown')}")
        
        # 从当前状态获取消息历史
        messages = current_state.get("messages", [])
        
        # 构造更新：只设置用户输入，让collect节点处理消息添加
        update: AgentState = {
            "user_input": message,  # 设置当前用户输入
            "llm_output": None,  # 清除之前的LLM输出
        }

        logger.info(f"process_message: 调用 app.invoke with update")
        result = self.app.invoke(update, {**config, "recursion_limit": 25})
        
        # 检查结果中是否有下一个节点的信息
        next_node = result.get("__langgraph_node__", "unknown")
        logger.info(f"process_message: invoke 完成，下一个节点: {next_node}")
        
        return self._to_response(result, session_id)

    def _get_current_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取当前会话状态（从 checkpoint 读取）"""
        config = {"configurable": {"thread_id": session_id}}
        checkpoint = self.checkpointer.get(config)

        if not checkpoint:
            return None

        return checkpoint.get("channel_values", {})

    def get_progress(self, session_id: str) -> Dict[str, Any]:
        """获取当前会话进度（从 checkpoint 读取）"""
        state = self._get_current_state(session_id)
        
        if not state:
            return {"error": "会话不存在"}

        collected = state.get("collected_data", {})
        if not collected:
            collected = state.get("collected_fields", {})
            
        completed = state.get("info_complete", False)

        collected_count = sum(1 for f in REQUIRED_FIELDS if f in collected)
        total = len(REQUIRED_FIELDS)
        progress = (collected_count / total) * 100 if total else 0

        return {
            "session_id": session_id,
            "progress": progress,
            "current_step": state.get("current_step", "unknown"),
            "info_complete": completed,
            "collected_fields": list(collected.keys()),
        }

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _to_response(self, state: Dict[str, Any], session_id: str) -> AgentResponse:
        """将 LangGraph state 转换为 AgentResponse"""
        collected = state.get("collected_data", {})
        if not collected:
            collected = state.get("collected_fields", {})
            
        collected_count = sum(1 for f in REQUIRED_FIELDS if f in collected)
        total = len(REQUIRED_FIELDS)
        progress = (collected_count / total) * 100 if total else 0

        is_complete = bool(state.get("info_complete", False)) or state.get("analysis_result") is not None or bool(state.get("workflow_complete", False))

        # 从 messages 中提取最后一条助手消息
        messages = state.get("messages", [])
        last_message = ""
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                last_message = msg["content"]
                break

        return AgentResponse(
            session_id=session_id,
            message=last_message or state.get("message", ""),
            current_step=state.get("current_step", "unknown"),
            requires_input=state.get("requires_input", True) and not is_complete,
            completed=is_complete,
            collected_fields=list(collected.keys()),
            progress=progress,
        )
    
    async def close(self):
        """清理资源"""
        if hasattr(self, 'api_service'):
            # 检查api_service是否有close方法
            if hasattr(self.api_service, 'close'):
                import asyncio
                if asyncio.iscoroutinefunction(self.api_service.close):
                    await self.api_service.close()
                else:
                    self.api_service.close()
                logger.info("API服务已关闭")
        logger.info("Agent 已关闭")
