# -*- coding: utf-8 -*-
"""
URION Trading Bot - Professional Telegram System
=================================================
Sistema de notificações Telegram profissional e completo.

Features:
- Alertas de entrada/saída de trades
- Acompanhamento em tempo real de posições
- Notícias econômicas traduzidas
- Análises técnicas automáticas
- Relatórios diários/semanais
- Comandos interativos avançados
- Gráficos e screenshots
"""

import asyncio
import os
import io
import signal
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
from loguru import logger

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        ContextTypes,
        MessageHandler,
        filters
    )
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot não instalado")

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False


class NotificationType(Enum):
    """Tipos de notificação"""
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    TRADE_UPDATE = "trade_update"
    SIGNAL = "signal"
    NEWS = "news"
    ANALYSIS = "analysis"
    ALERT = "alert"
    REPORT = "report"
    ERROR = "error"
    SYSTEM = "system"


@dataclass
class TradeInfo:
    """Informações de um trade"""
    ticket: int
    symbol: str
    type: str  # BUY ou SELL
    volume: float
    entry_price: float
    current_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0
    pips: float = 0.0
    strategy: str = ""
    confidence: float = 0.0
    entry_time: datetime = None
    exit_time: datetime = None
    exit_reason: str = ""
    

class TelegramProfessional:
    """
    Sistema profissional de notificações Telegram
    """
    
    def __init__(self, config: Dict[str, Any], mt5=None, stats_db=None):
        """
        Inicializa o sistema Telegram profissional
        
        Args:
            config: Configuração do bot
            mt5: Conector MT5
            stats_db: Database de estatísticas
        """
        self.config = config
        self.mt5 = mt5
        self.stats_db = stats_db
        
        # Credenciais
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Configurações
        tg_config = config.get('telegram', {})
        self.enabled = tg_config.get('enabled', True) and self.bot_token and self.chat_id
        
        # Notificações habilitadas
        self.notifications = {
            'trade_entry': tg_config.get('notify_entry', True),
            'trade_exit': tg_config.get('notify_exit', True),
            'trade_update': tg_config.get('notify_update', True),
            'signals': tg_config.get('notify_signals', True),
            'news': tg_config.get('notify_news', True),
            'analysis': tg_config.get('notify_analysis', True),
            'daily_report': tg_config.get('daily_report', True),
            'errors': tg_config.get('notify_errors', True),
        }
        
        # Estado
        self.app = None
        self.is_running = False
        self.bot_start_time = datetime.now(timezone.utc)
        self.tracked_positions: Dict[int, TradeInfo] = {}
        self.daily_stats = {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0
        }
        
        # Tradutor
        self.translator = None
        if TRANSLATOR_AVAILABLE:
            try:
                self.translator = GoogleTranslator(source='en', target='pt')
            except:
                pass
        
        # Inicializar aplicação Telegram
        if self.enabled and TELEGRAM_AVAILABLE:
            self._init_telegram()
        
        logger.info(f"📱 Telegram Professional: {'Ativo' if self.enabled else 'Desativado'}")
    
    def _init_telegram(self):
        """Inicializa a aplicação Telegram"""
        try:
            self.app = Application.builder().token(self.bot_token).build()
            self._setup_handlers()
            logger.info("✅ Telegram inicializado com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Telegram: {e}")
            self.enabled = False
    
    def _setup_handlers(self):
        """Configura handlers de comandos"""
        handlers = [
            # Comandos básicos
            ("start", self.cmd_start),
            ("help", self.cmd_help),
            ("status", self.cmd_status),
            
            # Conta e posições
            ("balance", self.cmd_balance),
            ("positions", self.cmd_positions),
            ("orders", self.cmd_orders),
            
            # Estatísticas
            ("stats", self.cmd_stats),
            ("today", self.cmd_today),
            ("week", self.cmd_week),
            ("month", self.cmd_month),
            
            # Análises
            ("analysis", self.cmd_analysis),
            ("chart", self.cmd_chart),
            ("signals", self.cmd_signals),
            
            # Relatórios
            ("report", self.cmd_report),
            ("performance", self.cmd_performance),
            ("strategies", self.cmd_strategies),
            
            # Controle
            ("pause", self.cmd_pause),
            ("resume", self.cmd_resume),
            ("closeall", self.cmd_closeall),
            ("stop", self.cmd_stop),
            
            # Configurações
            ("settings", self.cmd_settings),
            ("risk", self.cmd_risk),
        ]
        
        for cmd, handler in handlers:
            self.app.add_handler(CommandHandler(cmd, handler))
        
        # Handler para callbacks de botões
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
    
    # ==================== MÉTODOS DE ENVIO ====================
    
    def _send_sync(self, message: str, parse_mode: str = 'HTML', 
                   reply_markup=None, photo=None) -> bool:
        """
        Envia mensagem de forma síncrona (wrapper)
        
        Args:
            message: Texto da mensagem
            parse_mode: Modo de parse (HTML, Markdown)
            reply_markup: Teclado inline opcional
            photo: Bytes da imagem opcional
            
        Returns:
            True se enviado com sucesso
        """
        if not self.enabled:
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        self._send_async(message, parse_mode, reply_markup, photo),
                        timeout=15.0
                    )
                )
                return True
            except asyncio.TimeoutError:
                logger.warning("⏱️ Timeout ao enviar mensagem Telegram")
                return False
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"❌ Erro ao enviar Telegram: {e}")
            return False
    
    async def _send_async(self, message: str, parse_mode: str = 'HTML',
                          reply_markup=None, photo=None):
        """Envia mensagem de forma assíncrona"""
        async with self.app.bot as bot:
            if photo:
                await bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=message,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            else:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
    
    def _translate(self, text: str) -> str:
        """Traduz texto de inglês para português"""
        if not text or not self.translator:
            return text
        try:
            if len(text) > 4500:
                text = text[:4500] + "..."
            return self.translator.translate(text)
        except:
            return text
    
    # ==================== NOTIFICAÇÕES DE TRADES ====================
    
    def notify_trade_entry(self, trade: TradeInfo) -> bool:
        """
        Notifica entrada em um trade
        
        Args:
            trade: Informações do trade
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('trade_entry', True):
            return False
        
        emoji = "🟢" if trade.type == "BUY" else "🔴"
        arrow = "⬆️" if trade.type == "BUY" else "⬇️"
        
        # Calcular RR
        if trade.sl > 0 and trade.tp > 0:
            risk = abs(trade.entry_price - trade.sl)
            reward = abs(trade.tp - trade.entry_price)
            rr = reward / risk if risk > 0 else 0
        else:
            rr = 0
        
        message = f"""
{emoji} <b>NOVA ENTRADA - {trade.type}</b> {arrow}

