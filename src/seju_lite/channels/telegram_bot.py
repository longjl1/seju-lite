from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from seju_lite.bus.events import InboundMessage, OutboundMessage


class TelegramChannel:
    def __init__(self, token: str, bus, allow_from: list[str] | None = None):
        self.token = token
        self.bus = bus
        self.allow_from = set(allow_from or [])
        self.app = Application.builder().token(token).build()

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_message or not update.effective_chat or not update.effective_user:
            return

        user_id = str(update.effective_user.id)
        if self.allow_from and user_id not in self.allow_from:
            return

        text = update.effective_message.text or ""
        inbound = InboundMessage(
            channel="telegram",
            sender_id=user_id,
            chat_id=str(update.effective_chat.id),
            content=text,
            metadata={"message_id": update.effective_message.message_id}
        )
        await self.bus.publish_inbound(inbound)

    async def start(self):
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message))
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def send_message(self, msg: OutboundMessage):
        await self.app.bot.send_message(chat_id=msg.chat_id, text=msg.content)