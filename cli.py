"""
命令行交互入口

启动方式：
  python cli.py
"""
import sys
import logging

from agents.llm_client import create_llm_client
from agents.salary_agent import SalaryArrearsAgent
from agents.injury_compensation_agent import InjuryCompensationAgent
from agents.router_agent import create_router_agent
from models.extended_models import SCENARIO_DESCRIPTIONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 分隔线
SEPARATOR = "-" * 60


def print_banner():
    print()
    print(SEPARATOR)
    print("  法律咨询助手 - 多场景智能咨询")
    print("  支持场景：")
    for scenario_id, description in SCENARIO_DESCRIPTIONS.items():
        print(f"    - {description}")
    print()
    print("  输入 'quit' 或 '退出' 结束对话")
    print("  输入 '进度' 查看当前收集进度")
    print("  输入 '场景' 查看当前咨询的场景")
    print(SEPARATOR)
    print()


def create_scenario_agents(llm_client):
    """创建所有场景Agent"""
    agents = {}
    
    # 拖欠工资Agent
    try:
        salary_agent = SalaryArrearsAgent(llm=llm_client, use_mock_api=True)
        agents["salary_arrears"] = salary_agent
        logger.info("拖欠工资Agent初始化完成")
    except Exception as e:
        logger.error(f"拖欠工资Agent初始化失败: {e}")
    
    # 工伤赔偿Agent
    try:
        injury_agent = InjuryCompensationAgent(llm=llm_client, use_mock_api=True)
        agents["injury_compensation"] = injury_agent
        logger.info("工伤赔偿Agent初始化完成")
    except Exception as e:
        logger.error(f"工伤赔偿Agent初始化失败: {e}")
    
    # 可以继续添加其他场景Agent...
    
    return agents


def main():
    print_banner()

    # 初始化 LLM
    try:
        llm = create_llm_client()
        logger.info("LLM客户端初始化完成")
    except ValueError as e:
        print(f"LLM初始化失败: {e}")
        print("请创建 .env 文件并配置 DASHSCOPE_API_KEY")
        print("示例：")
        print("  DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx")
        print("  LLM_MODEL_NAME=qwen-plus")
        sys.exit(1)
    except Exception as e:
        print(f"LLM初始化失败: {e}")
        sys.exit(1)
    
    # 创建所有场景Agent
    try:
        scenario_agents = create_scenario_agents(llm)
        if not scenario_agents:
            print("错误：未能初始化任何场景Agent")
            sys.exit(1)

        # 创建路由器Agent
        agent = create_router_agent(llm, scenario_agents)
        logger.info(f"路由器Agent初始化完成，加载了 {len(scenario_agents)} 个场景")
        
    except Exception as e:
        print(f"Agent初始化失败: {e}")
        sys.exit(1)


    # 开始对话
    print("正在连接律师助理...\n")
    response = agent.start_conversation()
    # response = agent.start_conversation()
    session_id = response.session_id
    print(f"[律师助理] {response.message}")
    print()

    # RouterAgent 内部流程：
    #   1. supervisor_node: LLM 分析 → 决策 = "salary_agent"
    #   2. _route_decision: current_scenario="salary_agent" → 路由到 salary_agent 节点
    #   3. _salary_agent_node: 调用子 Agent 的 process_message → 返回回复
    # 聊天循环
    while not response.completed:
        try:
            user_input = input("[你] ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n对话已结束。")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "退出", "exit", "q"):
            print("\n再见，祝您维权顺利！")
            break

        if user_input.lower() in ("进度", "progress"):
            progress = agent.get_progress(session_id)
            print(f"\n  当前场景: {progress.get('scenario', '场景检测中')}")
            print(f"  当前进度: {progress.get('progress', 0):.0f}%")
            print(f"  已收集: {', '.join(progress.get('collected_fields', []) or ['暂无'])}")
            print(f"  当前步骤: {progress.get('current_step', '未知')}")
            print()
            continue
        
        if user_input.lower() in ("场景", "scenario", "scenarios"):
            progress = agent.get_progress(session_id)
            current_scenario = progress.get('scenario', '场景检测中')
            scenario_name = SCENARIO_DESCRIPTIONS.get(current_scenario, current_scenario)
            print(f"\n  当前咨询场景: {scenario_name}")
            print(f"  支持的所有场景:")
            for scenario_id, description in SCENARIO_DESCRIPTIONS.items():
                prefix = "→ " if scenario_id == current_scenario else "  "
                print(f"  {prefix}{description}")
            print()
            continue

        # 发送消息给 Agent
        try:
            response = agent.process_message(session_id, user_input)
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            print(f"\n[系统] 处理消息时出错，请重试。\n")
            continue

        print(f"\n[律师助理] {response.message}")
        print()

    # 对话结束
    if response.completed:
        print(SEPARATOR)
        print("  咨询结束。以上分析仅供参考，具体操作请咨询专业律师。")
        print(SEPARATOR)

    # 清理
    import asyncio
    asyncio.run(agent.close())


if __name__ == "__main__":
    main()
