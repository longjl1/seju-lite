from __future__ import annotations

import asyncio
import contextlib
import logging

from seju_lite.bus.events import InboundMessage, OutboundMessage
from seju_lite.runtime.app import SejuApp

logger = logging.getLogger("seju_lite.runtime")


def _enter_cli_quiet_mode() -> dict[str, int | bool]:
    """Reduce noisy third-party logs in interactive CLI chat."""
    targets = [
        "LiteLLM",
        "httpx",
        "httpcore",
        "openai",
        "asyncio",
    ]
    prev_levels: dict[str, int] = {}
    for name in targets:
        lg = logging.getLogger(name)
        prev_levels[name] = lg.level
        lg.setLevel(logging.WARNING)

    state: dict[str, int | bool] = {"_enabled": True, **prev_levels}

    # Best-effort: silence LiteLLM verbose prints if available.
    try:
        import litellm  # type: ignore

        state["litellm_set_verbose"] = bool(getattr(litellm, "set_verbose", False))
        state["litellm_suppress_debug_info"] = bool(
            getattr(litellm, "suppress_debug_info", False)
        )
        if hasattr(litellm, "set_verbose"):
            litellm.set_verbose = False
        if hasattr(litellm, "suppress_debug_info"):
            litellm.suppress_debug_info = True
    except Exception:
        state["litellm_set_verbose"] = False
        state["litellm_suppress_debug_info"] = False

    return state


def _exit_cli_quiet_mode(state: dict[str, int | bool]) -> None:
    if not state:
        return

    for name, level in state.items():
        if name.startswith("_") or name.startswith("litellm_"):
            continue
        logging.getLogger(name).setLevel(int(level))

    try:
        import litellm  # type: ignore

        if "litellm_set_verbose" in state and hasattr(litellm, "set_verbose"):
            litellm.set_verbose = bool(state["litellm_set_verbose"])
        if "litellm_suppress_debug_info" in state and hasattr(litellm, "suppress_debug_info"):
            litellm.suppress_debug_info = bool(state["litellm_suppress_debug_info"])
    except Exception:
        pass


def _format_runtime_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "503" in msg or "unavailable" in msg or "high demand" in msg:
        return "Model service is temporarily busy (503). Please try again in a moment."
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg:
        return "Request quota/rate limit reached (429). Please retry later."
    if "403" in msg or "permission_denied" in msg:
        return "Provider permission denied (403). Please check API key and project settings."
    return "Sorry, something went wrong while processing your message."


async def inbound_worker(app: SejuApp) -> None:
    """
    Consume inbound messages, pass them to AgentLoop,
    then publish outbound messages.
    """
    while True:
        inbound = await app.bus.consume_inbound()
        logger.info(
            "Inbound message: channel=%s chat_id=%s sender_id=%s",
            inbound.channel,
            inbound.chat_id,
            inbound.sender_id,
        )

        try:
            reply = await app.workflow_orchestrator.handle(inbound)
        except Exception as exc:
            logger.exception("Failed to process inbound message")
            reply = _format_runtime_error(exc)

        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=reply,
            metadata={
                "reply_to_message_id": inbound.metadata.get("message_id"),
            },
        )
        await app.bus.publish_outbound(outbound)


async def outbound_worker(app: SejuApp) -> None:
    """
    Consume outbound messages and dispatch them to the matching channel.
    """
    while True:
        outbound = await app.bus.consume_outbound()
        logger.info(
            "Outbound message: channel=%s chat_id=%s",
            outbound.channel,
            outbound.chat_id,
        )

        try:
            channel = app.channels.get(outbound.channel)
            if channel is None:
                logger.warning("Unsupported outbound channel: %s", outbound.channel)
                continue
            await channel.send(outbound)
        except Exception:
            logger.exception("Failed to send outbound message")


async def run_forever(app: SejuApp) -> None:
    """
    Start enabled channels and keep the runtime alive forever.
    """
    tasks: list[asyncio.Task] = []

    for name, channel in app.channels.items():
        await channel.start()
        logger.info("%s channel started", name)

    tasks.append(asyncio.create_task(inbound_worker(app), name="inbound-worker"))
    tasks.append(asyncio.create_task(outbound_worker(app), name="outbound-worker"))

    logger.info(
        "Runtime started: app=%s env=%s",
        app.config.app.name,
        app.config.app.env,
    )

    try:
        await asyncio.Event().wait()
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def run_cli_chat(app: SejuApp, session_key: str = "cli:local") -> None:
    """
    Local terminal chat loop for development.
    Reuses the same orchestrator path, but bypasses Telegram/bus.
    """
    logger.info("Starting CLI chat session: %s", session_key)
    print("seju-lite CLI chat")
    print("Type /exit to quit.\n")
    quiet_state = _enter_cli_quiet_mode()

    if ":" in session_key:
        channel, chat_id = session_key.split(":", 1)
    else:
        channel, chat_id = "cli", session_key

    try:
        while True:
            try:
                user_text = await asyncio.to_thread(input, "You > ")
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return

            if not user_text.strip():
                continue

            if user_text.strip().lower() in {"/exit", "exit", "quit"}:
                print("Bye.")
                return

            inbound = InboundMessage(
                channel=channel,
                sender_id="local-user",
                chat_id=chat_id,
                content=user_text,
                metadata={},
            )

            try:
                reply = await app.workflow_orchestrator.handle(inbound)
            except Exception as exc:
                logger.exception("CLI chat failed")
                reply = _format_runtime_error(exc)

            print(f"Bot > {reply}\n")
    finally:
        _exit_cli_quiet_mode(quiet_state)


async def close_app(app: SejuApp) -> None:
    """
    Best-effort shutdown hook.
    """
    with contextlib.suppress(Exception):
        await app.agent.subagents.close()

    if app.mcp_client_hub is not None:
        with contextlib.suppress(Exception):
            await app.mcp_client_hub.close()

    for channel in app.channels.values():
        with contextlib.suppress(Exception):
            await channel.stop()