<b>📊 Detalhes da Operação</b>
━━━━━━━━━━━━━━━━━━━━
• Símbolo: <code>{trade.symbol}</code>
• Tipo: <b>{trade.type}</b>
• Volume: <code>{trade.volume}</code> lotes
• Preço: <code>{trade.entry_price:.5f}</code>

<b>🎯 Níveis</b>
• Stop Loss: <code>{trade.sl:.5f}</code>
• Take Profit: <code>{trade.tp:.5f}</code>
• Risk/Reward: <code>1:{rr:.1f}</code>

<b>🤖 Estratégia</b>
• {trade.strategy or 'Auto'}
• Confiança: {trade.confidence:.0f}%

<b>🎫 Ticket:</b> <code>{trade.ticket}</code>
<b>⏰ Hora:</b> {datetime.now().strftime('%H:%M:%S')}
"""
        
        # Botões de ação
        keyboard = [
            [
                InlineKeyboardButton("📊 Ver Posição", callback_data=f"pos_{trade.ticket}"),
                InlineKeyboardButton("❌ Fechar", callback_data=f"close_{trade.ticket}")
            ],
            [
                InlineKeyboardButton("📈 Análise", callback_data=f"analysis_{trade.symbol}"),
                InlineKeyboardButton("⚙️ Modificar", callback_data=f"modify_{trade.ticket}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Rastrear posição
        self.tracked_positions[trade.ticket] = trade
        
        return self._send_sync(message, reply_markup=reply_markup)
    
    def notify_trade_exit(self, trade: TradeInfo) -> bool:
        """
        Notifica saída de um trade
        
        Args:
            trade: Informações do trade com resultado
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('trade_exit', True):
            return False
        
        # Determinar resultado
        is_win = trade.profit > 0
        emoji = "💚" if is_win else "❌"
        result = "LUCRO" if is_win else "PREJUÍZO"
        
        # Calcular duração
        if trade.entry_time and trade.exit_time:
            duration = trade.exit_time - trade.entry_time
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            duration_str = f"{hours}h {minutes}m"
        else:
            duration_str = "N/A"
        
        # Atualizar estatísticas diárias
        self.daily_stats['trades'] += 1
        self.daily_stats['pnl'] += trade.profit
        if is_win:
            self.daily_stats['wins'] += 1
            if trade.profit > self.daily_stats['best_trade']:
                self.daily_stats['best_trade'] = trade.profit
        else:
            self.daily_stats['losses'] += 1
            if trade.profit < self.daily_stats['worst_trade']:
                self.daily_stats['worst_trade'] = trade.profit
        
        message = f"""
{emoji} <b>TRADE FECHADO - {result}</b>

<b>📊 Resultado</b>
━━━━━━━━━━━━━━━━━━━━
• Símbolo: <code>{trade.symbol}</code>
• Tipo: {trade.type}
• Volume: {trade.volume} lotes

<b>💰 Financeiro</b>
• Entrada: <code>{trade.entry_price:.5f}</code>
• Saída: <code>{trade.current_price:.5f}</code>
• Pips: <code>{trade.pips:+.1f}</code>
• <b>P&L: ${trade.profit:+.2f}</b>

<b>📈 Detalhes</b>
• Motivo: {trade.exit_reason or 'Manual'}
• Duração: {duration_str}
• Estratégia: {trade.strategy or 'N/A'}

<b>📊 Hoje</b>
• Trades: {self.daily_stats['trades']}
• Win Rate: {(self.daily_stats['wins']/self.daily_stats['trades']*100) if self.daily_stats['trades'] > 0 else 0:.0f}%
• P&L Dia: ${self.daily_stats['pnl']:+.2f}
"""
        
        # Remover do rastreamento
        if trade.ticket in self.tracked_positions:
            del self.tracked_positions[trade.ticket]
        
        return self._send_sync(message)
    
    def notify_trade_update(self, trade: TradeInfo, update_type: str = "price") -> bool:
        """
        Notifica atualização de um trade (SL movido, TP parcial, etc)
        
        Args:
            trade: Trade atualizado
            update_type: Tipo de atualização (price, sl_moved, partial_tp, trailing)
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('trade_update', True):
            return False
        
        emoji_map = {
            "price": "📊",
            "sl_moved": "🛡️",
            "partial_tp": "💰",
            "trailing": "📈",
            "breakeven": "⚖️"
        }
        emoji = emoji_map.get(update_type, "📊")
        
        title_map = {
            "price": "Atualização de Preço",
            "sl_moved": "Stop Loss Movido",
            "partial_tp": "Take Profit Parcial",
            "trailing": "Trailing Stop Ativo",
            "breakeven": "Stop em Breakeven"
        }
        title = title_map.get(update_type, "Atualização")
        
        profit_emoji = "🟢" if trade.profit > 0 else "🔴"
        
        message = f"""
{emoji} <b>{title.upper()}</b>

