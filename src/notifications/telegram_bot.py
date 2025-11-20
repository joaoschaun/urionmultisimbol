"""
Telegram Notifier
Sends notifications and handles commands via Telegram
"""
import asyncio
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from deep_translator import GoogleTranslator


class TelegramNotifier:
    """Telegram Bot for notifications and commands"""
    
    def __init__(self, config: Dict[str, Any], mt5=None, stats_db=None):
        """
        Initialize Telegram Notifier
        
        Args:
            config: Configuration dictionary
            mt5: Optional MT5Connector instance for commands
            stats_db: Optional StrategyStatsDB instance for commands
        """
        self.config = config
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = config.get('notifications', {}).get('telegram', {}).get('enabled', True)
        self.app = None
        
        # 🆕 Referencias para comandos
        self.mt5 = mt5
        self.stats_db = stats_db
        self.bot_start_time = datetime.now(timezone.utc)
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not found, notifications disabled")
            self.enabled = False
        
        if self.enabled:
            self.app = Application.builder().token(self.bot_token).build()
            self._setup_handlers()
        
        # Tradutor (inglês → português)
        self.translator = GoogleTranslator(source='en', target='pt')
    
    def _translate_to_portuguese(self, text: str) -> str:
        """
        Traduz texto de inglês para português
        
        Args:
            text: Texto em inglês
            
        Returns:
            Texto traduzido em português
        """
        if not text:
            return text
        
        try:
            # Limitar tamanho (Google Translator tem limite de 5000 caracteres)
            if len(text) > 4500:
                text = text[:4500] + "..."
            
            translated = self.translator.translate(text)
            return translated
        except Exception as e:
            logger.warning(f"Falha na tradução, enviando texto original: {e}")
            return text
    
    def _setup_handlers(self):
        """Setup command handlers"""
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("stats", self.cmd_stats))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
    
    def send_message_sync(self, message: str, parse_mode: str = None):
        """
        Send message to Telegram (synchronous wrapper)
        
        Args:
            message: Message text
            parse_mode: Optional parse mode (Markdown, HTML)
        """
        if not self.enabled:
            return
        
        try:
            # Run async function in new event loop with timeout
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Set timeout to prevent hanging
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        self.send_message(message, parse_mode),
                        timeout=10.0  # 10 second timeout
                    )
                )
            except asyncio.TimeoutError:
                logger.warning("Telegram message send timeout (10s) - continuing execution")
            finally:
                loop.close()
                
        except Exception as e:
            # CRITICAL: Never let Telegram errors crash the bot
            logger.error(f"Telegram send failed (non-critical): {e}")
            # Continue execution - trading must not stop due to notifications
    
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
    
    def send_trade_notification(self, action: str, symbol: str, price: float,
                                volume: float, sl: float, tp: float,
                                strategy: str = None, confidence: float = None) -> bool:
        """
        Send trade notification (synchronous wrapper)
        
        Args:
            action: BUY or SELL
            symbol: Trading symbol
            price: Entry price
            volume: Position size
            sl: Stop loss
            tp: Take profit
            strategy: Strategy name
            confidence: Signal confidence
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            emoji = "🟢" if action == "BUY" else "🔴"
            
            message = (
                f"{emoji} <b>NOVA ORDEM - {action}</b>\n\n"
                f"Símbolo: {symbol}\n"
                f"Preço: {price:.2f}\n"
                f"Volume: {volume}\n"
                f"Stop Loss: {sl:.2f}\n"
                f"Take Profit: {tp:.2f}"
            )
            
            if strategy:
                message += f"\nEstratégia: {strategy}"
            
            if confidence:
                message += f"\nConfiança: {confidence:.1f}%"
            
            # Run async function with timeout protection
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        self.send_message(message, parse_mode='HTML'),
                        timeout=10.0
                    )
                )
            except asyncio.TimeoutError:
                logger.warning("Trade notification timeout - continuing")
                return False
            finally:
                loop.close()
            
            return True
            
        except Exception as e:
            # CRITICAL: Never crash bot due to notification failure
            logger.error(f"Trade notification failed (non-critical): {e}")
            return False
    
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
    
    def send_news_notification(self, news_title: str, news_content: str = None, 
                               source: str = None, importance: str = "medium") -> bool:
        """
        Envia notificação de notícia traduzida para português
        
        Args:
            news_title: Título da notícia (em inglês)
            news_content: Conteúdo/descrição da notícia (opcional, em inglês)
            source: Fonte da notícia (opcional)
            importance: Importância (low, medium, high)
            
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled:
            return False
        
        try:
            # Traduzir título
            title_pt = self._translate_to_portuguese(news_title)
            
            # Emoji baseado na importância
            emoji_map = {
                'low': '📰',
                'medium': '📢',
                'high': '🚨'
            }
            emoji = emoji_map.get(importance, '📰')
            
            # Montar mensagem
            message = f"{emoji} <b>NOTÍCIA - {importance.upper()}</b>\n\n"
            message += f"<b>{title_pt}</b>\n\n"
            
            # Traduzir e adicionar conteúdo se fornecido
            if news_content:
                content_pt = self._translate_to_portuguese(news_content)
                # Limitar tamanho do conteúdo
                if len(content_pt) > 300:
                    content_pt = content_pt[:297] + "..."
                message += f"{content_pt}\n\n"
            
            # Adicionar fonte
            if source:
                message += f"<i>Fonte: {source}</i>"
            
            # Enviar com timeout protection
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        self.send_message(message, parse_mode='HTML'),
                        timeout=15.0  # 15s timeout (tradução pode demorar)
                    )
                )
            except asyncio.TimeoutError:
                logger.warning("News notification timeout - continuing")
                return False
            finally:
                loop.close()
            
            logger.info(f"Notícia enviada (traduzida): {title_pt[:50]}...")
            return True
            
        except Exception as e:
            # CRITICAL: Never crash bot due to notification failure
            logger.error(f"News notification failed (non-critical): {e}")
            return False
    
    # Command handlers
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 Urion Trading Bot iniciado!\n"
            "Use /help para ver comandos disponíveis."
        )
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command - Graceful shutdown"""
        await update.message.reply_text(
            "⏹️ <b>PARANDO BOT</b>\n\n"
            "Fechando todas as posições abertas...\n"
            "Aguarde confirmação.",
            parse_mode='HTML'
        )
        
        try:
            if self.mt5:
                # Buscar posições abertas
                positions = self.mt5.get_open_positions()
                
                if positions:
                    await update.message.reply_text(
                        f"🔴 Fechando {len(positions)} posição(ões)..."
                    )
                    
                    closed = 0
                    for pos in positions:
                        if self.mt5.close_position(pos['ticket']):
                            closed += 1
                    
                    await update.message.reply_text(
                        f"✅ <b>{closed}/{len(positions)} posições fechadas</b>\n\n"
                        f"Bot será encerrado em 5 segundos...",
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text("✅ Nenhuma posição aberta")
                
                # Aguardar 5 segundos e enviar SIGTERM
                await asyncio.sleep(5)
                await update.message.reply_text("🛑 <b>BOT ENCERRADO</b>", parse_mode='HTML')
                
                # Encerrar processo
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                await update.message.reply_text(
                    "❌ MT5 não disponível. Reinicie o bot manualmente."
                )
        except Exception as e:
            logger.error(f"Erro no comando /stop: {e}")
            await update.message.reply_text(f"❌ Erro: {e}")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - Bot status"""
        try:
            # Calcular uptime
            uptime = datetime.now(timezone.utc) - self.bot_start_time
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            status_msg = f"<b>📊 STATUS DO BOT</b>\n\n"
            status_msg += f"🟢 <b>Operacional</b>\n"
            status_msg += f"⏱ Uptime: {hours}h {minutes}m\n\n"
            
            if self.mt5:
                # Status MT5
                if self.mt5.mt5.initialize():
                    account_info = self.mt5.mt5.account_info()
                    if account_info:
                        status_msg += f"💰 <b>Conta MT5</b>\n"
                        status_msg += f"Login: {account_info.login}\n"
                        status_msg += f"Server: {account_info.server}\n"
                        status_msg += f"Balance: ${account_info.balance:.2f}\n"
                        status_msg += f"Equity: ${account_info.equity:.2f}\n"
                        status_msg += f"Margin: ${account_info.margin:.2f}\n"
                        status_msg += f"Free Margin: ${account_info.margin_free:.2f}\n\n"
                    
                    # Posições abertas
                    positions = self.mt5.get_open_positions()
                    status_msg += f"📍 Posições: {len(positions)}\n"
                    
                    if positions:
                        total_profit = sum(p['profit'] for p in positions)
                        status_msg += f"💵 P/L Total: ${total_profit:.2f}\n"
                else:
                    status_msg += "❌ MT5 desconectado\n"
            
            if self.stats_db:
                # Estatísticas do dia
                from datetime import date
                today_trades = self.stats_db.get_trades_by_date(date.today())
                if today_trades:
                    wins = sum(1 for t in today_trades if t.get('profit', 0) > 0)
                    total_profit = sum(t.get('profit', 0) for t in today_trades)
                    status_msg += f"\n📈 <b>Hoje</b>\n"
                    status_msg += f"Trades: {len(today_trades)}\n"
                    status_msg += f"Wins: {wins}/{len(today_trades)}\n"
                    status_msg += f"P/L: ${total_profit:.2f}\n"
            
            await update.message.reply_text(status_msg, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Erro no comando /status: {e}")
            await update.message.reply_text(f"❌ Erro: {e}")
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command - Account balance"""
        try:
            if not self.mt5:
                await update.message.reply_text("❌ MT5 não disponível")
                return
            
            if self.mt5.mt5.initialize():
                account_info = self.mt5.mt5.account_info()
                if account_info:
                    balance_msg = f"<b>💰 SALDO DA CONTA</b>\n\n"
                    balance_msg += f"Balance: ${account_info.balance:.2f}\n"
                    balance_msg += f"Equity: ${account_info.equity:.2f}\n"
                    balance_msg += f"Margin: ${account_info.margin:.2f}\n"
                    balance_msg += f"Free Margin: ${account_info.margin_free:.2f}\n"
                    balance_msg += f"Margin Level: {account_info.margin_level:.2f}%\n\n"
                    
                    # P/L não realizado
                    positions = self.mt5.get_open_positions()
                    if positions:
                        unrealized_pl = sum(p['profit'] for p in positions)
                        balance_msg += f"P/L Aberto: ${unrealized_pl:.2f}\n"
                    
                    # P/L do dia
                    if self.stats_db:
                        from datetime import date
                        today_trades = self.stats_db.get_trades_by_date(date.today())
                        if today_trades:
                            today_pl = sum(t.get('profit', 0) for t in today_trades)
                            balance_msg += f"P/L Hoje: ${today_pl:.2f}\n"
                    
                    await update.message.reply_text(balance_msg, parse_mode='HTML')
                else:
                    await update.message.reply_text("❌ Erro ao obter info da conta")
            else:
                await update.message.reply_text("❌ MT5 desconectado")
                
        except Exception as e:
            logger.error(f"Erro no comando /balance: {e}")
            await update.message.reply_text(f"❌ Erro: {e}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command - List open positions"""
        try:
            if not self.mt5:
                await update.message.reply_text("❌ MT5 não disponível")
                return
            
            positions = self.mt5.get_open_positions()
            
            if not positions:
                await update.message.reply_text("✅ Nenhuma posição aberta")
                return
            
            pos_msg = f"<b>📍 POSIÇÕES ABERTAS ({len(positions)})</b>\n\n"
            
            for i, pos in enumerate(positions, 1):
                profit_emoji = "🟢" if pos['profit'] > 0 else "🔴"
                pos_msg += f"{i}. <b>{pos['symbol']}</b> {pos['type']}\n"
                pos_msg += f"   Ticket: {pos['ticket']}\n"
                pos_msg += f"   Volume: {pos['volume']}\n"
                pos_msg += f"   Preço: {pos['price_open']:.5f} → {pos['price_current']:.5f}\n"
                pos_msg += f"   {profit_emoji} P/L: ${pos['profit']:.2f}\n"
                
                if pos['sl'] > 0:
                    pos_msg += f"   SL: {pos['sl']:.5f}\n"
                if pos['tp'] > 0:
                    pos_msg += f"   TP: {pos['tp']:.5f}\n"
                pos_msg += "\n"
            
            # Total P/L
            total_pl = sum(p['profit'] for p in positions)
            total_emoji = "🟢" if total_pl > 0 else "🔴"
            pos_msg += f"{total_emoji} <b>Total P/L: ${total_pl:.2f}</b>"
            
            await update.message.reply_text(pos_msg, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Erro no comando /positions: {e}")
            await update.message.reply_text(f"❌ Erro: {e}")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - Trading statistics"""
        try:
            if not self.stats_db:
                await update.message.reply_text("❌ Database não disponível")
                return
            
            stats_msg = "<b>📈 ESTATÍSTICAS</b>\n\n"
            
            # Stats do dia
            from datetime import date, timedelta
            today = date.today()
            today_trades = self.stats_db.get_trades_by_date(today)
            
            if today_trades:
                wins = sum(1 for t in today_trades if t.get('profit', 0) > 0)
                losses = len(today_trades) - wins
                total_profit = sum(t.get('profit', 0) for t in today_trades)
                win_rate = (wins / len(today_trades)) * 100 if today_trades else 0
                
                stats_msg += f"<b>📅 HOJE</b>\n"
                stats_msg += f"Trades: {len(today_trades)}\n"
                stats_msg += f"Wins: {wins} | Losses: {losses}\n"
                stats_msg += f"Win Rate: {win_rate:.1f}%\n"
                stats_msg += f"P/L: ${total_profit:.2f}\n\n"
            else:
                stats_msg += "<b>📅 HOJE</b>\nNenhum trade ainda\n\n"
            
            # Stats da semana
            week_ago = today - timedelta(days=7)
            week_trades = []
            for i in range(8):
                day = week_ago + timedelta(days=i)
                week_trades.extend(self.stats_db.get_trades_by_date(day))
            
            if week_trades:
                wins = sum(1 for t in week_trades if t.get('profit', 0) > 0)
                losses = len(week_trades) - wins
                total_profit = sum(t.get('profit', 0) for t in week_trades)
                win_rate = (wins / len(week_trades)) * 100 if week_trades else 0
                
                stats_msg += f"<b>📊 ÚLTIMOS 7 DIAS</b>\n"
                stats_msg += f"Trades: {len(week_trades)}\n"
                stats_msg += f"Wins: {wins} | Losses: {losses}\n"
                stats_msg += f"Win Rate: {win_rate:.1f}%\n"
                stats_msg += f"P/L: ${total_profit:.2f}\n\n"
            
            # Top estratégia
            strategies = {}
            for trade in week_trades:
                strat = trade.get('strategy', 'Unknown')
                if strat not in strategies:
                    strategies[strat] = {'trades': 0, 'profit': 0}
                strategies[strat]['trades'] += 1
                strategies[strat]['profit'] += trade.get('profit', 0)
            
            if strategies:
                best_strat = max(strategies.items(), key=lambda x: x[1]['profit'])
                stats_msg += f"<b>🏆 MELHOR ESTRATÉGIA</b>\n"
                stats_msg += f"{best_strat[0]}\n"
                stats_msg += f"Trades: {best_strat[1]['trades']}\n"
                stats_msg += f"P/L: ${best_strat[1]['profit']:.2f}\n"
            
            await update.message.reply_text(stats_msg, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Erro no comando /stats: {e}")
            await update.message.reply_text(f"❌ Erro: {e}")
    
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
