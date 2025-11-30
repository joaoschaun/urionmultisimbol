# -*- coding: utf-8 -*-
"""
Strategy Communicator (Event Bus)
=================================
Sistema de comunicacao entre estrategias usando pattern Pub/Sub.
Permite que estrategias compartilhem insights e coordenem acoes.

Eventos suportados:
- Tendencia detectada
- Breakout iminente
- Reversao detectada
- Alta volatilidade
- Noticia de impacto
- Regime de mercado mudou
- Correlacao alterada
"""

from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import threading
import queue
from collections import defaultdict


class EventType(Enum):
    """Tipos de eventos do sistema"""
    # Tendencia
    TREND_DETECTED = "trend_detected"
    TREND_REVERSAL = "trend_reversal"
    TREND_WEAKENING = "trend_weakening"
    
    # Breakout
    BREAKOUT_IMMINENT = "breakout_imminent"
    BREAKOUT_CONFIRMED = "breakout_confirmed"
    BREAKOUT_FAILED = "breakout_failed"
    
    # Range
    RANGE_DETECTED = "range_detected"
    RANGE_BREAKOUT = "range_breakout"
    
    # Volatilidade
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    VOLATILITY_SPIKE = "volatility_spike"
    
    # Noticias
    NEWS_HIGH_IMPACT = "news_high_impact"
    NEWS_SURPRISE = "news_surprise"
    NEWS_SCHEDULED = "news_scheduled"
    
    # Regime
    REGIME_CHANGED = "regime_changed"
    REGIME_TRENDING = "regime_trending"
    REGIME_RANGING = "regime_ranging"
    REGIME_VOLATILE = "regime_volatile"
    
    # Correlacao
    CORRELATION_CHANGED = "correlation_changed"
    CORRELATION_DIVERGENCE = "correlation_divergence"
    
    # Order Flow
    STRONG_BUYING = "strong_buying"
    STRONG_SELLING = "strong_selling"
    ABSORPTION = "absorption"
    
    # Manipulacao
    STOP_HUNT_DETECTED = "stop_hunt_detected"
    FAKE_BREAKOUT_DETECTED = "fake_breakout_detected"
    
    # Sinais externos
    EXTERNAL_SIGNAL = "external_signal"
    TRADINGVIEW_ALERT = "tradingview_alert"
    
    # Posicoes
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_AT_RISK = "position_at_risk"
    
    # Sistema
    SYSTEM_PAUSE = "system_pause"
    SYSTEM_RESUME = "system_resume"
    CIRCUIT_BREAKER = "circuit_breaker"