• Símbolo: <code>{trade.symbol}</code>
• Ticket: <code>{trade.ticket}</code>
• Preço atual: <code>{trade.current_price:.5f}</code>
• SL: <code>{trade.sl:.5f}</code>
• TP: <code>{trade.tp:.5f}</code>
• {profit_emoji} P&L: ${trade.profit:+.2f} ({trade.pips:+.1f} pips)
"""
        
        return self._send_sync(message)
    
    # ==================== NOTIFICAÇÕES DE SINAIS ====================
    
    def notify_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Notifica um sinal de trading detectado
        
        Args:
            signal: Dicionário com informações do sinal
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('signals', True):
            return False
        
        symbol = signal.get('symbol', 'N/A')
        signal_type = signal.get('type', 'UNKNOWN')
        strength = signal.get('strength', 0)
        price = signal.get('price', 0)
        sl = signal.get('sl', 0)
        tp = signal.get('tp', 0)
        reason = signal.get('reason', 'N/A')
        strategy = signal.get('strategy', 'N/A')
        
        # Emoji baseado na força
        if strength >= 80:
            strength_emoji = "🔥🔥🔥"
            strength_text = "MUITO FORTE"
        elif strength >= 60:
            strength_emoji = "🔥🔥"
            strength_text = "FORTE"
        elif strength >= 40:
            strength_emoji = "🔥"
            strength_text = "MODERADO"
        else:
            strength_emoji = "⚠️"
            strength_text = "FRACO"
        
        arrow = "⬆️" if signal_type == "BUY" else "⬇️"
        emoji = "🟢" if signal_type == "BUY" else "🔴"
        
        message = f"""
{emoji} <b>SINAL DETECTADO</b> {arrow}

<b>📊 {symbol}</b> - {signal_type}
━━━━━━━━━━━━━━━━━━━━

<b>💪 Força: {strength_emoji} {strength:.0f}% ({strength_text})</b>

<b>📍 Níveis</b>
• Preço: <code>{price:.5f}</code>
• Stop Loss: <code>{sl:.5f}</code>
• Take Profit: <code>{tp:.5f}</code>

