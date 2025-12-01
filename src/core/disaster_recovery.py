# -*- coding: utf-8 -*-
"""
Disaster Recovery Module

Sistema de recuperação de desastres:
- Detecção de anomalias
- Recuperação automática
- Circuit breaker
- Notificações de emergência
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import traceback

logger = logging.getLogger(__name__)


class DisasterType(Enum):
    """Tipos de desastres"""
    CONNECTION_LOSS = "connection_loss"
    HIGH_DRAWDOWN = "high_drawdown"
    RAPID_LOSSES = "rapid_losses"
    SYSTEM_ERROR = "system_error"
    MARKET_ANOMALY = "market_anomaly"
    DATA_CORRUPTION = "data_corruption"
    MEMORY_OVERFLOW = "memory_overflow"
    MT5_DISCONNECT = "mt5_disconnect"


class RecoveryAction(Enum):
    """Ações de recuperação"""
    RECONNECT = "reconnect"
    CLOSE_ALL = "close_all"
    PAUSE_TRADING = "pause_trading"
    RESTART_BOT = "restart_bot"
    ALERT_ONLY = "alert_only"
    REDUCE_EXPOSURE = "reduce_exposure"


@dataclass
class DisasterEvent:
    """Evento de desastre"""
    type: DisasterType
    timestamp: datetime
    message: str
    severity: int  # 1-5
    data: Dict[str, Any] = field(default_factory=dict)
    recovered: bool = False
    recovery_time: Optional[datetime] = None
    recovery_action: Optional[RecoveryAction] = None


@dataclass
class CircuitState:
    """Estado do circuit breaker"""
    is_open: bool = False
    opened_at: Optional[datetime] = None
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None


class CircuitBreaker:
    """
    Circuit Breaker Pattern
    
    Previne falhas em cascata:
    - Abre após N falhas
    - Half-open para testar
    - Fecha se teste passar
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        
        self.state = CircuitState()
        self.half_open_successes = 0
        self._lock = threading.Lock()
    
    def is_closed(self) -> bool:
        """Verifica se circuit está fechado (funcionando)"""
        with self._lock:
            if not self.state.is_open:
                return True
            
            # Verificar se podemos tentar half-open
            if self.state.cooldown_until and datetime.now() >= self.state.cooldown_until:
                return True  # Permitir tentativa
            
            return False
    
    def record_success(self):
        """Registra sucesso"""
        with self._lock:
            if self.state.is_open:
                self.half_open_successes += 1
                
                if self.half_open_successes >= self.half_open_requests:
                    self._close()
            else:
                # Reset failure count em sucesso
                self.state.failure_count = 0
    
    def record_failure(self):
        """Registra falha"""
        with self._lock:
            self.state.failure_count += 1
            self.state.last_failure = datetime.now()
            
            if self.state.is_open:
                # Resetar half-open
                self.half_open_successes = 0
                self._open()
            elif self.state.failure_count >= self.failure_threshold:
                self._open()
    
    def _open(self):
        """Abre o circuit"""
        self.state.is_open = True
        self.state.opened_at = datetime.now()
        self.state.cooldown_until = datetime.now() + timedelta(seconds=self.recovery_timeout)
        self.half_open_successes = 0
        
        logger.warning(f"Circuit breaker '{self.name}' ABERTO após {self.state.failure_count} falhas")
    
    def _close(self):
        """Fecha o circuit"""
        self.state.is_open = False
        self.state.failure_count = 0
        self.half_open_successes = 0
        
        logger.info(f"Circuit breaker '{self.name}' FECHADO")
    
    def __call__(self, func: Callable):
        """Decorator para proteger funções"""
        def wrapper(*args, **kwargs):
            if not self.is_closed():
                raise Exception(f"Circuit '{self.name}' está aberto")
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise
        
        return wrapper


