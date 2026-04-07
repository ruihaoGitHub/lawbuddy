"""Entry point for law agent with continuous conversation mode."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    SystemMessage,
    StreamEvent,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
    ResultMessage,
    TextBlock,
)

from utils.transcript import setup_session, TranscriptWriter
from utils.message_handler import process_assistant_message
from tools.legal_tools import LEGAL_TOOLS_SERVER
from tools.builtin_tools import built_in_tools

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"
console = Console()


def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_path = PROMPTS_DIR / filename
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def select_identity() -> tuple[str, str]:
    """Let user select their identity and return (identity_name, prompt_filename)."""
    console.print("\n" + "=" * 50)
    console.print("  Law Agent - 法律咨询助手")
    console.print("=" * 50)
    console.print("\n请选择您的身份：")
    console.print("  [1] 劳动者 - 保障劳动权益，获取维权指导")
    console.print("  [2] HR/企业管理者 - 合规用工指导，风险防控建议")
    console.print()

    while True:
        choice = input("请输入选项 (1/2): ").strip()
        if choice == "1":
            return "劳动者", "law_agent_worker.txt"
        elif choice == "2":
            return "HR/企业管理者", "law_agent_hr.txt"
        else:
            console.print("[red]无效选项，请输入 1 或 2[/red]")


def print_help():
    """Print available commands."""
    console.print("\n[bold]可用命令:[/bold]")
    console.print("  /exit    - 退出程序")
    console.print("  /clear   - 清空当前对话，开始新会话")
    console.print("  /compact - 压缩对话上下文")
    console.print("  /log     - 保存对话记录到文件")
    console.print("  /help    - 显示帮助信息\n")


async def chat():
    """Start interactive chat with the law agent."""

    missing_keys = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing_keys.append("ANTHROPIC_API_KEY")
    if not os.environ.get("DELI_APPID"):
        missing_keys.append("DELI_APPID")
    if not os.environ.get("DELI_SECRET"):
        missing_keys.append("DELI_SECRET")

    if missing_keys:
        console.print("\n[red]Error: Missing required environment variables:[/red]")
        for key in missing_keys:
            console.print(f"  - {key}")
        console.print("\nSet them in a .env file or export them in your shell.")
        console.print("  - ANTHROPIC_API_KEY: https://console.anthropic.com/settings/keys")
        console.print("  - DELI_APPID/SECRET: https://open.delilegal.com\n")
        return

    identity_name, prompt_file = select_identity()
    law_agent_prompt = load_prompt(prompt_file)

    transcript_file, session_dir = setup_session()
    transcript = TranscriptWriter()
    transcript.set_save_path(transcript_file)

    workspace_dir = Path(__file__).parent.parent / "workspace"
    options = ClaudeAgentOptions(
        model=os.getenv("MODEL_ID"),
        cwd=str(workspace_dir),
        permission_mode="bypassPermissions",
        system_prompt=law_agent_prompt,
        mcp_servers={"legal_tools": LEGAL_TOOLS_SERVER},
        setting_sources=["project"],
        allowed_tools=built_in_tools + [
            "Skill",
            "mcp__legal_tools__search_law",
            "mcp__legal_tools__search_cases",
        ],
    )

    console.print("\n" + "-" * 50)
    console.print(f"  当前身份: [bold]{identity_name}[/bold]")
    console.print("-" * 50)
    console.print("\n输入 /help 查看可用命令")

    try:
        async with ClaudeSDKClient(options=options) as client:
            while True:
                try:
                    user_input = input("你: ").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_input:
                    continue

                transcript.write_to_file(f"\ntype in: {user_input}\n")

                if user_input.startswith("/"):
                    command = user_input.lower().split()[0]

                    if command in ["/exit", "/quit"]:
                        console.print("\n[bold green]Bye ![/bold green]")
                        break

                    elif command == "/clear":
                        await client.disconnect()
                        transcript.close()
                        transcript_file, session_dir = setup_session()
                        transcript = TranscriptWriter()
                        transcript.set_save_path(transcript_file)
                        await client.connect()
                        await client.query("")
                        new_session_id = None
                        async for msg in client.receive_response():
                            if isinstance(msg, ResultMessage):
                                new_session_id = msg.session_id
                        if new_session_id:
                            console.print(f"\n[bold green]已开始新会话[/bold green] [dim](Session ID: {new_session_id})[/dim]")
                        else:
                            console.print("\n[bold green]已开始新会话[/bold green]")
                        continue

                    elif command == "/compact":
                        await client.query(prompt="/compact")
                        async for msg in client.receive_response():
                            if isinstance(msg, SystemMessage) and getattr(msg, 'subtype', None) == "compact_boundary":
                                console.print("\n[dim]对话上下文已压缩[/dim]")
                        continue

                    elif command == "/log":
                        saved_path = transcript.save_to_file()
                        if saved_path:
                            console.print(f"\n[dim]对话记录已保存至: {saved_path}[/dim]")
                        else:
                            console.print("\n[yellow]对话记录已保存过或无法保存[/yellow]")
                        continue

                    elif command == "/help":
                        print_help()
                        continue

                await client.query(prompt=user_input)

                response_text = ""
                async for msg in client.receive_response():
                    if isinstance(msg, StreamEvent):
                        event = msg.event
                        event_type = event.get("type")
                        if event_type == "content_block_start":
                            content_block = event.get("content_block", {})
                            if content_block.get("type") == "tool_use":
                                tool_name = content_block.get("name", "unknown")
                                console.print(f"\n[dim][Using tool: {tool_name}][/dim]")
                        elif event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "thinking_delta":
                                thinking = delta.get("thinking", "")
                                if thinking:
                                    console.print(f"\n[dim][Thinking: {thinking}][/dim]")
                    elif type(msg).__name__ == 'AssistantMessage':
                        for block in msg.content:
                            if isinstance(block, ThinkingBlock):
                                console.print(f"\n[dim][Thinking: {block.thinking}][/dim]")
                            elif isinstance(block, ToolUseBlock):
                                console.print(f"\n[dim][Tool call: {block.name}][/dim]")
                            elif isinstance(block, ToolResultBlock):
                                if block.is_error:
                                    console.print(f"\n[dim][Tool result: ERROR][/dim]")
                                else:
                                    result_preview = str(block.content)[:100] if block.content else "None"
                                    console.print(f"\n[dim][Tool result: {result_preview}...][/dim]")
                            elif isinstance(block, TextBlock):
                                response_text += block.text
                        process_assistant_message(msg, transcript)

                if response_text:
                    console.print()
                    md = Markdown(response_text)
                    console.print(md)

                transcript.write("\n")
    finally:
        transcript.close()


if __name__ == "__main__":
    asyncio.run(chat())