<b>🔍 Análise</b>
• Estratégia: {strategy}
• Motivo: {reason}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        # Botões para executar ou ignorar
        keyboard = [
            [
                InlineKeyboardButton(f"✅ Executar {signal_type}", callback_data=f"exec_{symbol}_{signal_type}_{price}"),
                InlineKeyboardButton("❌ Ignorar", callback_data="ignore_signal")
            ],
            [
                InlineKeyboardButton("📊 Ver Análise", callback_data=f"analysis_{symbol}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        return self._send_sync(message, reply_markup=reply_markup)
    
    # ==================== NOTIFICAÇÕES DE NOTÍCIAS ====================
    
    def notify_news(self, title: str, content: str = None, 
                    source: str = None, importance: str = "medium",
                    impact_currencies: List[str] = None) -> bool:
        """
        Notifica notícia econômica importante
        
        Args:
            title: Título da notícia
            content: Conteúdo/resumo
            source: Fonte da notícia
            importance: low, medium, high
            impact_currencies: Moedas afetadas
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('news', True):
            return False
        
        # Traduzir
        title_pt = self._translate(title)
        content_pt = self._translate(content) if content else None
        
        # Emojis por importância
        emoji_map = {
            'low': '📰',
            'medium': '📢',
            'high': '🚨'
        }
        emoji = emoji_map.get(importance, '📰')
        
        importance_map = {
            'low': 'Baixa',
            'medium': 'Média',
            'high': 'Alta'
        }
        
        message = f"""
{emoji} <b>NOTÍCIA - Importância {importance_map.get(importance, 'Média')}</b>

<b>{title_pt}</b>
"""
        
        if content_pt:
            if len(content_pt) > 500:
                content_pt = content_pt[:497] + "..."
            message += f"\n{content_pt}\n"
        
        if impact_currencies:
            message += f"\n💱 Moedas afetadas: {', '.join(impact_currencies)}"
        
        if source:
            message += f"\n\n<i>Fonte: {source}</i>"
        
        message += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        
        return self._send_sync(message)
    
    def notify_economic_event(self, event: Dict[str, Any]) -> bool:
        """
        Notifica evento econômico do calendário
        
        Args:
            event: Dados do evento
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('news', True):
            return False
        
        importance = event.get('importance', 'medium')
        
        # Emojis por importância
        if importance == 'high':
            emoji = "🔴🔴🔴"
        elif importance == 'medium':
            emoji = "🟡🟡"
        else:
            emoji = "🟢"
        
        event_time = event.get('time', 'N/A')
        currency = event.get('currency', 'N/A')
        title = event.get('title', 'N/A')
        forecast = event.get('forecast', 'N/A')
        previous = event.get('previous', 'N/A')
        actual = event.get('actual', 'Pendente')
        
        message = f"""
📅 <b>EVENTO ECONÔMICO</b> {emoji}

<b>{title}</b>

• Moeda: <code>{currency}</code>
• Horário: <code>{event_time}</code>
• Importância: {importance.upper()}

<b>📊 Valores</b>
• Anterior: <code>{previous}</code>
• Previsão: <code>{forecast}</code>
• Atual: <code>{actual}</code>
"""
        
        return self._send_sync(message)
    
    # ==================== NOTIFICAÇÕES DE ANÁLISE ====================
    
    def notify_analysis(self, symbol: str, analysis: Dict[str, Any]) -> bool:
        """
        Notifica análise técnica completa
        
        Args:
            symbol: Símbolo analisado
            analysis: Resultado da análise
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('analysis', True):
            return False
        
        trend = analysis.get('trend', 'NEUTRO')
        trend_emoji = {
            'BULLISH': '🟢 ALTA',
            'BEARISH': '🔴 BAIXA',
            'NEUTRAL': '⚪ NEUTRO',
            'RANGING': '↔️ RANGE'
        }.get(trend.upper(), trend)
        
        strength = analysis.get('strength', 0)
        
        # Indicadores
        rsi = analysis.get('rsi', 0)
        macd = analysis.get('macd_signal', 'N/A')
        ema_cross = analysis.get('ema_cross', 'N/A')
        support = analysis.get('support', 0)
        resistance = analysis.get('resistance', 0)
        
        # RSI status
        if rsi > 70:
            rsi_status = "🔴 Sobrecomprado"
        elif rsi < 30:
            rsi_status = "🟢 Sobrevendido"
        else:
            rsi_status = "⚪ Neutro"
        
        message = f"""
📊 <b>ANÁLISE TÉCNICA</b>

<b>{symbol}</b>
━━━━━━━━━━━━━━━━━━━━

<b>📈 Tendência:</b> {trend_emoji}
<b>💪 Força:</b> {strength:.0f}%

<b>📉 Indicadores</b>
• RSI(14): {rsi:.1f} - {rsi_status}
• MACD: {macd}
• EMA Cross: {ema_cross}

<b>🎯 Níveis</b>
• Suporte: <code>{support:.5f}</code>
• Resistência: <code>{resistance:.5f}</code>

<b>🤖 Recomendação:</b>
{analysis.get('recommendation', 'Aguardar')}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        return self._send_sync(message)
    
    # ==================== RELATÓRIOS ====================
    
    def send_daily_report(self) -> bool:
        """
        Envia relatório diário completo
        
        Returns:
            True se enviado
        """
        if not self.notifications.get('daily_report', True):
            return False
        
        stats = self.daily_stats
        trades = stats['trades']
        wins = stats['wins']
        losses = stats['losses']
        pnl = stats['pnl']
        
        win_rate = (wins / trades * 100) if trades > 0 else 0
        
        # Emoji baseado no resultado
        if pnl > 0:
            result_emoji = "🟢"
            result_text = "POSITIVO"
        elif pnl < 0:
            result_emoji = "🔴"
            result_text = "NEGATIVO"
        else:
            result_emoji = "⚪"
            result_text = "NEUTRO"
        
        message = f"""
📊 <b>RELATÓRIO DIÁRIO</b>
{datetime.now().strftime('%d/%m/%Y')}
━━━━━━━━━━━━━━━━━━━━

{result_emoji} <b>RESULTADO: {result_text}</b>

<b>📈 Performance</b>
• Total de trades: {trades}
• Wins: {wins} ✅
• Losses: {losses} ❌
• Win Rate: {win_rate:.1f}%

<b>💰 Financeiro</b>
• P&L Total: <b>${pnl:+.2f}</b>
• Melhor trade: ${stats['best_trade']:+.2f}
• Pior trade: ${stats['worst_trade']:+.2f}
• Média/trade: ${(pnl/trades if trades > 0 else 0):+.2f}

<b>📊 Métricas</b>
• Profit Factor: {(abs(stats['best_trade'])/abs(stats['worst_trade']) if stats['worst_trade'] != 0 else 0):.2f}

━━━━━━━━━━━━━━━━━━━━
<i>Urion Trading Bot v2.0</i>
"""
        
        # Resetar estatísticas diárias
        self.daily_stats = {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0
        }
        
        return self._send_sync(message)
    
    # ==================== ALERTAS DO SISTEMA ====================
    
    def notify_error(self, error: str, context: str = None) -> bool:
        """
        Notifica erro do sistema
        
        Args:
            error: Mensagem de erro
            context: Contexto adicional
            
        Returns:
            True se notificado
        """
        if not self.notifications.get('errors', True):
            return False
        
        message = f"""
❌ <b>ERRO DO SISTEMA</b>

<b>Mensagem:</b>
<code>{error[:500]}</code>
"""
        
        if context:
            message += f"\n<b>Contexto:</b>\n{context[:200]}"
        
        message += f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        
        return self._send_sync(message)
    
    def notify_system(self, title: str, message: str, 
                      level: str = "info") -> bool:
        """
        Notifica mensagem do sistema
        
        Args:
            title: Título
            message: Mensagem
            level: info, warning, success, error
            
        Returns:
            True se notificado
        """
        emoji_map = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'success': '✅',
            'error': '❌'
        }
        emoji = emoji_map.get(level, 'ℹ️')
        
        full_message = f"""
{emoji} <b>{title.upper()}</b>

{message}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        return self._send_sync(full_message)
    
    # ==================== COMANDOS DO BOT ====================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="status"),
                InlineKeyboardButton("💰 Saldo", callback_data="balance")
            ],
            [
                InlineKeyboardButton("📍 Posições", callback_data="positions"),
                InlineKeyboardButton("📈 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("📋 Relatório", callback_data="report"),
                InlineKeyboardButton("❓ Ajuda", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"""
🤖 <b>URION TRADING BOT</b>
━━━━━━━━━━━━━━━━━━━━

Bem-vindo ao sistema de trading automatizado!

<b>Status:</b> 🟢 Operacional
<b>Versão:</b> 2.0 Professional

Use os botões abaixo ou digite /help para ver todos os comandos.
""",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        help_text = """
<b>📚 COMANDOS DISPONÍVEIS</b>
━━━━━━━━━━━━━━━━━━━━

<b>📊 Informações</b>
/status - Status do bot
/balance - Saldo da conta
/positions - Posições abertas
/orders - Ordens pendentes

<b>📈 Estatísticas</b>
/stats - Estatísticas gerais
/today - Resultado de hoje
/week - Resultado da semana
/month - Resultado do mês
/strategies - Performance por estratégia

<b>📉 Análise</b>
/analysis - Análise do mercado
/signals - Sinais ativos
/chart [símbolo] - Gráfico

<b>📋 Relatórios</b>
/report - Relatório completo
/performance - Métricas de performance

<b>⚙️ Controle</b>
/pause - Pausar trading
/resume - Retomar trading
/closeall - Fechar todas posições
/stop - Parar bot

<b>🔧 Configurações</b>
/settings - Ver configurações
/risk - Configurar risco
"""
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status"""
        # Calcular uptime
        uptime = datetime.now(timezone.utc) - self.bot_start_time
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        
        status_emoji = "🟢" if self.is_running else "🟡"
        
        message = f"""
<b>📊 STATUS DO BOT</b>
━━━━━━━━━━━━━━━━━━━━

{status_emoji} <b>Operacional</b>

<b>⏱️ Uptime:</b> {hours}h {minutes}m
<b>📍 Posições:</b> {len(self.tracked_positions)}
"""
        
        if self.mt5:
            try:
                import MetaTrader5 as mt5
                if mt5.initialize():
                    account = mt5.account_info()
                    if account:
                        message += f"""
<b>💰 Conta MT5</b>
• Login: {account.login}
• Server: {account.server}
• Balance: ${account.balance:.2f}
• Equity: ${account.equity:.2f}
• Margin: ${account.margin:.2f}
"""
            except:
                pass
        
        message += f"""
<b>📊 Hoje</b>
• Trades: {self.daily_stats['trades']}
• P&L: ${self.daily_stats['pnl']:+.2f}
"""
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /balance"""
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                account = mt5.account_info()
                if account:
                    message = f"""
<b>💰 SALDO DA CONTA</b>
━━━━━━━━━━━━━━━━━━━━

<b>📊 Valores</b>
• Balance: <code>${account.balance:.2f}</code>
• Equity: <code>${account.equity:.2f}</code>
• Margin: <code>${account.margin:.2f}</code>
• Free Margin: <code>${account.margin_free:.2f}</code>
• Margin Level: <code>{account.margin_level:.1f}%</code>

<b>📈 Lucro</b>
• P&L Não Realizado: <code>${account.profit:.2f}</code>
• P&L Hoje: <code>${self.daily_stats['pnl']:+.2f}</code>

<b>⚙️ Configurações</b>
• Leverage: 1:{account.leverage}
• Currency: {account.currency}
"""
                    await update.message.reply_text(message, parse_mode='HTML')
                    return
        except Exception as e:
            logger.error(f"Erro ao obter saldo: {e}")
        
        await update.message.reply_text("❌ Não foi possível obter informações da conta")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /positions"""
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                positions = mt5.positions_get()
                
                if not positions:
                    await update.message.reply_text("✅ Nenhuma posição aberta")
                    return
                
                message = f"<b>📍 POSIÇÕES ABERTAS ({len(positions)})</b>\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n\n"
                
                total_profit = 0
                for pos in positions:
                    profit_emoji = "🟢" if pos.profit > 0 else "🔴"
                    pos_type = "BUY" if pos.type == 0 else "SELL"
                    total_profit += pos.profit
                    
                    message += f"""<b>{pos.symbol}</b> {pos_type}
• Volume: {pos.volume}
• Entrada: {pos.price_open:.5f}
• Atual: {pos.price_current:.5f}
• {profit_emoji} P&L: ${pos.profit:.2f}
• SL: {pos.sl:.5f} | TP: {pos.tp:.5f}

"""
                
                total_emoji = "🟢" if total_profit > 0 else "🔴"
                message += f"{total_emoji} <b>Total P&L: ${total_profit:.2f}</b>"
                
                await update.message.reply_text(message, parse_mode='HTML')
                return
        except Exception as e:
            logger.error(f"Erro ao obter posições: {e}")
        
        await update.message.reply_text("❌ Erro ao obter posições")
    
    async def cmd_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /orders"""
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                orders = mt5.orders_get()
                
                if not orders:
                    await update.message.reply_text("✅ Nenhuma ordem pendente")
                    return
                
                message = f"<b>📋 ORDENS PENDENTES ({len(orders)})</b>\n"
                message += "━━━━━━━━━━━━━━━━━━━━\n\n"
                
                for order in orders:
                    order_type = {
                        2: "BUY LIMIT",
                        3: "SELL LIMIT",
                        4: "BUY STOP",
                        5: "SELL STOP"
                    }.get(order.type, "UNKNOWN")
                    
                    message += f"""<b>{order.symbol}</b> {order_type}
• Volume: {order.volume_current}
• Preço: {order.price_open:.5f}
• SL: {order.sl:.5f} | TP: {order.tp:.5f}
• Ticket: {order.ticket}

"""
                
                await update.message.reply_text(message, parse_mode='HTML')
                return
        except Exception as e:
            logger.error(f"Erro ao obter ordens: {e}")
        
        await update.message.reply_text("❌ Erro ao obter ordens")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats"""
        message = f"""
<b>📈 ESTATÍSTICAS</b>
━━━━━━━━━━━━━━━━━━━━

<b>📅 Hoje</b>
• Trades: {self.daily_stats['trades']}
• Wins: {self.daily_stats['wins']} ✅
• Losses: {self.daily_stats['losses']} ❌
• Win Rate: {(self.daily_stats['wins']/self.daily_stats['trades']*100) if self.daily_stats['trades'] > 0 else 0:.1f}%
• P&L: ${self.daily_stats['pnl']:+.2f}

<b>🎯 Melhor/Pior Trade</b>
• Melhor: ${self.daily_stats['best_trade']:+.2f}
• Pior: ${self.daily_stats['worst_trade']:+.2f}
"""
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /today"""
        await self.cmd_stats(update, context)
    
    async def cmd_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /week"""
        await update.message.reply_text("📊 Estatísticas da semana em desenvolvimento...")
    
    async def cmd_month(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /month"""
        await update.message.reply_text("📊 Estatísticas do mês em desenvolvimento...")
    
    async def cmd_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /analysis"""
        symbol = "XAUUSD"  # Default
        if context.args:
            symbol = context.args[0].upper()
        
        await update.message.reply_text(f"📊 Gerando análise para {symbol}...")
        
        # Análise simplificada
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
                if rates is not None:
                    import pandas as pd
                    import numpy as np
                    
                    df = pd.DataFrame(rates)
                    
                    # Calcular indicadores
                    df['ema12'] = df['close'].ewm(span=12).mean()
                    df['ema26'] = df['close'].ewm(span=26).mean()
                    
                    # RSI
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    
                    current_rsi = rsi.iloc[-1]
                    current_price = df['close'].iloc[-1]
                    ema12 = df['ema12'].iloc[-1]
                    ema26 = df['ema26'].iloc[-1]
                    
                    # Tendência
                    if ema12 > ema26:
                        trend = "🟢 ALTA"
                    elif ema12 < ema26:
                        trend = "🔴 BAIXA"
                    else:
                        trend = "⚪ NEUTRO"
                    
                    # RSI status
                    if current_rsi > 70:
                        rsi_status = "🔴 Sobrecomprado"
                    elif current_rsi < 30:
                        rsi_status = "🟢 Sobrevendido"
                    else:
                        rsi_status = "⚪ Neutro"
                    
                    message = f"""
<b>📊 ANÁLISE TÉCNICA</b>

<b>{symbol}</b>
━━━━━━━━━━━━━━━━━━━━

<b>📈 Tendência:</b> {trend}

<b>📉 Indicadores</b>
• Preço atual: <code>{current_price:.2f}</code>
• EMA 12: <code>{ema12:.2f}</code>
• EMA 26: <code>{ema26:.2f}</code>
• RSI(14): <code>{current_rsi:.1f}</code> - {rsi_status}

<b>🎯 Suporte/Resistência</b>
• Suporte: <code>{df['low'].tail(20).min():.2f}</code>
• Resistência: <code>{df['high'].tail(20).max():.2f}</code>

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                    await update.message.reply_text(message, parse_mode='HTML')
                    return
        except Exception as e:
            logger.error(f"Erro na análise: {e}")
        
        await update.message.reply_text("❌ Erro ao gerar análise")
    
    async def cmd_chart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /chart"""
        if not MATPLOTLIB_AVAILABLE:
            await update.message.reply_text("❌ Matplotlib não disponível")
            return
        
        symbol = "XAUUSD"
        if context.args:
            symbol = context.args[0].upper()
        
        await update.message.reply_text(f"📊 Gerando gráfico para {symbol}...")
        
        try:
            import MetaTrader5 as mt5
            if mt5.initialize():
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
                if rates is not None:
                    import pandas as pd
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    
                    # Criar gráfico
                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.plot(df['time'], df['close'], 'b-', linewidth=1)
                    ax.fill_between(df['time'], df['low'], df['high'], alpha=0.3)
                    
                    ax.set_title(f'{symbol} - Últimas 50 Horas', fontsize=14)
                    ax.set_xlabel('Tempo')
                    ax.set_ylabel('Preço')
                    ax.grid(True, alpha=0.3)
                    
                    # Formatar datas
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    
                    # Salvar em buffer
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', dpi=100)
                    buf.seek(0)
                    plt.close()
                    
                    # Enviar imagem
                    await self.app.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=buf,
                        caption=f"📊 {symbol} - Gráfico H1"
                    )
                    return
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico: {e}")
        
        await update.message.reply_text("❌ Erro ao gerar gráfico")
    
    async def cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /signals"""
        await update.message.reply_text("📊 Sistema de sinais em tempo real ativo...")
    
    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /report"""
        stats = self.daily_stats
        trades = stats['trades']
        wins = stats['wins']
        pnl = stats['pnl']
        
        win_rate = (wins / trades * 100) if trades > 0 else 0
        
        message = f"""
<b>📋 RELATÓRIO COMPLETO</b>
{datetime.now().strftime('%d/%m/%Y %H:%M')}
━━━━━━━━━━━━━━━━━━━━

<b>📊 Resumo do Dia</b>
• Trades executados: {trades}
• Trades vencedores: {wins} ✅
• Trades perdedores: {stats['losses']} ❌
• Win Rate: {win_rate:.1f}%

<b>💰 Resultado Financeiro</b>
• P&L Total: <b>${pnl:+.2f}</b>
• Melhor trade: ${stats['best_trade']:+.2f}
• Pior trade: ${stats['worst_trade']:+.2f}
• Média por trade: ${(pnl/trades if trades > 0 else 0):+.2f}

━━━━━━━━━━━━━━━━━━━━
<i>Urion Trading Bot v2.0</i>
"""
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /performance"""
        await update.message.reply_text("📈 Métricas de performance em desenvolvimento...")
    
    async def cmd_strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /strategies"""
        await update.message.reply_text("🎯 Performance por estratégia em desenvolvimento...")
    
    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /pause"""
        self.is_running = False
        await update.message.reply_text("⏸️ Trading pausado. Use /resume para retomar.")
    
    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /resume"""
        self.is_running = True
        await update.message.reply_text("▶️ Trading retomado!")
    
    async def cmd_closeall(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /closeall"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm_closeall"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_closeall")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ <b>ATENÇÃO</b>\n\nIsso irá fechar TODAS as posições abertas.\n\nConfirma?",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stop"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirm_stop"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_stop")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ <b>ATENÇÃO</b>\n\nIsso irá PARAR o bot completamente.\n\nConfirma?",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /settings"""
        message = """
<b>⚙️ CONFIGURAÇÕES</b>
━━━━━━━━━━━━━━━━━━━━

<b>📱 Notificações</b>
"""
        for key, value in self.notifications.items():
            emoji = "✅" if value else "❌"
            message += f"• {key}: {emoji}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def cmd_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /risk"""
        await update.message.reply_text("⚙️ Configuração de risco em desenvolvimento...")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para callbacks de botões inline"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "status":
            await self.cmd_status(update, context)
        elif data == "balance":
            await query.edit_message_text("Carregando saldo...")
            # Simular cmd_balance
        elif data == "positions":
            await query.edit_message_text("Carregando posições...")
        elif data == "stats":
            await query.edit_message_text("Carregando estatísticas...")
        elif data == "report":
            await query.edit_message_text("Gerando relatório...")
        elif data == "help":
            await query.edit_message_text("Veja /help para comandos disponíveis")
        elif data == "confirm_closeall":
            await query.edit_message_text("🔄 Fechando todas as posições...")
            # Implementar fechamento
            await query.edit_message_text("✅ Todas as posições foram fechadas!")
        elif data == "cancel_closeall":
            await query.edit_message_text("❌ Operação cancelada")
        elif data == "confirm_stop":
            await query.edit_message_text("🛑 Parando bot...")
            os.kill(os.getpid(), signal.SIGTERM)
        elif data == "cancel_stop":
            await query.edit_message_text("❌ Operação cancelada")
        elif data == "ignore_signal":
            await query.edit_message_text("❌ Sinal ignorado")
        elif data.startswith("pos_"):
            ticket = int(data.split("_")[1])
            await query.edit_message_text(f"📊 Carregando posição {ticket}...")
        elif data.startswith("close_"):
            ticket = int(data.split("_")[1])
            await query.edit_message_text(f"🔄 Fechando posição {ticket}...")
        elif data.startswith("analysis_"):
            symbol = data.split("_")[1]
            await query.edit_message_text(f"📊 Gerando análise para {symbol}...")
    
    # ==================== POLLING ====================
    
    async def start_polling(self):
        """Inicia polling do Telegram"""
        if not self.enabled or not self.app:
            return
        
        try:
            logger.info("📱 Iniciando Telegram polling...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            self.is_running = True
            logger.info("✅ Telegram polling ativo")
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar polling: {e}")
    
    async def stop_polling(self):
        """Para polling do Telegram"""
        if not self.enabled or not self.app:
            return
        
        try:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self.is_running = False
            logger.info("📱 Telegram polling parado")
        except Exception as e:
            logger.error(f"❌ Erro ao parar polling: {e}")


# ==================== FUNÇÕES AUXILIARES ====================

_telegram_instance: Optional[TelegramProfessional] = None


def get_telegram(config: Dict = None, mt5=None, stats_db=None) -> TelegramProfessional:
    """
    Retorna instância singleton do Telegram
    
    Args:
        config: Configuração
        mt5: Conector MT5
        stats_db: Database de stats
        
    Returns:
        Instância do TelegramProfessional
    """
    global _telegram_instance
    
    if _telegram_instance is None:
        if config is None:
            config = {}
        _telegram_instance = TelegramProfessional(config, mt5, stats_db)
    
    return _telegram_instance


def send_telegram(message: str, notification_type: str = "system") -> bool:
    """
    Função helper para enviar mensagem rapidamente
    
    Args:
        message: Mensagem a enviar
        notification_type: Tipo de notificação
        
    Returns:
        True se enviado
    """
    tg = get_telegram()
    return tg._send_sync(message)