class DisasterRecovery:
    """
    Sistema de Disaster Recovery
    
    Features:
    - Detecção de anomalias
    - Recuperação automática
    - Circuit breakers
    - Notificações
    """
    
    def __init__(self, config: Dict[str, Any] = None, state_manager = None, mt5 = None):
        self.config = config or {}
        self.state_manager = state_manager
        self.mt5 = mt5
        
        # Histórico de eventos
        self.events: List[DisasterEvent] = []
        self.max_events = 1000
        
        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._init_circuit_breakers()
        
        # Thresholds
        self.max_drawdown = self.config.get('max_drawdown', 0.05)  # 5%
        self.max_daily_loss = self.config.get('max_daily_loss', 0.03)  # 3%
        self.max_rapid_losses = self.config.get('max_rapid_losses', 5)  # 5 perdas em 1h
        self.reconnect_attempts = self.config.get('reconnect_attempts', 5)
        
        # Estado de trading
        self.trading_paused = False
        self.pause_until: Optional[datetime] = None
        
        # Callbacks
        self.alert_callbacks: List[Callable] = []
        
        # Threading
        self.running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Métricas
        self.recent_losses: List[datetime] = []
        
        logger.info("DisasterRecovery inicializado")
    
    def _init_circuit_breakers(self):
        """Inicializa circuit breakers"""
        self.circuit_breakers = {
            'mt5_connection': CircuitBreaker('mt5_connection', 3, 30),
            'order_execution': CircuitBreaker('order_execution', 5, 60),
            'data_feed': CircuitBreaker('data_feed', 3, 30),
            'ml_prediction': CircuitBreaker('ml_prediction', 5, 120),
        }
    
    def start(self):
        """Inicia monitoramento"""
        if self.running:
            return
        
        self.running = True
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="DisasterMonitor"
        )
        self._monitor_thread.start()
        
        logger.info("DisasterRecovery iniciado")
    
    def stop(self):
        """Para monitoramento"""
        self.running = False
        logger.info("DisasterRecovery parado")
    
    def register_alert_callback(self, callback: Callable):
        """Registra callback para alertas"""
        self.alert_callbacks.append(callback)
    
    def get_circuit(self, name: str) -> CircuitBreaker:
        """Retorna circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name)
        return self.circuit_breakers[name]
    
    def check_trading_allowed(self) -> tuple[bool, str]:
        """Verifica se trading está permitido"""
        with self._lock:
            if self.trading_paused:
                if self.pause_until and datetime.now() >= self.pause_until:
                    self.trading_paused = False
                    logger.info("Pausa de trading expirou")
                else:
                    return False, "Trading pausado por segurança"
            
            # Verificar circuit breakers críticos
            for name in ['mt5_connection', 'order_execution']:
                cb = self.circuit_breakers.get(name)
                if cb and not cb.is_closed():
                    return False, f"Circuit breaker '{name}' aberto"
            
            return True, "OK"
    
    def report_trade_result(self, profit: float, symbol: str):
        """Reporta resultado de trade"""
        with self._lock:
            if profit < 0:
                self.recent_losses.append(datetime.now())
                
                # Limpar perdas antigas (mais de 1h)
                cutoff = datetime.now() - timedelta(hours=1)
                self.recent_losses = [l for l in self.recent_losses if l > cutoff]
                
                # Verificar rapid losses
                if len(self.recent_losses) >= self.max_rapid_losses:
                    self._handle_disaster(DisasterEvent(
                        type=DisasterType.RAPID_LOSSES,
                        timestamp=datetime.now(),
                        message=f"{len(self.recent_losses)} perdas na última hora",
                        severity=4,
                        data={'losses': len(self.recent_losses), 'symbol': symbol}
                    ))
    
    def report_drawdown(self, current_drawdown: float):
        """Reporta drawdown atual"""
        with self._lock:
            if current_drawdown >= self.max_drawdown:
                self._handle_disaster(DisasterEvent(
                    type=DisasterType.HIGH_DRAWDOWN,
                    timestamp=datetime.now(),
                    message=f"Drawdown de {current_drawdown:.2%} excede limite de {self.max_drawdown:.2%}",
                    severity=5,
                    data={'drawdown': current_drawdown, 'limit': self.max_drawdown}
                ))
    
    def report_daily_loss(self, daily_loss: float):
        """Reporta perda diária"""
        with self._lock:
            if abs(daily_loss) >= self.max_daily_loss:
                self._handle_disaster(DisasterEvent(
                    type=DisasterType.HIGH_DRAWDOWN,
                    timestamp=datetime.now(),
                    message=f"Perda diária de {abs(daily_loss):.2%} excede limite",
                    severity=5,
                    data={'daily_loss': daily_loss}
                ))
    
    def report_connection_loss(self, source: str):
        """Reporta perda de conexão"""
        with self._lock:
            cb = self.circuit_breakers.get(f'{source}_connection')
            if cb:
                cb.record_failure()
            
            self._handle_disaster(DisasterEvent(
                type=DisasterType.CONNECTION_LOSS,
                timestamp=datetime.now(),
                message=f"Conexão perdida: {source}",
                severity=3,
                data={'source': source}
            ))
    
    def report_error(self, error: Exception, context: str):
        """Reporta erro do sistema"""
        with self._lock:
            self._handle_disaster(DisasterEvent(
                type=DisasterType.SYSTEM_ERROR,
                timestamp=datetime.now(),
                message=f"Erro em {context}: {str(error)}",
                severity=3,
                data={
                    'context': context,
                    'error': str(error),
                    'traceback': traceback.format_exc()
                }
            ))
    
    def _handle_disaster(self, event: DisasterEvent):
        """Processa evento de desastre"""
        logger.error(f"DISASTER: {event.type.value} - {event.message}")
        
        # Adicionar ao histórico
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Determinar ação
        action = self._determine_action(event)
        event.recovery_action = action
        
        # Executar ação
        self._execute_recovery(event, action)
        
        # Alertar
        self._send_alert(event)
        
        # Salvar estado
        if self.state_manager:
            self.state_manager.record_error(event.message)
    
    def _determine_action(self, event: DisasterEvent) -> RecoveryAction:
        """Determina ação de recuperação"""
        
        # Baseado no tipo
        if event.type == DisasterType.CONNECTION_LOSS:
            return RecoveryAction.RECONNECT
        
        elif event.type == DisasterType.HIGH_DRAWDOWN:
            return RecoveryAction.CLOSE_ALL
        
        elif event.type == DisasterType.RAPID_LOSSES:
            return RecoveryAction.PAUSE_TRADING
        
        elif event.type == DisasterType.MT5_DISCONNECT:
            return RecoveryAction.RECONNECT
        
        elif event.type == DisasterType.MARKET_ANOMALY:
            return RecoveryAction.REDUCE_EXPOSURE
        
        else:
            return RecoveryAction.ALERT_ONLY
    
    def _execute_recovery(self, event: DisasterEvent, action: RecoveryAction):
        """Executa ação de recuperação"""
        
        try:
            if action == RecoveryAction.RECONNECT:
                self._attempt_reconnect(event.data.get('source', 'mt5'))
            
            elif action == RecoveryAction.CLOSE_ALL:
                self._close_all_positions()
                self._pause_trading(hours=24)
            
            elif action == RecoveryAction.PAUSE_TRADING:
                self._pause_trading(hours=1)
            
            elif action == RecoveryAction.REDUCE_EXPOSURE:
                self._reduce_exposure()
            
            event.recovered = True
            event.recovery_time = datetime.now()
            logger.info(f"Recuperação executada: {action.value}")
            
        except Exception as e:
            logger.error(f"Erro na recuperação: {e}")
    
    def _attempt_reconnect(self, source: str):
        """Tenta reconectar"""
        for attempt in range(self.reconnect_attempts):
            try:
                if source == 'mt5' and self.mt5:
                    import MetaTrader5 as mt5
                    
                    # Desconectar
                    mt5.shutdown()
                    time.sleep(2)
                    
                    # Reconectar
                    if mt5.initialize():
                        logger.info(f"Reconexão MT5 bem-sucedida (tentativa {attempt + 1})")
                        cb = self.circuit_breakers.get('mt5_connection')
                        if cb:
                            cb.record_success()
                        return
                
                time.sleep(5 * (attempt + 1))  # Backoff
                
            except Exception as e:
                logger.warning(f"Tentativa {attempt + 1} falhou: {e}")
        
        logger.error(f"Todas as {self.reconnect_attempts} tentativas de reconexão falharam")
    
    def _close_all_positions(self):
        """Fecha todas as posições"""
        if not self.mt5:
            logger.warning("MT5 não disponível para fechar posições")
            return
        
        try:
            import MetaTrader5 as mt5
            
            positions = mt5.positions_get()
            if positions:
                logger.warning(f"FECHANDO {len(positions)} POSIÇÕES DE EMERGÊNCIA")
                
                for pos in positions:
                    # Determinar tipo de ordem de fechamento
                    close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos.symbol,
                        "volume": pos.volume,
                        "type": close_type,
                        "position": pos.ticket,
                        "magic": pos.magic,
                        "comment": "emergency_close"
                    }
                    
                    result = mt5.order_send(request)
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"Posição {pos.ticket} fechada")
                    else:
                        logger.error(f"Erro ao fechar {pos.ticket}: {result.retcode}")
                        
        except Exception as e:
            logger.error(f"Erro ao fechar posições: {e}")
    
    def _pause_trading(self, hours: float):
        """Pausa trading"""
        self.trading_paused = True
        self.pause_until = datetime.now() + timedelta(hours=hours)
        logger.warning(f"Trading PAUSADO até {self.pause_until}")
    
    def _reduce_exposure(self):
        """Reduz exposição"""
        if not self.mt5:
            return
        
        try:
            import MetaTrader5 as mt5
            
            positions = mt5.positions_get()
            if positions:
                # Fechar metade das posições (as menores)
                sorted_positions = sorted(positions, key=lambda p: abs(p.profit))
                to_close = sorted_positions[:len(sorted_positions) // 2]
                
                logger.warning(f"Reduzindo exposição: fechando {len(to_close)} posições")
                
                for pos in to_close:
                    close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos.symbol,
                        "volume": pos.volume,
                        "type": close_type,
                        "position": pos.ticket,
                        "magic": pos.magic,
                        "comment": "reduce_exposure"
                    }
                    
                    mt5.order_send(request)
                    
        except Exception as e:
            logger.error(f"Erro ao reduzir exposição: {e}")
    
    def _send_alert(self, event: DisasterEvent):
        """Envia alerta"""
        # Executar callbacks
        for callback in self.alert_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Erro em callback de alerta: {e}")
        
        # Log estruturado para alertas externos
        alert_data = {
            'type': event.type.value,
            'severity': event.severity,
            'message': event.message,
            'timestamp': event.timestamp.isoformat(),
            'action': event.recovery_action.value if event.recovery_action else None
        }
        
        logger.critical(f"ALERT: {alert_data}")
    
    def _monitor_loop(self):
        """Loop de monitoramento"""
        while self.running:
            try:
                time.sleep(10)  # Check a cada 10s
                
                if not self.running:
                    break
                
                # Verificar conexão MT5
                if self.mt5:
                    try:
                        import MetaTrader5 as mt5
                        if not mt5.terminal_info():
                            self.report_connection_loss('mt5')
                        else:
                            cb = self.circuit_breakers.get('mt5_connection')
                            if cb:
                                cb.record_success()
                    except:
                        self.report_connection_loss('mt5')
                
            except Exception as e:
                logger.error(f"Erro no monitor loop: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do sistema de recovery"""
        return {
            'trading_paused': self.trading_paused,
            'pause_until': self.pause_until.isoformat() if self.pause_until else None,
            'recent_events': len(self.events),
            'recent_losses': len(self.recent_losses),
            'circuit_breakers': {
                name: {
                    'is_open': cb.state.is_open,
                    'failure_count': cb.state.failure_count,
                    'cooldown_until': cb.state.cooldown_until.isoformat() if cb.state.cooldown_until else None
                }
                for name, cb in self.circuit_breakers.items()
            }
        }
    
    def get_recent_events(self, limit: int = 10) -> List[DisasterEvent]:
        """Retorna eventos recentes"""
        return self.events[-limit:]


# Instância global
_disaster_recovery: Optional[DisasterRecovery] = None


def get_disaster_recovery(config: Dict[str, Any] = None, state_manager = None, mt5 = None) -> DisasterRecovery:
    """Retorna instância singleton"""
    global _disaster_recovery
    if _disaster_recovery is None:
        _disaster_recovery = DisasterRecovery(config, state_manager, mt5)
    return _disaster_recovery


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Criar sistema
    dr = get_disaster_recovery({
        'max_drawdown': 0.05,
        'max_daily_loss': 0.03
    })
    
    dr.start()
    
    # Simular eventos
    dr.report_trade_result(-50, 'XAUUSD')
    dr.report_drawdown(0.03)
    
    print("Status:", dr.get_status())
    
    dr.stop()
