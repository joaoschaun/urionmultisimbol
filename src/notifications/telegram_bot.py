"""
Telegram Notifier
Sends notifications and handles commands via Telegram
"""
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from typing import Dict, Any
from loguru import logger
import os


class TelegramNotifier:
    """Telegram Bot for notifications and commands"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Telegram Notifier
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = config.get('notifications', {}).get('telegram', {}).get('enabled', True)
        self.app = None
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not found, notifications disabled")
            self.enabled = False
        
        if self.enabled:
            self.app = Application.builder().token(self.bot_token).build()
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup command handlers"""
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
    
    async def send_message(self, message: str, parse_mode: str = None):
        """
        Send message to Telegram
        
        Args:
            message: Message text
            parse_mode: Optional parse mode (Markdown, HTML)
        """
        if not self.enabled:
            return
        
        try:
            async with self.app.bot as bot:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=parse_mode
                )
            logger.debug(f"Telegram message sent: {message[:50]}...")
        except Exception as e:
            logger.exception(f"Error sending Telegram message: {e}")
    
    async def send_trade_signal(self, signal: Dict):
        """
        Send trading signal notification
        
        Args:
            signal: Signal dictionary
        """
        if not self.config.get('notifications', {}).get('telegram', {}).get('send_trade_signals', True):
            return
        
        message = (
            f"📊 <b>SINAL DE TRADING</b>\n\n"
            f"Símbolo: {signal.get('symbol')}\n"
            f"Tipo: {signal.get('type')}\n"
            f"Força: {signal.get('strength', 0):.2f}\n"
            f"Preço: {signal.get('price', 0):.2f}\n"
            f"SL: {signal.get('sl', 0):.2f}\n"
            f"TP: {signal.get('tp', 0):.2f}\n"
            f"Razão: {signal.get('reason', 'N/A')}"
        )
        
        await self.send_message(message, parse_mode='HTML')
    
    async def send_trade_execution(self, trade: Dict):
        """
        Send trade execution notification
        
        Args:
            trade: Trade dictionary
        """
        if not self.config.get('notifications', {}).get('telegram', {}).get('send_trade_executions', True):
            return
        
        message = (
            f"✅ <b>ORDEM EXECUTADA</b>\n\n"
            f"Ticket: {trade.get('ticket')}\n"
            f"Símbolo: {trade.get('symbol')}\n"
            f"Tipo: {trade.get('type')}\n"
            f"Volume: {trade.get('volume')}\n"
            f"Preço: {trade.get('price', 0):.2f}\n"
            f"SL: {trade.get('sl', 0):.2f}\n"
            f"TP: {trade.get('tp', 0):.2f}"
        )
        
        await self.send_message(message, parse_mode='HTML')
    
    async def send_trade_closure(self, trade: Dict):
        """
        Send trade closure notification
        
        Args:
            trade: Trade dictionary with closure info
        """
        if not self.config.get('notifications', {}).get('telegram', {}).get('send_trade_closures', True):
            return
        
        profit = trade.get('profit', 0)
        emoji = "💚" if profit > 0 else "❌"
        
        message = (
            f"{emoji} <b>ORDEM FECHADA</b>\n\n"
            f"Ticket: {trade.get('ticket')}\n"
            f"Símbolo: {trade.get('symbol')}\n"
            f"Tipo: {trade.get('type')}\n"
            f"Lucro: ${profit:.2f}\n"
            f"Duração: {trade.get('duration', 'N/A')}"
        )
        
        await self.send_message(message, parse_mode='HTML')
    
    async def send_error(self, error: str):
        """
        Send error notification
        
        Args:
            error: Error message
        """
        if not self.config.get('notifications', {}).get('telegram', {}).get('send_errors', True):
            return
        
        message = f"❌ <b>ERRO</b>\n\n{error}"
        await self.send_message(message, parse_mode='HTML')
    
    # Command handlers
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 Urion Trading Bot iniciado!\n"
            "Use /help para ver comandos disponíveis."
        )
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        await update.message.reply_text("⏹️ Comando de parada recebido...")
        # TODO: Implement graceful shutdown
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        # TODO: Implement status check
        await update.message.reply_text("📊 Status: Operacional")
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        # TODO: Implement balance check
        await update.message.reply_text("💰 Consultando saldo...")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        # TODO: Implement position listing
        await update.message.reply_text("📍 Consultando posições...")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        # TODO: Implement statistics
        await update.message.reply_text("📈 Consultando estatísticas...")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "<b>Comandos disponíveis:</b>\n\n"
            "/start - Iniciar bot\n"
            "/stop - Parar bot\n"
            "/status - Ver status\n"
            "/balance - Ver saldo\n"
            "/positions - Ver posições abertas\n"
            "/stats - Ver estatísticas\n"
            "/help - Mostrar esta ajuda"
        )
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    async def start_polling(self):
        """Start Telegram bot polling"""
        if not self.enabled:
            return
        
        try:
            logger.info("Starting Telegram bot polling...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
        except Exception as e:
            logger.exception(f"Error starting Telegram polling: {e}")
    
    async def stop_polling(self):
        """Stop Telegram bot polling"""
        if not self.enabled:
            return
        
        try:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        except Exception as e:
            logger.exception(f"Error stopping Telegram polling: {e}")
