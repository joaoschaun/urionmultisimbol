# -*- coding: utf-8 -*-
"""
TradingView Integration
=======================
Integra alertas do TradingView via webhook para receber sinais externos.
Permite usar indicadores avancados do TradingView como:
- Smart Money Concepts (SMC)
- Order Blocks
- Fair Value Gaps (FVG)
- Liquidity Zones
- ICT Concepts
"""

import asyncio
import json
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger
import threading
import queue

try:
    from aiohttp import web
except ImportError:
    web = None


class TradingViewSignalType(Enum):
    """Tipos de sinais do TradingView"""
    BUY = "buy"
    SELL = "sell"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    ALERT = "alert"
    ORDER_BLOCK = "order_block"
    FVG = "fvg"
    LIQUIDITY = "liquidity"
    SMART_MONEY = "smart_money"


@dataclass
class TradingViewSignal:
    """Sinal recebido do TradingView"""
    timestamp: datetime
    signal_type: TradingViewSignalType
    symbol: str
    price: float
    action: str
    message: str
    confidence: float = 0.5
    timeframe: str = "1H"
    indicator: str = ""
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    raw_data: Dict = field(default_factory=dict)


class TradingViewWebhookServer:
    """
    Servidor de webhooks para receber alertas do TradingView
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.tv_config = config.get('tradingview', {})
        
        self.host = self.tv_config.get('webhook_host', '0.0.0.0')
        self.port = self.tv_config.get('webhook_port', 8765)
        self.secret_key = self.tv_config.get('secret_key', '')
        
        # Fila de sinais recebidos
        self._signal_queue: queue.Queue = queue.Queue()
        
        # Callbacks registrados
        self._callbacks: List[Callable] = []
        
        # Estado do servidor
        self._running = False
        self._server_thread = None
        self._app = None
        self._runner = None
        
        logger.info(f"TradingView Webhook Server configurado em {self.host}:{self.port}")
    
    def register_callback(self, callback: Callable[[TradingViewSignal], None]):
        """Registra callback para processar sinais"""
        self._callbacks.append(callback)
        logger.info(f"Callback registrado: {callback.__name__}")
    
    async def _handle_webhook(self, request):
        """Handler para requisicoes webhook"""
        try:
            # Verificar metodo
            if request.method != 'POST':
                return web.Response(status=405, text="Method not allowed")
            
            # Ler body
            try:
                data = await request.json()
            except json.JSONDecodeError:
                text = await request.text()
                # Tentar parsear como texto simples
                data = {'message': text, 'action': 'ALERT'}
            
            logger.info(f"Webhook recebido: {data}")
            
            # Verificar secret key se configurado
            if self.secret_key:
                received_key = data.get('secret_key', request.headers.get('X-Secret-Key', ''))
                if received_key != self.secret_key:
                    logger.warning("Webhook rejeitado: secret key invalida")
                    return web.Response(status=401, text="Unauthorized")
            
            # Parsear sinal
            signal = self._parse_signal(data)
            
            if signal:
                # Adicionar a fila
                self._signal_queue.put(signal)
                
                # Chamar callbacks
                for callback in self._callbacks:
                    try:
                        callback(signal)
                    except Exception as e:
                        logger.error(f"Erro no callback: {e}")
                
                logger.info(f"Sinal processado: {signal.signal_type.value} {signal.symbol}")
            
            return web.Response(status=200, text="OK")
            
        except Exception as e:
            logger.error(f"Erro ao processar webhook: {e}")
            return web.Response(status=500, text=str(e))
    
    def _parse_signal(self, data: Dict) -> Optional[TradingViewSignal]:
        """Parseia dados do webhook para TradingViewSignal"""
        try:
            # Extrair action
            action = data.get('action', data.get('order', '')).upper()
            
            # Determinar tipo de sinal
            if action in ['BUY', 'LONG']:
                signal_type = TradingViewSignalType.BUY
            elif action in ['SELL', 'SHORT']:
                signal_type = TradingViewSignalType.SELL
            elif action == 'CLOSE_LONG':
                signal_type = TradingViewSignalType.CLOSE_LONG
            elif action == 'CLOSE_SHORT':
                signal_type = TradingViewSignalType.CLOSE_SHORT
            elif 'ORDER_BLOCK' in action or 'OB' in action:
                signal_type = TradingViewSignalType.ORDER_BLOCK
            elif 'FVG' in action or 'GAP' in action:
                signal_type = TradingViewSignalType.FVG
            elif 'LIQUIDITY' in action or 'LIQ' in action:
                signal_type = TradingViewSignalType.LIQUIDITY
            elif 'SMC' in action or 'SMART' in action:
                signal_type = TradingViewSignalType.SMART_MONEY
            else:
                signal_type = TradingViewSignalType.ALERT
            
            # Extrair simbolo
            symbol = data.get('symbol', data.get('ticker', 'XAUUSD'))
            symbol = symbol.replace('/', '').replace('_', '').upper()
            
            # Extrair preco
            price = float(data.get('price', data.get('close', 0)))
            
            # Extrair confianca
            confidence = float(data.get('confidence', data.get('strength', 0.5)))
            confidence = max(0, min(1, confidence))
            
            # Extrair TP/SL
            take_profit = data.get('take_profit', data.get('tp'))
            stop_loss = data.get('stop_loss', data.get('sl'))
            
            if take_profit:
                take_profit = float(take_profit)
            if stop_loss:
                stop_loss = float(stop_loss)
            
            return TradingViewSignal(
                timestamp=datetime.now(),
                signal_type=signal_type,
                symbol=symbol,
                price=price,
                action=action,
                message=data.get('message', data.get('comment', '')),
                confidence=confidence,
                timeframe=data.get('timeframe', data.get('interval', '1H')),
                indicator=data.get('indicator', data.get('strategy', '')),
                take_profit=take_profit,
                stop_loss=stop_loss,
                raw_data=data
            )
            
        except Exception as e:
            logger.error(f"Erro ao parsear sinal: {e}")
            return None
    
    async def _run_server(self):
        """Executa o servidor async"""
        self._app = web.Application()
        self._app.router.add_post('/webhook', self._handle_webhook)
        self._app.router.add_post('/tradingview', self._handle_webhook)
        self._app.router.add_get('/health', self._health_check)
        
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        
        logger.info(f"TradingView Webhook Server rodando em http://{self.host}:{self.port}")
        
        while self._running:
            await asyncio.sleep(1)
        
        await self._runner.cleanup()
    
    async def _health_check(self, request):
        """Endpoint de health check"""
        return web.Response(text="OK", status=200)
    
    def start(self):
        """Inicia o servidor em uma thread separada"""
        if self._running:
            return
        
        if web is None:
            logger.error("aiohttp nao instalado. Instale com: pip install aiohttp")
            return
        
        self._running = True
        
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_server())
        
        self._server_thread = threading.Thread(target=run_loop, daemon=True)
        self._server_thread.start()
        
        logger.info("TradingView Webhook Server iniciado")
    
    def stop(self):
        """Para o servidor"""
        self._running = False
        if self._server_thread:
            self._server_thread.join(timeout=5)
        logger.info("TradingView Webhook Server parado")
    
    def get_pending_signals(self) -> List[TradingViewSignal]:
        """Retorna sinais pendentes na fila"""
        signals = []
        while not self._signal_queue.empty():
            try:
                signals.append(self._signal_queue.get_nowait())
            except queue.Empty:
                break
        return signals
    
    def has_pending_signals(self) -> bool:
        """Verifica se ha sinais pendentes"""
        return not self._signal_queue.empty()


class TradingViewAlertManager:
    """
    Gerenciador de alertas do TradingView
    Processa e filtra sinais recebidos
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.tv_config = config.get('tradingview', {})
        
        # Configuracoes de filtro
        self.min_confidence = self.tv_config.get('min_confidence', 0.6)
        self.allowed_symbols = self.tv_config.get('allowed_symbols', ['XAUUSD'])
        self.allowed_timeframes = self.tv_config.get('allowed_timeframes', ['5M', '15M', '1H', '4H'])
        
        # Historico de sinais
        self._signal_history: List[TradingViewSignal] = []
        self._max_history = 1000
        
        # Webhook server
        self.webhook_server = TradingViewWebhookServer(config)
        
        logger.info("TradingViewAlertManager inicializado")
    
    def start(self):
        """Inicia o servidor de webhooks"""
        self.webhook_server.start()
    
    def stop(self):
        """Para o servidor"""
        self.webhook_server.stop()
    
    def register_signal_handler(self, handler: Callable[[TradingViewSignal], None]):
        """Registra handler para sinais"""
        def filtered_handler(signal: TradingViewSignal):
            if self._filter_signal(signal):
                handler(signal)
                self._signal_history.append(signal)
                if len(self._signal_history) > self._max_history:
                    self._signal_history = self._signal_history[-self._max_history:]
        
        self.webhook_server.register_callback(filtered_handler)
    
    def _filter_signal(self, signal: TradingViewSignal) -> bool:
        """Filtra sinais baseado em criterios"""
        # Verificar confianca minima
        if signal.confidence < self.min_confidence:
            logger.debug(f"Sinal filtrado: confianca {signal.confidence} < {self.min_confidence}")
            return False
        
        # Verificar simbolo
        if self.allowed_symbols and signal.symbol not in self.allowed_symbols:
            logger.debug(f"Sinal filtrado: simbolo {signal.symbol} nao permitido")
            return False
        
        # Verificar timeframe
        if self.allowed_timeframes and signal.timeframe.upper() not in [tf.upper() for tf in self.allowed_timeframes]:
            logger.debug(f"Sinal filtrado: timeframe {signal.timeframe} nao permitido")
            return False
        
        return True
    
    def get_latest_signal(self, symbol: str = None) -> Optional[TradingViewSignal]:
        """Retorna o sinal mais recente"""
        for signal in reversed(self._signal_history):
            if symbol is None or signal.symbol == symbol:
                return signal
        return None
    
    def get_signals_summary(self) -> Dict:
        """Retorna resumo dos sinais"""
        buy_signals = len([s for s in self._signal_history if s.signal_type == TradingViewSignalType.BUY])
        sell_signals = len([s for s in self._signal_history if s.signal_type == TradingViewSignalType.SELL])
        
        return {
            'total_signals': len(self._signal_history),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'last_signal': self._signal_history[-1].timestamp.isoformat() if self._signal_history else None,
            'webhook_url': f"http://{self.webhook_server.host}:{self.webhook_server.port}/webhook"
        }


# Pine Script template para usar no TradingView
PINE_SCRIPT_TEMPLATE = '''
//@version=5
strategy("Urion Bot Signal Sender", overlay=true)

// Configuracoes
webhook_url = "http://YOUR_SERVER_IP:8765/webhook"

// Sua logica de estrategia aqui
// ...

// Enviar sinal de compra
if (buy_condition)
    alert('{"action": "BUY", "symbol": "' + syminfo.ticker + '", "price": ' + str.tostring(close) + ', "confidence": 0.8, "timeframe": "' + timeframe.period + '"}', alert.freq_once_per_bar)

// Enviar sinal de venda
if (sell_condition)
    alert('{"action": "SELL", "symbol": "' + syminfo.ticker + '", "price": ' + str.tostring(close) + ', "confidence": 0.8, "timeframe": "' + timeframe.period + '"}', alert.freq_once_per_bar)
'''


# Singleton
_tradingview_manager = None

def get_tradingview_manager(config: Dict = None) -> Optional[TradingViewAlertManager]:
    """Retorna instancia singleton"""
    global _tradingview_manager
    if _tradingview_manager is None and config:
        _tradingview_manager = TradingViewAlertManager(config)
    return _tradingview_manager
