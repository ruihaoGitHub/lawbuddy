# Law Agent - 劳动法律咨询助手

## 项目结构

```
law-agent/
├── .claude/                          # Claude CLI 配置
│   ├── commands/                     # 自定义命令
│   │   ├── clear.md
│   │   ├── compact.md
│   │   ├── exit.md
│   │   └── log.md
│   └── skills/                       # 全局 Skills
│       └── skill-creator/            # Skill 创建工具
│           ├── agents/
│           ├── assets/
│           ├── eval-viewer/
│           ├── references/
│           ├── scripts/
│           ├── LICENSE.txt
│           └── SKILL.md
├── law_agent/                        # 核心代码
│   ├── __init__.py
│   ├── agent.py                      # 主入口
│   ├── prompts/
│   │   ├── law_agent_worker.txt      # 劳动者身份提示词
│   │   └── law_agent_hr.txt          # HR/企业管理者身份提示词
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── builtin_tools.py          # 内置工具列表
│   │   └── legal_tools.py            # 法律检索工具（法规/类案检索）
│   └── utils/
│       ├── __init__.py
│       ├── message_handler.py        # 消息处理
│       └── transcript.py             # 对话记录管理
├── workspace/                        # 工作目录（Agent cwd）
│   ├── .claude/
│   │   └── skills/                   # 项目级 Skills
│   │       ├── review-pdf-contract/  # PDF 合同审查
│   │       │   ├── scripts/
│   │       │   │   └── extract_text.py
│   │       │   └── SKILL.md
│   │       └── skill-creator/        # Skill 创建工具
│   └── contract.pdf                  # 示例合同文件
├── .env                              # 环境变量配置
├── .gitignore
├── pyproject.toml
├── questions.txt
└── README.md
```

## 技术栈

| 组件 | 说明 |
|------|------|
| Python 3.10+ | 核心运行时环境 |
| claude-agent-sdk | Claude Agent SDK，用于构建 AI Agent |
| python-dotenv | 环境变量管理 |
| requests | HTTP 请求库，用于调用外部 API |
| rich | 终端美化输出，支持 Markdown 渲染 |

## 环境配置

在项目根目录创建 `.env` 文件，配置以下环境变量：

```bash
# Claude API 配置
ANTHROPIC_API_KEY=<your_anthropic_api_key>
ANTHROPIC_BASE_URL=<your_anthropic_base_url>
MODEL_ID=<your_model_id>

# 法律检索 API 配置 (得理法律)
DELI_APPID=your_appid
DELI_SECRET=your_secret
```

**推荐可用方式**  
anthropic 官方 api key 在大陆环境较难满足稳定使用需求，建议在阿里百炼大模型平台申请 api key 进行使用