class EventPriority(Enum):
    """Prioridade do evento"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class StrategyEvent:
    """Evento do sistema"""
    event_type: EventType
    source: str  # Nome da estrategia/modulo que gerou
    symbol: str
    data: Dict = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 300  # Tempo de vida do evento
    
    def is_expired(self) -> bool:
        """Verifica se o evento expirou"""
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)


@dataclass
class Subscription:
    """Inscricao de um handler"""
    event_types: Set[EventType]
    callback: Callable[[StrategyEvent], None]
    source_filter: Optional[str] = None  # Filtrar por fonte
    symbol_filter: Optional[str] = None  # Filtrar por simbolo
    priority_filter: Optional[EventPriority] = None  # Minimo de prioridade


class StrategyCommunicator:
    """
    Event Bus para comunicacao entre estrategias
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Filas de eventos por prioridade
        self._queues: Dict[EventPriority, queue.Queue] = {
            EventPriority.CRITICAL: queue.Queue(),
            EventPriority.HIGH: queue.Queue(),
            EventPriority.NORMAL: queue.Queue(),
            EventPriority.LOW: queue.Queue()
        }
        
        # Inscricoes
        self._subscriptions: Dict[str, Subscription] = {}
        self._subscription_lock = threading.Lock()
        
        # Historico de eventos
        self._event_history: List[StrategyEvent] = []
        self._max_history = 1000
        
        # Estado
        self._running = False
        self._processor_thread = None
        
        # Estatisticas
        self._stats = {
            'events_published': 0,
            'events_processed': 0,
            'events_dropped': 0
        }
        
        logger.info("StrategyCommunicator inicializado")
    
    def subscribe(self, subscriber_id: str, event_types: List[EventType],
                 callback: Callable[[StrategyEvent], None],
                 source_filter: str = None, symbol_filter: str = None,
                 min_priority: EventPriority = None):
        """Inscreve um handler para eventos"""
        with self._subscription_lock:
            self._subscriptions[subscriber_id] = Subscription(
                event_types=set(event_types),
                callback=callback,
                source_filter=source_filter,
                symbol_filter=symbol_filter,
                priority_filter=min_priority
            )
        logger.debug(f"Inscricao: {subscriber_id} para {[e.value for e in event_types]}")
    
    def unsubscribe(self, subscriber_id: str):
        """Remove inscricao"""
        with self._subscription_lock:
            if subscriber_id in self._subscriptions:
                del self._subscriptions[subscriber_id]
                logger.debug(f"Desinscricao: {subscriber_id}")
    
    def publish(self, event: StrategyEvent):
        """Publica um evento"""
        try:
            self._queues[event.priority].put_nowait(event)
            self._stats['events_published'] += 1
            
            # Adicionar ao historico
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]
            
            logger.debug(f"Evento publicado: {event.event_type.value} de {event.source}")
            
        except queue.Full:
            self._stats['events_dropped'] += 1
            logger.warning(f"Evento descartado (fila cheia): {event.event_type.value}")
    
    def publish_simple(self, event_type: EventType, source: str, symbol: str,
                      data: Dict = None, priority: EventPriority = EventPriority.NORMAL):
        """Publica evento de forma simplificada"""
        event = StrategyEvent(
            event_type=event_type,
            source=source,
            symbol=symbol,
            data=data or {},
            priority=priority
        )
        self.publish(event)
    
    def start(self):
        """Inicia o processador de eventos"""
        if self._running:
            return
        
        self._running = True
        self._processor_thread = threading.Thread(target=self._process_events, daemon=True)
        self._processor_thread.start()
        logger.info("Event processor iniciado")
    
    def stop(self):
        """Para o processador"""
        self._running = False
        if self._processor_thread:
            self._processor_thread.join(timeout=5)
        logger.info("Event processor parado")
    
    def _process_events(self):
        """Processa eventos das filas"""
        while self._running:
            try:
                # Processar por ordem de prioridade
                for priority in [EventPriority.CRITICAL, EventPriority.HIGH,
                               EventPriority.NORMAL, EventPriority.LOW]:
                    
                    try:
                        event = self._queues[priority].get_nowait()
                        
                        # Ignorar eventos expirados
                        if event.is_expired():
                            continue
                        
                        self._dispatch_event(event)
                        self._stats['events_processed'] += 1
                        
                    except queue.Empty:
                        continue
                
                # Pequena pausa para nao consumir 100% CPU
                threading.Event().wait(0.01)
                
            except Exception as e:
                logger.error(f"Erro no processador de eventos: {e}")
    
    def _dispatch_event(self, event: StrategyEvent):
        """Despacha evento para inscricoes relevantes"""
        with self._subscription_lock:
            subscriptions = list(self._subscriptions.items())
        
        for sub_id, sub in subscriptions:
            try:
                # Verificar se o tipo de evento esta inscrito
                if event.event_type not in sub.event_types:
                    continue
                
                # Verificar filtro de fonte
                if sub.source_filter and event.source != sub.source_filter:
                    continue
                
                # Verificar filtro de simbolo
                if sub.symbol_filter and event.symbol != sub.symbol_filter:
                    continue
                
                # Verificar filtro de prioridade
                if sub.priority_filter and event.priority.value < sub.priority_filter.value:
                    continue
                
                # Chamar callback
                sub.callback(event)
                
            except Exception as e:
                logger.error(f"Erro no callback {sub_id}: {e}")
    
    def get_recent_events(self, event_type: EventType = None, 
                         symbol: str = None, minutes: int = 60) -> List[StrategyEvent]:
        """Retorna eventos recentes"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        events = [e for e in self._event_history if e.timestamp > cutoff]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if symbol:
            events = [e for e in events if e.symbol == symbol]
        
        return events
    
    def get_stats(self) -> Dict:
        """Retorna estatisticas"""
        return {
            **self._stats,
            'history_size': len(self._event_history),
            'subscriptions': len(self._subscriptions),
            'queue_sizes': {p.value: self._queues[p].qsize() for p in EventPriority}
        }
    
    def has_recent_event(self, event_type: EventType, symbol: str = None,
                        minutes: int = 5) -> bool:
        """Verifica se ha evento recente de um tipo"""
        events = self.get_recent_events(event_type, symbol, minutes)
        return len(events) > 0
    
    def get_market_sentiment(self, symbol: str, minutes: int = 60) -> Dict:
        """Analisa sentimento baseado em eventos recentes"""
        events = self.get_recent_events(symbol=symbol, minutes=minutes)
        
        bullish_events = [
            EventType.TREND_DETECTED,
            EventType.BREAKOUT_CONFIRMED,
            EventType.STRONG_BUYING,
            EventType.REGIME_TRENDING
        ]
        
        bearish_events = [
            EventType.TREND_REVERSAL,
            EventType.STRONG_SELLING,
            EventType.BREAKOUT_FAILED,
            EventType.STOP_HUNT_DETECTED
        ]
        
        warning_events = [
            EventType.HIGH_VOLATILITY,
            EventType.NEWS_HIGH_IMPACT,
            EventType.FAKE_BREAKOUT_DETECTED,
            EventType.CIRCUIT_BREAKER
        ]
        
        bullish_count = len([e for e in events if e.event_type in bullish_events])
        bearish_count = len([e for e in events if e.event_type in bearish_events])
        warning_count = len([e for e in events if e.event_type in warning_events])
        
        total = bullish_count + bearish_count
        if total == 0:
            sentiment = "neutral"
            strength = 0
        else:
            bull_pct = bullish_count / total
            if bull_pct > 0.6:
                sentiment = "bullish"
            elif bull_pct < 0.4:
                sentiment = "bearish"
            else:
                sentiment = "neutral"
            strength = abs(bull_pct - 0.5) * 2
        
        return {
            'symbol': symbol,
            'sentiment': sentiment,
            'strength': strength,
            'bullish_events': bullish_count,
            'bearish_events': bearish_count,
            'warning_events': warning_count,
            'total_events': len(events)
        }


class StrategyCoordinator:
    """
    Coordenador de estrategias
    Garante que estrategias nao conflitem e prioriza sinais
    """
    
    def __init__(self, communicator: StrategyCommunicator, config: Dict = None):
        self.communicator = communicator
        self.config = config or {}
        
        # Prioridade das estrategias
        self._strategy_priority = {
            'NewsStrategy': 5,      # Maior prioridade (eventos)
            'BreakoutStrategy': 4,
            'TrendStrategy': 3,
            'RangeStrategy': 2,
            'MeanReversionStrategy': 2,
            'ScalpingStrategy': 1    # Menor prioridade
        }
        
        # Conflitos conhecidos
        self._conflicts = {
            ('TrendStrategy', 'RangeStrategy'),
            ('BreakoutStrategy', 'RangeStrategy'),
            ('ScalpingStrategy', 'TrendStrategy')
        }
        
        # Estado das estrategias
        self._strategy_state: Dict[str, str] = {}  # 'active', 'paused', 'conflict'
        
        # Lock
        self._lock = threading.Lock()
        
        logger.info("StrategyCoordinator inicializado")
    
    def can_trade(self, strategy_name: str, symbol: str) -> Tuple[bool, str]:
        """Verifica se estrategia pode operar"""
        with self._lock:
            # Verificar se esta pausada
            if self._strategy_state.get(strategy_name) == 'paused':
                return False, "Estrategia pausada"
            
            # Verificar conflitos
            for active_strategy, state in self._strategy_state.items():
                if state != 'active':
                    continue
                
                conflict_pair = tuple(sorted([strategy_name, active_strategy]))
                if conflict_pair in self._conflicts:
                    # Verificar prioridade
                    my_priority = self._strategy_priority.get(strategy_name, 0)
                    other_priority = self._strategy_priority.get(active_strategy, 0)
                    
                    if my_priority < other_priority:
                        return False, f"Conflito com {active_strategy} (maior prioridade)"
            
            # Verificar eventos de warning
            if self.communicator.has_recent_event(EventType.CIRCUIT_BREAKER, symbol, 5):
                return False, "Circuit breaker ativo"
            
            if self.communicator.has_recent_event(EventType.NEWS_HIGH_IMPACT, symbol, 10):
                return False, "Noticia de alto impacto recente"
            
            return True, "OK"
    
    def notify_trade_start(self, strategy_name: str, symbol: str):
        """Notifica que estrategia iniciou trade"""
        with self._lock:
            self._strategy_state[strategy_name] = 'active'
        
        self.communicator.publish_simple(
            EventType.POSITION_OPENED,
            strategy_name,
            symbol,
            {'strategy': strategy_name}
        )
    
    def notify_trade_end(self, strategy_name: str, symbol: str):
        """Notifica que estrategia finalizou trade"""
        with self._lock:
            self._strategy_state[strategy_name] = 'idle'
        
        self.communicator.publish_simple(
            EventType.POSITION_CLOSED,
            strategy_name,
            symbol,
            {'strategy': strategy_name}
        )
    
    def pause_strategy(self, strategy_name: str, reason: str = ""):
        """Pausa uma estrategia"""
        with self._lock:
            self._strategy_state[strategy_name] = 'paused'
        logger.info(f"Estrategia {strategy_name} pausada: {reason}")
    
    def resume_strategy(self, strategy_name: str):
        """Resume uma estrategia"""
        with self._lock:
            self._strategy_state[strategy_name] = 'idle'
        logger.info(f"Estrategia {strategy_name} retomada")
    
    def get_active_strategies(self) -> List[str]:
        """Retorna estrategias ativas"""
        with self._lock:
            return [s for s, state in self._strategy_state.items() if state == 'active']


# Singleton global
_communicator_instance = None

def get_strategy_communicator(config: Dict = None) -> StrategyCommunicator:
    """Retorna instancia singleton do communicator"""
    global _communicator_instance
    if _communicator_instance is None:
        _communicator_instance = StrategyCommunicator(config)
    return _communicator_instance
