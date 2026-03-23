import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from seju_lite.bus.events import OutboundMessage
from seju_lite.channels.base import BaseChannel


class TelegramChannel(BaseChannel):
    name = "telegram"
    display_name = "Telegram"

    def __init__(self, token: str, bus, allow_from: list[str] | None = None):
        super().__init__(bus=bus, allow_from=allow_from)
        self.token = token
        self.app = Application.builder().token(token).build()
        self.logger = logging.getLogger("seju_lite.channels.telegram")

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_message or not update.effective_chat or not update.effective_user:
            return

        user_id = str(update.effective_user.id)
        username = (update.effective_user.username or "").strip()
        username_with_at = f"@{username}" if username else ""
        # allowFrom supports numeric user id and username (with or without @)
        if self.allow_from:
            allow_from = {str(item).strip().lower() for item in self.allow_from}
            user_id_l = user_id.lower()
            username_l = username.lower()
            username_with_at_l = username_with_at.lower()
            allowed = (
                user_id_l in allow_from
                or (username and username_l in allow_from)
                or (username_with_at and username_with_at_l in allow_from)
            )
            if not allowed:
                self.logger.info(
                    "Telegram message ignored by allowFrom: user_id=%s username=%s allowFrom=%s",
                    user_id,
                    username or "(none)",
                    sorted(self.allow_from),
                )
                return

        text = update.effective_message.text or ""
        if not text.strip():
            self.logger.info("Telegram message ignored: empty text from user_id=%s", user_id)
            return

        await self.publish_inbound(
            sender_id=user_id,
            chat_id=str(update.effective_chat.id),
            content=text,
            metadata={"message_id": update.effective_message.message_id},
        )

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat:
            await self.app.bot.send_message(
                chat_id=str(update.effective_chat.id),
                text="Bot is online. Send any text message to start chatting.",
            )

    async def start(self):
        # add handler
        self.app.add_handler(CommandHandler("start", self.on_start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message))
        # start app
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        self._running = True

    async def stop(self) -> None:
        if not self._running:
            return
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        await self.app.bot.send_message(chat_id=msg.chat_id, text=msg.content)
