from __future__ import annotations

import asyncio
import contextlib
import logging

from seju_lite.bus.events import InboundMessage, OutboundMessage
from seju_lite.runtime.app import SejuApp

logger = logging.getLogger("seju_lite.runtime")


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
            reply = await app.agent.process_message(inbound)
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
            if outbound.channel == "telegram":
                if app.telegram is None:
                    logger.warning("Telegram channel is not initialized")
                    continue
                await app.telegram.send_message(outbound)
            else:
                logger.warning("Unsupported outbound channel: %s", outbound.channel)
        except Exception:
            logger.exception("Failed to send outbound message")


async def run_forever(app: SejuApp) -> None:
    """
    Start enabled channels and keep the runtime alive forever.
    """
    tasks: list[asyncio.Task] = []

    if app.telegram is not None:
        await app.telegram.start()
        logger.info("Telegram channel started")

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
    Reuses the same AgentLoop, but bypasses Telegram/bus.
    """
    logger.info("Starting CLI chat session: %s", session_key)
    print("seju-lite CLI chat")
    print("Type /exit to quit.\n")

    if ":" in session_key:
        channel, chat_id = session_key.split(":", 1)
    else:
        channel, chat_id = "cli", session_key

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
            reply = await app.agent.process_message(inbound)
        except Exception as exc:
            logger.exception("CLI chat failed")
            reply = _format_runtime_error(exc)

        print(f"Bot > {reply}\n")


async def close_app(app: SejuApp) -> None:
    """
    Best-effort shutdown hook.
    """
    if app.telegram is not None:
        with contextlib.suppress(Exception):
            await app.telegram.app.updater.stop()
        with contextlib.suppress(Exception):
            await app.telegram.app.stop()
        with contextlib.suppress(Exception):
            await app.telegram.app.shutdown()
