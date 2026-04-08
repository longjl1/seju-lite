from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.table import Table

from seju_lite.agent.v2.token_compare import build_context_token_snapshot
from seju_lite.api.server import build_api
from seju_lite.cli.console import (
    console,
    print_config_summary,
    print_provider_response,
    print_tools_table,
)
from seju_lite.config.loader import load_config
from seju_lite.runtime.app import create_app
from seju_lite.runtime.runner import (
    close_app,
    run_cli_chat,
    run_forever,
)
from seju_lite.runtime.single_instance import InstanceLock
from seju_lite.tools.mcp_server import run_mcp_server

app = typer.Typer(
    help="seju-lite CLI",
    no_args_is_help=True,
)


@app.command("start")
def start_command(
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
) -> None:
    """
    Start the long-running runtime service.
    """
    asyncio.run(_start_async(config))


async def _start_async(config_path: str) -> None:
    lock = InstanceLock(Path("./workspace/runtime/start.lock"))
    lock.acquire()
    try:
        app_ctx = await create_app(config_path)
        try:
            await run_forever(app_ctx)
        finally:
            await close_app(app_ctx)
    finally:
        lock.release()


@app.command("chat")
def chat_command(
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
    session: str = typer.Option("cli:local", "--session", "-s", help="CLI session key"),
) -> None:
    """
    Run local terminal chat without Telegram.
    """
    asyncio.run(_chat_async(config, session))


async def _chat_async(config_path: str, session_key: str) -> None:
    app_ctx = await create_app(config_path)

    try:
        await run_cli_chat(app_ctx, session_key=session_key)
    finally:
        await close_app(app_ctx)


@app.command("config-validate")
def config_validate_command(
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
) -> None:
    """
    Validate config file only.
    """
    cfg = load_config(config)
    print_config_summary(
        str(Path(config).resolve()),
        cfg.app.name,
        f"{cfg.provider.kind} / {cfg.provider.model}",
    )


@app.command("tool-list")
def tool_list_command(
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
) -> None:
    """
    Print registered tools from runtime.
    """
    asyncio.run(_tool_list_async(config))


async def _tool_list_async(config_path: str) -> None:
    app_ctx = await create_app(config_path)
    try:
        defs = app_ctx.agent.tools.get_definitions()
        if not defs:
            typer.echo("No tools registered.")
            return
        print_tools_table(defs)
    finally:
        await close_app(app_ctx)


@app.command("test-provider")
def test_provider_command(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Prompt to send to provider"),
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
) -> None:
    """
    Send one prompt directly to provider for debugging.
    """
    asyncio.run(_test_provider_async(config, prompt))


async def _test_provider_async(config_path: str, prompt: str) -> None:
    app_ctx = await create_app(config_path)
    try:
        response = await app_ctx.provider.generate(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
        )
        print_provider_response(response.content or "", response.tool_calls)
    finally:
        await close_app(app_ctx)


@app.command("compare-context-tokens")
def compare_context_tokens_command(
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
    session: str = typer.Option("cli:local", "--session", "-s", help="Session key to inspect"),
    message: str = typer.Option(..., "--message", "-m", help="Current user message to test"),
    with_llm_summary: bool = typer.Option(
        False,
        "--with-llm-summary",
        help="Also compare v2_llm_summary by generating an actual summary through the provider",
    ),
    force_history: bool = typer.Option(
        False,
        "--force-history",
        help="Ignore context policy and always compare against the same raw session history window",
    ),
) -> None:
    """
    Compare old and v2 context token usage for the same session history.
    """
    asyncio.run(_compare_context_tokens_async(config, session, message, with_llm_summary, force_history))


async def _compare_context_tokens_async(
    config_path: str,
    session_key: str,
    message: str,
    with_llm_summary: bool,
    force_history: bool,
) -> None:
    app_ctx = await create_app(config_path)
    try:
        session = app_ctx.agent.sessions.get_or_create(session_key)
        modes = ["old", "v2_trim"]
        if with_llm_summary:
            modes.append("v2_llm_summary")

        snapshots = []
        for mode in modes:
            snapshot = await build_context_token_snapshot(
                workspace=app_ctx.agent.workspace,
                system_prompt=app_ctx.config.agent.systemPrompt,
                provider=app_ctx.provider,
                model_name=app_ctx.config.provider.model,
                session=session,
                current_message=message,
                max_history=app_ctx.config.agent.maxHistory,
                include_memory=app_ctx.config.agent.enableMemory,
                include_skills=app_ctx.config.agent.enableSkills,
                mode=mode,
                summary_trigger_messages=app_ctx.config.agent.v2SummaryTriggerMessages,
                summary_keep_recent_messages=app_ctx.config.agent.v2SummaryKeepRecentMessages,
                summary_max_messages_to_summarize=app_ctx.config.agent.v2SummaryMaxMessagesToSummarize,
                respect_policy=not force_history,
            )
            snapshots.append(snapshot)

        baseline = next((item for item in snapshots if item.mode == "old"), None)

        table = Table(title="Context Token Comparison")
        table.add_column("Mode")
        table.add_column("History")
        table.add_column("Msgs")
        table.add_column("Chars", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Delta vs old", justify="right")

        for item in snapshots:
            if baseline is None:
                delta = "-"
            else:
                delta_value = item.token_count - baseline.token_count
                delta = f"{delta_value:+d}"
            table.add_row(
                item.mode,
                str(item.history_count),
                str(item.message_count),
                str(item.char_count),
                str(item.token_count),
                delta,
            )

        console.print(table)
        if snapshots:
            console.print(
                f"[dim]Tokenizer: {snapshots[0].tokenizer} | Session: {session_key} | Message: {message}[/dim]"
            )
    finally:
        await close_app(app_ctx)


@app.command("mcp-server")
def mcp_server_command(
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="MCP transport (stdio/sse/streamable-http)",
    ),
    name: str = typer.Option("seju-lite-tools", "--name", "-n", help="MCP server name"),
) -> None:
    """
    Start an MCP server that exposes seju-lite built-in tools.
    """
    cfg = load_config(config)
    run_mcp_server(
        transport=transport,
        name=name,
        read_root=Path(cfg.tools.readFile.rootDir),
        web_max_chars=cfg.tools.web.maxChars,
    )


@app.command("api")
def api_command(
    config: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind"),
    port: int = typer.Option(8000, "--port", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto reload"),
) -> None:
    """
    Start HTTP API server for frontend/backend integration.
    """
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is required. Install with: uv add uvicorn fastapi") from exc

    api = build_api(config_path=config)
    uvicorn.run(api, host=host, port=port, reload=reload)