```python
ANTHROPIC_API_KEY = "<your_anthropic_api_key>"
ANTHROPIC_BASE_URL = "https://dashscope.aliyuncs.com/apps/anthropic"
MODEL_ID = "claude-sonnet-4-20250514"
```
- 获取百炼官方 api key：[获取 api key](https://help.aliyun.com/zh/model-studio/get-api-key?spm=a2c4g.11186623.0.0.5a656ce3vtXB78)
- 百炼官方支持使用的模型：[模型列表](https://help.aliyun.com/zh/model-studio/anthropic-api-messages?spm=a2c4g.11186623.help-menu-2400256.d_2_12_9.13ea5ec6Dht28F&scm=20140722.H_2980295._.OR_help-T_cn~zh-V_1#07833dedefft7)



## 自定义 Tool 方式

本项目使用 Claude Agent SDK 的 `@tool` 装饰器创建自定义工具。

### 1. 定义工具函数

```python
from claude_agent_sdk import tool, create_sdk_mcp_server
from typing import Any

@tool("tool_name", "工具描述，说明工具的功能和用途", {"param_name": param_type})
async def your_tool(args: dict[str, Any]) -> dict[str, Any]:
    """工具实现逻辑"""
    param = args.get("param_name", default_value)
    
    # 业务逻辑处理
    result = do_something(param)
    
    return {
        "content": [{
            "type": "text",
            "text": f"处理结果: {result}"
        }]
    }
```

### 2. 创建 MCP Server

```python
YOUR_TOOLS_SERVER = create_sdk_mcp_server(
    name="your_tools",
    version="1.0.0",
    tools=[your_tool_1, your_tool_2]
)
```

### 3. 注册到 Agent

在 `agent.py` 中配置：

```python
from tools.your_tools import YOUR_TOOLS_SERVER

options = ClaudeAgentOptions(
    mcp_servers={"your_tools": YOUR_TOOLS_SERVER},
    allowed_tools=[
        "mcp__your_tools__tool_name_1",
        "mcp__your_tools__tool_name_2",
    ],
)
```

**命名规则：** 工具在 Agent 中的名称格式为 `mcp__{server_name}__{tool_name}`

## 接入外部 MCP 方式

### 1. 内置 MCP Server（SDK 创建）

使用 `create_sdk_mcp_server` 创建的 MCP Server 直接通过 `mcp_servers` 参数配置：

```python
from claude_agent_sdk import ClaudeAgentOptions
from tools.legal_tools import LEGAL_TOOLS_SERVER

options = ClaudeAgentOptions(
    mcp_servers={"legal_tools": LEGAL_TOOLS_SERVER},
    allowed_tools=["mcp__legal_tools__search_law"],
)
```

### 2. 外部 MCP Server（Stdio 方式）

对于独立运行的 MCP Server，使用 `StdioMCPConnection` 配置：

```python
from claude_agent_sdk import ClaudeAgentOptions, StdioMCPConnection

options = ClaudeAgentOptions(
    mcp_servers={
        "external_server": StdioMCPConnection(
            command="python",
            args=["path/to/mcp_server.py"],
            env={"API_KEY": "xxx"}
        )
    },
    allowed_tools=["mcp__external_server__tool_name"],
)
```

### 3. 远程 MCP Server（SSE 方式）

支持 Server-Sent Events 的远程 MCP Server：

```python
from claude_agent_sdk import ClaudeAgentOptions, SSEMCPConnection

options = ClaudeAgentOptions(
    mcp_servers={
        "remote_server": SSEMCPConnection(
            url="https://mcp.example.com/sse",
            headers={"Authorization": "Bearer xxx"}
        )
    },
    allowed_tools=["mcp__remote_server__tool_name"],
)
```

## 创建 Skill 方式

Skill 是基于文件系统的能力扩展，Claude 会根据用户请求自动调用相关 Skill。

### 1. 目录结构

```
workspace/.claude/skills/
└── your-skill-name/
    ├── SKILL.md           # 必需：Skill 定义文件
    ├── scripts/           # 可选：脚本文件
    │   └── helper.py
    └── references/        # 可选：参考文档
        └── guide.md
```

### 2. SKILL.md 格式

```markdown
---
name: your-skill-name
description: |
  详细描述 Skill 的功能和使用场景。
  描述越具体，Claude 越能准确判断何时调用此 Skill。
  包含关键词和典型使用场景。
---

# Skill 标题

详细的使用说明和指导内容...

## 使用方法

具体操作步骤...

## 示例

使用示例...
```

### 3. 启用 Skill 加载

在 `ClaudeAgentOptions` 中配置：

```python
options = ClaudeAgentOptions(
    cwd="/path/to/workspace",           # 必须包含 .claude/skills/ 目录
    setting_sources=["project"],        # 加载项目级 Skills
    allowed_tools=["Skill", ...],       # 启用 Skill 工具
)
```

**配置说明：**
- `setting_sources=["project"]`: 从项目的 `.claude/skills/` 加载
- `setting_sources=["user"]`: 从用户目录 `~/.claude/skills/` 加载
- `setting_sources=["user", "project"]`: 同时加载用户级和项目级 Skills

### 4. Skill 发现机制

- Claude 自动扫描 `cwd/.claude/skills/*/SKILL.md` 文件
- 根据 `description` 字段判断是否调用
- 用户可通过询问 "What Skills are available?" 查看可用 Skills

### 5. 最佳实践

- **描述要具体**：包含触发关键词和使用场景
- **名称使用 kebab-case**：如 `review-labor-contract`
- **提供脚本支持**：复杂操作封装为可执行脚本
- **包含使用示例**：帮助 Claude 理解如何使用
