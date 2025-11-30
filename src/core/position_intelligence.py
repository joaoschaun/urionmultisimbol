# -*- coding: utf-8 -*-
"""
Position Intelligence Manager (PIM)
====================================
Modulo CRITICO que monitora posicoes abertas em tempo real e decide:
- MANTER: Mercado alinhado com objetivo
- PROTEGER: Mover SL para breakeven ou lock profit
- POTENCIALIZAR: Adicionar a posicao (pyramiding)
- REDUZIR: Partial close se risco aumentou
- FECHAR: Condicoes mudaram completamente

Analisa continuamente:
- Tendencia atual vs tendencia da entrada
- Momentum e divergencias
- Noticias e eventos
- Volatilidade
- Correlacoes
- Tempo na posicao
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import threading
import time

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class PositionAction(Enum):
    """Acoes possiveis para uma posicao"""
    HOLD = "hold"                    # Manter posicao
    PROTECT_BREAKEVEN = "protect_be" # Mover SL para breakeven
    PROTECT_LOCK = "protect_lock"    # Travar lucro parcial
    TRAIL_STOP = "trail_stop"        # Trailing stop
    PARTIAL_CLOSE = "partial_close"  # Fechar parcialmente
    ADD_POSITION = "add_position"    # Adicionar (pyramiding)
    CLOSE_NOW = "close_now"          # Fechar imediatamente
    CLOSE_URGENT = "close_urgent"    # Fechar com urgencia (evento adverso)


class PositionHealth(Enum):
    """Saude da posicao"""
    EXCELLENT = "excellent"    # Muito favoravel
    GOOD = "good"             # Favoravel
    NEUTRAL = "neutral"       # Neutro
    CONCERNING = "concerning" # Preocupante
    CRITICAL = "critical"     # Critico - fechar


@dataclass
class PositionContext:
    """Contexto completo de uma posicao"""
    ticket: int
    symbol: str
    type: str  # 'buy' ou 'sell'
    volume: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float
    profit_pips: float
    open_time: datetime
    time_in_position: timedelta
    
    # Analise
    trend_aligned: bool
    momentum_aligned: bool
    volatility_status: str
    news_impact: str
    correlation_risk: float
    
    # Scores
    health: PositionHealth
    confidence: float
    risk_score: float


@dataclass
class PositionDecision:
    """Decisao sobre uma posicao"""
    ticket: int
    action: PositionAction
    reason: str
    confidence: float
    parameters: Dict = field(default_factory=dict)
    urgency: str = "normal"  # 'low', 'normal', 'high', 'critical'


class PositionIntelligenceManager:
    """
    Gerenciador de Inteligencia de Posicoes
    Monitora e toma decisoes sobre posicoes abertas
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.pim_config = config.get('position_intelligence', {})
        
        # Configuracoes
        self.check_interval = self.pim_config.get('check_interval', 30)  # segundos
        self.breakeven_threshold = self.pim_config.get('breakeven_pips', 20)
        self.lock_profit_threshold = self.pim_config.get('lock_profit_pips', 50)
        self.max_time_in_position = self.pim_config.get('max_hours', 48)
        self.add_position_threshold = self.pim_config.get('add_position_profit_pips', 30)
        
        # Thresholds de risco
        self.max_adverse_pips = self.pim_config.get('max_adverse_pips', 50)
        self.volatility_multiplier = self.pim_config.get('volatility_multiplier', 2.0)
        
        # Cache de analises
        self._position_cache: Dict[int, PositionContext] = {}
        self._decision_history: Dict[int, List[PositionDecision]] = {}
        
        # Threading
        self._running = False
        self._monitor_thread = None
        self._lock = threading.Lock()
        
        # Callbacks
        self._action_callbacks: List[callable] = []
        
        logger.info("PositionIntelligenceManager inicializado")
    
    def register_action_callback(self, callback: callable):
        """Registra callback para quando uma acao e decidida"""
        self._action_callbacks.append(callback)
    
    def start(self):
        """Inicia monitoramento continuo"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Position Intelligence Monitor iniciado")
    
    def stop(self):
        """Para o monitoramento"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Position Intelligence Monitor parado")
    
    def _monitor_loop(self):
        """Loop principal de monitoramento"""
        while self._running:
            try:
                positions = self._get_open_positions()
                
                for pos in positions:
                    context = self._analyze_position(pos)
                    decision = self._decide_action(context)
                    
                    if decision.action != PositionAction.HOLD:
                        self._execute_decision(decision)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Erro no monitor de posicoes: {e}")
                time.sleep(5)
    
    def _get_open_positions(self) -> List[Dict]:
        """Obtem posicoes abertas do MT5"""
        if not mt5:
            return []
        
        positions = mt5.positions_get()
        if positions is None:
            return []
        
        return [
            {
                'ticket': p.ticket,
                'symbol': p.symbol,
                'type': 'buy' if p.type == mt5.ORDER_TYPE_BUY else 'sell',
                'volume': p.volume,
                'open_price': p.price_open,
                'current_price': p.price_current,
                'sl': p.sl,
                'tp': p.tp,
                'profit': p.profit,
                'open_time': datetime.fromtimestamp(p.time),
                'magic': p.magic,
                'comment': p.comment
            }
            for p in positions
        ]
    
    def _analyze_position(self, pos: Dict) -> PositionContext:
        """Analisa uma posicao em profundidade"""
        symbol = pos['symbol']
        
        # Calcular profit em pips
        symbol_info = mt5.symbol_info(symbol) if mt5 else None
        point = symbol_info.point if symbol_info else 0.01
        
        if pos['type'] == 'buy':
            profit_pips = (pos['current_price'] - pos['open_price']) / point
        else:
            profit_pips = (pos['open_price'] - pos['current_price']) / point
        
        # Tempo na posicao
        time_in_position = datetime.now() - pos['open_time']
        
        # Analisar tendencia
        trend_aligned = self._check_trend_alignment(symbol, pos['type'])
        
        # Analisar momentum
        momentum_aligned = self._check_momentum_alignment(symbol, pos['type'])
        
        # Analisar volatilidade
        volatility_status = self._check_volatility(symbol)
        
        # Verificar noticias
        news_impact = self._check_news_impact(symbol)
        
        # Calcular risco de correlacao
        correlation_risk = self._calculate_correlation_risk(symbol)
        
        # Determinar saude da posicao
        health, confidence, risk_score = self._calculate_health(
            profit_pips, trend_aligned, momentum_aligned, 
            volatility_status, news_impact, time_in_position
        )
        
        context = PositionContext(
            ticket=pos['ticket'],
            symbol=symbol,
            type=pos['type'],
            volume=pos['volume'],
            open_price=pos['open_price'],
            current_price=pos['current_price'],
            sl=pos['sl'],
            tp=pos['tp'],
            profit=pos['profit'],
            profit_pips=profit_pips,
            open_time=pos['open_time'],
            time_in_position=time_in_position,
            trend_aligned=trend_aligned,
            momentum_aligned=momentum_aligned,
            volatility_status=volatility_status,
            news_impact=news_impact,
            correlation_risk=correlation_risk,
            health=health,
            confidence=confidence,
            risk_score=risk_score
        )
        
        with self._lock:
            self._position_cache[pos['ticket']] = context
        
        return context
    
    def _check_trend_alignment(self, symbol: str, position_type: str) -> bool:
        """Verifica se a tendencia ainda esta alinhada com a posicao"""
        if not mt5:
            return True
        
        try:
            # Obter dados recentes
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
            if rates is None or len(rates) < 50:
                return True
            
            df = pd.DataFrame(rates)
            
            # Calcular EMAs
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            current_price = df['close'].iloc[-1]
            
            if position_type == 'buy':
                # Para compra: preco acima das EMAs e EMA20 > EMA50
                return current_price > ema20 and ema20 > ema50
            else:
                # Para venda: preco abaixo das EMAs e EMA20 < EMA50
                return current_price < ema20 and ema20 < ema50
                
        except Exception as e:
            logger.error(f"Erro ao verificar tendencia: {e}")
            return True
    
    def _check_momentum_alignment(self, symbol: str, position_type: str) -> bool:
        """Verifica se o momentum esta alinhado com a posicao"""
        if not mt5:
            return True
        
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 20)
            if rates is None or len(rates) < 20:
                return True
            
            df = pd.DataFrame(rates)
            
            # Calcular RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            if position_type == 'buy':
                # Momentum positivo para compra
                return current_rsi > 40 and current_rsi < 80
            else:
                # Momentum negativo para venda
                return current_rsi < 60 and current_rsi > 20
                
        except Exception as e:
            logger.error(f"Erro ao verificar momentum: {e}")
            return True
    
    def _check_volatility(self, symbol: str) -> str:
        """Verifica o status da volatilidade"""
        if not mt5:
            return "normal"
        
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 30)
            if rates is None or len(rates) < 30:
                return "normal"
            
            df = pd.DataFrame(rates)
            
            # Calcular ATR
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr = np.maximum(high[1:] - low[1:],
                           np.abs(high[1:] - close[:-1]),
                           np.abs(low[1:] - close[:-1]))
            
            current_atr = np.mean(tr[-14:])
            historical_atr = np.mean(tr[-30:-14])
            
            if historical_atr == 0:
                return "normal"
            
            atr_ratio = current_atr / historical_atr
            
            if atr_ratio > self.volatility_multiplier:
                return "high"
            elif atr_ratio < 0.5:
                return "low"
            else:
                return "normal"
                
        except Exception as e:
            logger.error(f"Erro ao verificar volatilidade: {e}")
            return "normal"
    
    def _check_news_impact(self, symbol: str) -> str:
        """Verifica impacto de noticias"""
        # Simplificado - em producao integraria com news analyzer
        return "none"
    
    def _calculate_correlation_risk(self, symbol: str) -> float:
        """Calcula risco de correlacao com outras posicoes"""
        # Simplificado - retorna 0 (sem risco adicional)
        return 0.0
    
    def _calculate_health(self, profit_pips: float, trend_aligned: bool,
                         momentum_aligned: bool, volatility: str,
                         news: str, time_in: timedelta) -> Tuple[PositionHealth, float, float]:
        """Calcula saude geral da posicao"""
        score = 50  # Base neutra
        
        # Profit/Loss impact
        if profit_pips > 50:
            score += 20
        elif profit_pips > 20:
            score += 10
        elif profit_pips < -30:
            score -= 20
        elif profit_pips < -10:
            score -= 10
        
        # Trend alignment
        if trend_aligned:
            score += 15
        else:
            score -= 15
        
        # Momentum alignment
        if momentum_aligned:
            score += 10
        else:
            score -= 10
        
        # Volatility
        if volatility == "high":
            score -= 10
        elif volatility == "low":
            score += 5
        
        # News impact
        if news == "high_negative":
            score -= 25
        elif news == "high_positive":
            score += 15
        
        # Time in position
        hours = time_in.total_seconds() / 3600
        if hours > self.max_time_in_position:
            score -= 15
        elif hours > self.max_time_in_position / 2:
            score -= 5
        
        # Normalizar score
        score = max(0, min(100, score))
        
        # Determinar health
        if score >= 75:
            health = PositionHealth.EXCELLENT
        elif score >= 60:
            health = PositionHealth.GOOD
        elif score >= 40:
            health = PositionHealth.NEUTRAL
        elif score >= 25:
            health = PositionHealth.CONCERNING
        else:
            health = PositionHealth.CRITICAL
        
        confidence = score / 100
        risk_score = 1 - confidence
        
        return health, confidence, risk_score
    
    def _decide_action(self, context: PositionContext) -> PositionDecision:
        """Decide qual acao tomar para a posicao"""
        
        # CRITICO - Fechar imediatamente
        if context.health == PositionHealth.CRITICAL:
            return PositionDecision(
                ticket=context.ticket,
                action=PositionAction.CLOSE_URGENT,
                reason=f"Saude CRITICA - Score: {context.confidence:.0%}, Trend: {context.trend_aligned}, Momentum: {context.momentum_aligned}",
                confidence=0.9,
                urgency="critical"
            )
        
        # Noticia de alto impacto negativo
        if context.news_impact == "high_negative":
            return PositionDecision(
                ticket=context.ticket,
                action=PositionAction.CLOSE_URGENT,
                reason="Noticia de alto impacto negativo detectada",
                confidence=0.85,
                urgency="critical"
            )
        
        # Tempo maximo excedido
        hours = context.time_in_position.total_seconds() / 3600
        if hours > self.max_time_in_position:
            return PositionDecision(
                ticket=context.ticket,
                action=PositionAction.CLOSE_NOW,
                reason=f"Tempo maximo em posicao excedido ({hours:.1f}h > {self.max_time_in_position}h)",
                confidence=0.8,
                urgency="high"
            )
        
        # Volatilidade muito alta e posicao perdendo
        if context.volatility_status == "high" and context.profit_pips < 0:
            if context.profit_pips < -self.max_adverse_pips:
                return PositionDecision(
                    ticket=context.ticket,
                    action=PositionAction.CLOSE_NOW,
                    reason=f"Alta volatilidade + perda de {abs(context.profit_pips):.0f} pips",
                    confidence=0.75,
                    urgency="high"
                )
        
        # Tendencia virou contra
        if not context.trend_aligned and not context.momentum_aligned:
            if context.profit_pips > self.breakeven_threshold:
                return PositionDecision(
                    ticket=context.ticket,
                    action=PositionAction.PROTECT_LOCK,
                    reason="Tendencia virou - protegendo lucro",
                    confidence=0.8,
                    parameters={'lock_pips': context.profit_pips * 0.5},
                    urgency="normal"
                )
            elif context.profit_pips > 0:
                return PositionDecision(
                    ticket=context.ticket,
                    action=PositionAction.PROTECT_BREAKEVEN,
                    reason="Tendencia virou - movendo para breakeven",
                    confidence=0.75,
                    urgency="normal"
                )
            else:
                return PositionDecision(
                    ticket=context.ticket,
                    action=PositionAction.PARTIAL_CLOSE,
                    reason="Tendencia virou contra - reduzindo exposicao",
                    confidence=0.7,
                    parameters={'close_percentage': 0.5},
                    urgency="normal"
                )
        
        # Posicao em bom lucro - proteger
        if context.profit_pips >= self.lock_profit_threshold:
            return PositionDecision(
                ticket=context.ticket,
                action=PositionAction.TRAIL_STOP,
                reason=f"Lucro de {context.profit_pips:.0f} pips - ativando trailing",
                confidence=0.85,
                parameters={'trail_distance': context.profit_pips * 0.3},
                urgency="low"
            )
        
        # Posicao em lucro moderado - breakeven
        if context.profit_pips >= self.breakeven_threshold:
            if context.sl < context.open_price and context.type == 'buy':
                return PositionDecision(
                    ticket=context.ticket,
                    action=PositionAction.PROTECT_BREAKEVEN,
                    reason=f"Lucro de {context.profit_pips:.0f} pips - protegendo breakeven",
                    confidence=0.8,
                    urgency="low"
                )
            elif context.sl > context.open_price and context.type == 'sell':
                return PositionDecision(
                    ticket=context.ticket,
                    action=PositionAction.PROTECT_BREAKEVEN,
                    reason=f"Lucro de {context.profit_pips:.0f} pips - protegendo breakeven",
                    confidence=0.8,
                    urgency="low"
                )
        
        # Condicoes excelentes - considerar adicionar
        if context.health == PositionHealth.EXCELLENT:
            if context.profit_pips >= self.add_position_threshold:
                if context.trend_aligned and context.momentum_aligned:
                    return PositionDecision(
                        ticket=context.ticket,
                        action=PositionAction.ADD_POSITION,
                        reason="Condicoes excelentes - pyramiding",
                        confidence=0.7,
                        parameters={'add_volume': context.volume * 0.5},
                        urgency="low"
                    )
        
        # Default - manter posicao
        return PositionDecision(
            ticket=context.ticket,
            action=PositionAction.HOLD,
            reason=f"Posicao saudavel - Health: {context.health.value}, Profit: {context.profit_pips:.0f} pips",
            confidence=context.confidence,
            urgency="low"
        )
    
    def _execute_decision(self, decision: PositionDecision):
        """Executa a decisao e notifica callbacks"""
        logger.info(f"PIM Decision: {decision.action.value} para ticket {decision.ticket} - {decision.reason}")
        
        # Salvar no historico
        with self._lock:
            if decision.ticket not in self._decision_history:
                self._decision_history[decision.ticket] = []
            self._decision_history[decision.ticket].append(decision)
        
        # Notificar callbacks
        for callback in self._action_callbacks:
            try:
                callback(decision)
            except Exception as e:
                logger.error(f"Erro no callback de decisao: {e}")
    
    def get_position_summary(self) -> Dict:
        """Retorna resumo de todas as posicoes"""
        with self._lock:
            positions = list(self._position_cache.values())
        
        if not positions:
            return {'total': 0, 'positions': []}
        
        return {
            'total': len(positions),
            'total_profit': sum(p.profit for p in positions),
            'excellent': len([p for p in positions if p.health == PositionHealth.EXCELLENT]),
            'good': len([p for p in positions if p.health == PositionHealth.GOOD]),
            'neutral': len([p for p in positions if p.health == PositionHealth.NEUTRAL]),
            'concerning': len([p for p in positions if p.health == PositionHealth.CONCERNING]),
            'critical': len([p for p in positions if p.health == PositionHealth.CRITICAL]),
            'positions': [
                {
                    'ticket': p.ticket,
                    'symbol': p.symbol,
                    'type': p.type,
                    'profit_pips': p.profit_pips,
                    'health': p.health.value,
                    'trend_aligned': p.trend_aligned,
                    'momentum_aligned': p.momentum_aligned
                }
                for p in positions
            ]
        }
    
    def force_check(self, ticket: int = None) -> List[PositionDecision]:
        """Forca verificacao imediata"""
        positions = self._get_open_positions()
        decisions = []
        
        for pos in positions:
            if ticket and pos['ticket'] != ticket:
                continue
            
            context = self._analyze_position(pos)
            decision = self._decide_action(context)
            decisions.append(decision)
            
            if decision.action != PositionAction.HOLD:
                self._execute_decision(decision)
        
        return decisions


# Singleton
_pim_instance = None

def get_position_intelligence_manager(config: Dict = None) -> Optional[PositionIntelligenceManager]:
    """Retorna instancia singleton"""
    global _pim_instance
    if _pim_instance is None and config:
        _pim_instance = PositionIntelligenceManager(config)
    return _pim_instance
