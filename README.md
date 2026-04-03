# 法律咨询助手 - 多场景智能咨询

基于 LangGraph 的命令行法律咨询 Agent，通过阿里云百炼平台接入大模型，支持多种法律咨询场景，像律师一样逐步追问收集案件信息，结合法律知识给出分析建议。

## 项目特点

- 多场景支持：目前支持拖欠工资和工伤赔偿两个场景
- 智能路由：自动识别用户咨询的场景并路由到相应的Agent
- 逐步收集：像真实律师一样逐步追问，收集案件关键信息
- 进度跟踪：实时查看收集进度和已收集信息

## 项目结构

```
├── cli.py                # 命令行交互入口（启动文件）
├── agents/               # Agent 目录
│   ├── __init__.py
│   ├── base_agent.py   # Agent 基类（状态管理、会话恢复）
│   ├── llm_client.py   # 百炼平台 LLM 客户端
│   ├── router_agent.py  # 路由Agent（场景识别和路由）
│   ├── salary_agent.py  # 拖欠工资 Agent
│   ├── injury_compensation_agent.py  # 工伤赔偿 Agent
│   └── template_scenario_agent.py  # 模板场景 Agent
├── models/              # 数据模型目录
│   ├── __init__.py
│   ├── simple_models.py  # 基础数据模型
│   └── extended_models.py  # 扩展数据模型（多场景定义）
├── services/            # 服务目录
│   ├── __init__.py
│   └── deli.py      # 得理 API 服务（Mock + 真实接口）
├── .env               # 环境变量配置
├── requirements.txt     # Python 依赖
└── README.md
```

## 支持场景

1. **拖欠工资维权** - 处理工资拖欠相关的法律咨询
2. **工伤赔偿** - 处理工伤赔偿相关的法律咨询

## 工作流

### 整体流程

```
用户输入 → 场景识别 → 路由到相应场景Agent → 信息收集 → 法律分析 → 结束
```

### 场景Agent流程

```
welcome → collect ⇄ collect → analyze → END
            ↑         ↓
            └─────────┘  (信息不足时循环)
```

- **welcome**: LLM 生成欢迎语，引导用户描述问题
- **collect**: LLM 理解用户输入，智能提取字段，自然语言追问
- **analyze**: 调用得理 API + LLM 生成法律分析报告

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置百炼 API Key

编辑 `.env` 文件，填入你的阿里云百炼 API Key：

```
DASHSCOPE_API_KEY=sk-your-api-key-here
LLM_MODEL_NAME=qwen-plus
```

> 百炼平台地址：https://bailian.console.aliyun.com/

### 3. 启动

```bash
python cli.py
```

### 4. 交互

```
[你] 我在深圳一个工厂上班，老板拖欠了三个月工资
[律师助理] 很抱歉听到这个情况。请问您能告诉我每月的工资大概是多少吗？

[你] 6000块
[律师助理] 了解。那这家工厂叫什么名字呢？

[你] 进度
  当前场景: 拖欠工资维权
  当前进度: 50%
  已收集: work_location, arrears_months, monthly_salary
  当前步骤: collect

[你] 场景
  当前咨询场景: 拖欠工资维权
  支持的所有场景:
  → 拖欠工资维权
    工伤赔偿

[你] 我在工地受伤了
[律师助理] 很抱歉听到您受伤的消息。为了更好地帮助您，我需要了解一些信息。请问您是在哪里工作时受伤的吗？
```

## 技术栈

- **LangGraph** — Agent 状态机和工作流
- **langchain-openai** — 百炼平台 LLM 接入（OpenAI 兼容模式）
- **Pydantic v2** — 数据模型和结构化输出
- **httpx** — 得理 API HTTP 客户端
- **python-dotenv** — 环境变量管理

## 配置项

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `DASHSCOPE_API_KEY` | 百炼平台 API Key（必填） | - |
| `LLM_MODEL_NAME` | 模型名称 | `qwen-plus` |
| `DASHSCOPE_BASE_URL` | API 基础 URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

## 命令行交互命令

- `quit` 或 `退出` - 结束对话
- `进度` 或 `progress` - 查看当前收集进度
- `场景` 或 `scenario` - 查看当前咨询的场景

## 扩展场景

要添加新的法律咨询场景，可以参考 `agents/template_scenario_agent.py` 中的模板，创建新的场景Agent类，并在 `cli.py` 中注册。

## 注意事项

- 本工具仅供参考，具体操作请咨询专业律师
- 得理 API 目前使用 Mock 数据，如需使用真实 API，请修改相应配置
- 项目基于 Conda 虚拟环境 `legal_agent` 开发，Python 版本建议 3.10+

## 许可证

MIT License
