from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from seju_lite.config.loader import load_config
from seju_lite.runtime.app import create_app
from seju_lite.runtime.runner import (
    close_app,
    run_cli_chat,
    run_forever,
)

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
    app_ctx = await create_app(config_path)
    try:
        await run_forever(app_ctx)
    finally:
        await close_app(app_ctx)


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
    typer.echo(f"Config OK: {Path(config).resolve()}")
    typer.echo(f"App: {cfg.app.name}")
    typer.echo(f"Provider: {cfg.provider.kind} / {cfg.provider.model}")


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

        typer.echo("Registered tools:")
        for item in defs:
            fn = item.get("function", {})
            name = fn.get("name", "<unknown>")
            desc = fn.get("description", "")
            if desc:
                typer.echo(f"- {name}: {desc}")
            else:
                typer.echo(f"- {name}")
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
        typer.echo("=== Provider Response ===")
        typer.echo(response.content or "")
        if response.tool_calls:
            typer.echo("\n=== Tool Calls ===")
            for tc in response.tool_calls:
                typer.echo(f"- {tc.name}: {tc.arguments}")
    finally:
        await close_app(app_ctx)