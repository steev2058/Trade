from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes


class TelegramController:
    def __init__(self, token: str, allowed_chat_id: str, callbacks: dict):
        self.enabled = bool(token and allowed_chat_id)
        self.allowed_chat_id = str(allowed_chat_id or "")
        self.callbacks = callbacks
        self.app = Application.builder().token(token).build() if self.enabled else None
        self.keyboard = ReplyKeyboardMarkup(
            [
                ["/status", "/balance"],
                ["/positions", "/pnl"],
                ["/pause", "/resume"],
                ["/paper", "/live CONFIRM"],
                ["/buy XAUUSD 0.01", "/sell XAUUSD 0.01"],
                ["/close 123456", "/sl_tp 123456 2500 2600"],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    def _is_allowed(self, update: Update) -> bool:
        cid = str(update.effective_chat.id) if update.effective_chat else ""
        return cid == self.allowed_chat_id

    async def _reject(self, update: Update):
        await update.message.reply_text("Unauthorized")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        await update.message.reply_text("Linkat MJ Trader controller online. Use /help", reply_markup=self.keyboard)

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
            "/positions - list open positions\n"
            "/balance - account balance snapshot\n"
            "/pnl - current open pnl snapshot\n"
            "/close_all CONFIRM - close all positions (guarded)\n"
            "/buy SYMBOL LOT - open buy via bridge\n"
            "/sell SYMBOL LOT - open sell via bridge\n"
            "/close TICKET - close one position\n"
            "/sl_tp TICKET SL TP - modify SL/TP\n"
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

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        await update.message.reply_text(self.callbacks["positions"]())

    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        await update.message.reply_text(self.callbacks["balance"]())

    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        await update.message.reply_text(self.callbacks["pnl"]())

    async def cmd_close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        arg = context.args[0] if context.args else ""
        if arg != "CONFIRM":
            await update.message.reply_text("Use: /close_all CONFIRM")
            return
        await update.message.reply_text(self.callbacks["close_all"]())

    async def cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        if len(context.args) < 2:
            return await update.message.reply_text("Use: /buy SYMBOL LOT")
        symbol = context.args[0]
        lot = float(context.args[1])
        await update.message.reply_text(self.callbacks["open"](symbol, "buy", lot))

    async def cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        if len(context.args) < 2:
            return await update.message.reply_text("Use: /sell SYMBOL LOT")
        symbol = context.args[0]
        lot = float(context.args[1])
        await update.message.reply_text(self.callbacks["open"](symbol, "sell", lot))

    async def cmd_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        if len(context.args) < 1:
            return await update.message.reply_text("Use: /close TICKET")
        ticket = int(context.args[0])
        await update.message.reply_text(self.callbacks["close"](ticket))

    async def cmd_sl_tp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_allowed(update):
            return await self._reject(update)
        if len(context.args) < 3:
            return await update.message.reply_text("Use: /sl_tp TICKET SL TP")
        ticket = int(context.args[0])
        sl = float(context.args[1])
        tp = float(context.args[2])
        await update.message.reply_text(self.callbacks["sl_tp"](ticket, sl, tp))

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
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        self.app.add_handler(CommandHandler("close_all", self.cmd_close_all))
        self.app.add_handler(CommandHandler("buy", self.cmd_buy))
        self.app.add_handler(CommandHandler("sell", self.cmd_sell))
        self.app.add_handler(CommandHandler("close", self.cmd_close))
        self.app.add_handler(CommandHandler("sl_tp", self.cmd_sl_tp))
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

    async def stop(self):
        if not self.enabled:
            return
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
