from __future__ import annotations

import asyncio

from seju_lite.bus.events import OutboundMessage
from seju_lite.channels.base import BaseChannel

DISCORD_MAX_CONTENT_LEN = 2000


class DiscordChannel(BaseChannel):
    name = "discord"
    display_name = "Discord"

    def __init__(
        self,
        token: str,
        bus,
        allow_from: list[str] | None = None,
        group_policy: str = "mention",
    ):
        super().__init__(bus=bus, allow_from=allow_from)
        self.token = token
        self.group_policy = group_policy
        self._client = None
        self._run_task: asyncio.Task | None = None
        self._bot_user_id: str | None = None

    async def start(self) -> None:
        if self._running:
            return
        if not self.token:
            raise ValueError("Discord token is required")

        try:
            import discord
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "discord.py is required for Discord channel. Install project dependencies first."
            ) from exc

        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        channel = self

        class _DiscordClient(discord.Client):
            async def on_ready(self):
                if self.user is not None:
                    channel._bot_user_id = str(self.user.id)
                channel._running = True

            async def on_message(self, message):
                if message.author.bot:
                    return

                sender_id = str(message.author.id)
                if not channel.is_allowed(sender_id):
                    return

                if message.guild is not None and not channel._should_respond_in_group(message):
                    return

                content = message.content or ""
                if message.attachments:
                    attachment_tags = [f"[attachment: {a.url}]" for a in message.attachments]
                    content = f"{content}\n" + "\n".join(attachment_tags) if content else "\n".join(
                        attachment_tags
                    )
                if not content:
                    content = "[empty message]"

                await channel.publish_inbound(
                    sender_id=sender_id,
                    chat_id=str(message.channel.id),
                    content=content,
                    metadata={"message_id": str(message.id)},
                )

        self._client = _DiscordClient(intents=intents)
        self._run_task = asyncio.create_task(self._client.start(self.token))

    async def stop(self) -> None:
        self._running = False
        if self._client is not None:
            await self._client.close()
        if self._run_task is not None:
            self._run_task.cancel()
            self._run_task = None

    async def send(self, msg: OutboundMessage) -> None:
        if self._client is None:
            return

        channel_obj = self._client.get_channel(int(msg.chat_id))
        if channel_obj is None:
            channel_obj = await self._client.fetch_channel(int(msg.chat_id))
        for chunk in self._split_content(msg.content or "", DISCORD_MAX_CONTENT_LEN):
            await channel_obj.send(chunk)

    @staticmethod
    def _split_content(content: str, max_len: int) -> list[str]:
        if len(content) <= max_len:
            return [content]

        chunks: list[str] = []
        text = content
        while len(text) > max_len:
            cut = text.rfind("\n", 0, max_len + 1)
            if cut <= 0:
                cut = max_len
            chunks.append(text[:cut])
            text = text[cut:].lstrip("\n")
        if text:
            chunks.append(text)
        return chunks

    def _should_respond_in_group(self, message) -> bool:
        if self.group_policy == "open":
            return True
        if self.group_policy != "mention":
            return True

        if self._bot_user_id is None:
            return False
        for user in message.mentions:
            if str(user.id) == self._bot_user_id:
                return True
        return False
