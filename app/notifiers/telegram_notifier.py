from telegram import Bot


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.enabled = bool(token and chat_id)
        self.chat_id = chat_id
        self.bot = Bot(token=token) if self.enabled else None

    async def send(self, text: str):
        if not self.enabled:
            return
        await self.bot.send_message(chat_id=self.chat_id, text=text)
