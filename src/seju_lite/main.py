
'''

app start

    if user send "hello"

    1. TelegramChannel.on_message() 收到 Telegram update
    2. 构造：

        InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="hello"
        )
    3. add to bus._inbound
    4. inbound_worker() 取出这条消息
    5. 调用 agent.process_message(msg)
    6. AgentLoop：
        找 session
        取历史
        ContextBuilder.build_messages(...)
        调 GeminiProvider.generate(...)
        得到文本回复
        保存本轮 session
    7. inbound_worker() 构造 OutboundMessage
    8. 塞进 bus._outbound
    9. outbound_worker() 取出消息
    10. TelegramChannel.send_message() 发回用户
'''

import asyncio
import typer
from dotenv import load_dotenv

from seju_lite.bus.queue import MessageBus
from seju_lite.channels.telegram_bot import TelegramChannel
from seju_lite.config.loader import load_config
from seju_lite.providers.openai_compatible import OpenAICompatibleProvider
from seju_lite.providers.gemini_provider import GeminiProvider
from seju_lite.agent.loop import AgentLoop

#创建 CLI 应用
app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: str = typer.Option("config.json", "--config", "-c"),
):
    if ctx.invoked_subcommand is None:
        asyncio.run(_run(config))


@app.command()
def run(config: str = typer.Option("config.json", "--config", "-c")):
    asyncio.run(_run(config))


async def _run(config_path: str):

    # read .env
    load_dotenv()

    # load config
    config = load_config(config_path)

    # build bus 
    bus = MessageBus()  
    # provider = OpenAICompatibleProvider(
    #     base_url=config.provider.baseUrl,
    #     api_key=config.provider.apiKey,
    #     model=config.provider.model,
    #     temperature=config.provider.temperature,
    #     max_tokens=config.provider.maxTokens,
    # )

    # build provider
    provider = GeminiProvider(
        api_key=config.provider.apiKey,
        model=config.provider.model,
        temperature=config.provider.temperature,
        max_output_tokens=config.provider.maxOutputTokens,
    )

    # build agent loop
    agent = AgentLoop(config=config, provider=provider, bus=bus)

    # build tele port
    telegram = TelegramChannel( 
        token=config.channels.telegram.token,
        bus=bus,
        allow_from=config.channels.telegram.allowFrom
    )

    # GET msg from outbound queue
    async def outbound_worker():
        while True:
            msg = await bus.consume_outbound()
            if msg.channel == "telegram":
                await telegram.send_message(msg)

    async def inbound_worker():
        while True:
            msg = await bus.consume_inbound()
            try:
                text = await agent.process_message(msg)
            except Exception:
                text = "Provider request failed. Please check API key/billing/quota and try again."
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
