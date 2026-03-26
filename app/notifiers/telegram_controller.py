from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


class TelegramController:
    def __init__(self, token: str, allowed_chat_id: str, callbacks: dict):
        self.enabled = bool(token and allowed_chat_id)
        self.allowed_chat_id = str(allowed_chat_id or "")
        self.callbacks = callbacks
        self.app = Application.builder().token(token).build() if self.enabled else None

    def _is_allowed(self, update: Update) -> bool:
        cid = str(update.effective_chat.id) if update.effective_chat else ""
        return cid == self.allowed_chat_id

    async def _reject(self, update: Update):
        await update.message.reply_text("Unauthorized")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        await update.message.reply_text("Linkat MJ Trader controller online. Use /help")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        await update.message.reply_text(
            "Commands:\n"
            "/status - runtime status\n"
            "/pause - pause strategy execution\n"
            "/resume - resume strategy execution\n"
            "/paper - switch mode to paper\n"
            "/live CONFIRM - switch mode to live\n"
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        txt = self.callbacks["status"]()
        await update.message.reply_text(txt)

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        self.callbacks["pause"]()
        await update.message.reply_text("Paused")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        self.callbacks["resume"]()
        await update.message.reply_text("Resumed")

    async def cmd_paper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        self.callbacks["switch_mode"]("paper")
        await update.message.reply_text("Mode switched to paper")

    async def cmd_live(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        arg = context.args[0] if context.args else ""
        if arg != "CONFIRM":
            await update.message.reply_text("Use: /live CONFIRM")
            return
        self.callbacks["switch_mode"]("live")
        await update.message.reply_text("Mode switched to live")

    async def start(self):
        if not self.enabled:
            return
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))
        self.app.add_handler(CommandHandler("paper", self.cmd_paper))
        self.app.add_handler(CommandHandler("live", self.cmd_live))
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

    async def stop(self):
        if not self.enabled:
            return
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
