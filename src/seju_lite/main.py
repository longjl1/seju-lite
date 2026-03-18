import asyncio
import typer
from dotenv import load_dotenv

from seju_lite.bus.queue import MessageBus
from seju_lite.channels.telegram_bot import TelegramChannel
from seju_lite.config.loader import load_config
from seju_lite.providers.openai_compatible import OpenAICompatibleProvider
from seju_lite.agent.loop import AgentLoop

app = typer.Typer()


@app.command()
def run(config: str = "config.json"):
    asyncio.run(_run(config))


async def _run(config_path: str):
    load_dotenv()
    config = load_config(config_path)

    bus = MessageBus()
    provider = OpenAICompatibleProvider(
        base_url=config.provider.baseUrl,
        api_key=config.provider.apiKey,
        model=config.provider.model,
        temperature=config.provider.temperature,
        max_tokens=config.provider.maxTokens,
    )

    agent = AgentLoop(config=config, provider=provider, bus=bus)

    telegram = TelegramChannel(
        token=config.channels.telegram.token,
        bus=bus,
        allow_from=config.channels.telegram.allowFrom
    )

    async def outbound_worker():
        while True:
            msg = await bus.consume_outbound()
            if msg.channel == "telegram":
                await telegram.send_message(msg)

    async def inbound_worker():
        while True:
            msg = await bus.consume_inbound()
            text = await agent.process_message(msg)
            await bus.publish_outbound(
                type("Obj", (), {
                    "channel": msg.channel,
                    "chat_id": msg.chat_id,
                    "content": text,
                    "metadata": {}
                })()
            )

    await telegram.start()
    await asyncio.gather(outbound_worker(), inbound_worker())


if __name__ == "__main__":
    app()