"""
Circuit Breaker Pattern
Protege o sistema contra falhas em cascata

Estados:
- CLOSED: Sistema funcionando normalmente
- OPEN: Sistema bloqueado após falhas consecutivas
- HALF_OPEN: Testando se sistema se recuperou
"""
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional, Dict, Any
from loguru import logger
from functools import wraps


class CircuitState(Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"       # Normal - permite chamadas
    OPEN = "open"           # Bloqueado - rejeita chamadas
    HALF_OPEN = "half_open" # Testando - permite 1 chamada de teste


class CircuitBreakerError(Exception):
    """Erro quando circuit breaker está aberto"""
    pass


class CircuitBreaker:
    """
    Circuit Breaker para proteção contra falhas em cascata
    
    Uso:
        cb = CircuitBreaker("mt5_connection", failure_threshold=5, recovery_timeout=60)
        
        with cb:
            result = mt5.connect()
        
        # Ou como decorator
        @cb
        def connect_mt5():
            return mt5.initialize()
    """
    
    # Registro global de circuit breakers
    _instances: Dict[str, 'CircuitBreaker'] = {}
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        excluded_exceptions: tuple = ()
    ):
        """
        Inicializa Circuit Breaker
        
        Args:
            name: Nome identificador do circuito
            failure_threshold: Número de falhas para abrir o circuito
            success_threshold: Número de sucessos em HALF_OPEN para fechar
            recovery_timeout: Tempo em segundos antes de tentar HALF_OPEN
            half_open_max_calls: Número máximo de chamadas em HALF_OPEN
            excluded_exceptions: Exceções que NÃO contam como falha
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.excluded_exceptions = excluded_exceptions
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change: datetime = datetime.now()
        
        self._lock = threading.RLock()
        
        # Registrar instância globalmente
        CircuitBreaker._instances[name] = self
        
        logger.info(
            f"🔌 Circuit Breaker '{name}' criado | "
            f"Threshold: {failure_threshold} falhas | "
            f"Recovery: {recovery_timeout}s"
        )
    
    @classmethod
    def get(cls, name: str) -> Optional['CircuitBreaker']:
        """Obtém circuit breaker por nome"""
        return cls._instances.get(name)
    
    @classmethod
    def get_all_status(cls) -> Dict[str, Dict[str, Any]]:
        """Retorna status de todos os circuit breakers"""
        return {
            name: cb.get_status()
            for name, cb in cls._instances.items()
        }
    
    @property
    def state(self) -> CircuitState:
        """Retorna estado atual, atualizando se necessário"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Verificar se é hora de tentar HALF_OPEN
                if self._should_attempt_reset():
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state
    
    def _should_attempt_reset(self) -> bool:
        """Verifica se deve tentar resetar o circuito"""
        if self._last_failure_time is None:
            return True
        
        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _transition_to(self, new_state: CircuitState):
        """Transição de estado com logging"""
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now()
        
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0
        
        if old_state != new_state:
            emoji = {
                CircuitState.CLOSED: "✅",
                CircuitState.OPEN: "🔴",
                CircuitState.HALF_OPEN: "🟡"
            }
            logger.warning(
                f"🔌 Circuit '{self.name}' {emoji.get(old_state, '')} {old_state.value} → "
                f"{emoji.get(new_state, '')} {new_state.value}"
            )
    
    def record_success(self):
        """Registra chamada bem-sucedida"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"🔌 Circuit '{self.name}' sucesso em HALF_OPEN "
                    f"({self._success_count}/{self.success_threshold})"
                )
                
                if self._success_count >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    self._failure_count = 0
                    logger.success(
                        f"✅ Circuit '{self.name}' RECUPERADO após "
                        f"{self._success_count} sucessos consecutivos"
                    )
            
            elif self._state == CircuitState.CLOSED:
                # Reset contador de falhas em sucesso
                if self._failure_count > 0:
                    self._failure_count = max(0, self._failure_count - 1)
    
    def record_failure(self, exception: Optional[Exception] = None):
        """Registra falha"""
        with self._lock:
            # Verificar se exceção está excluída
            if exception and isinstance(exception, self.excluded_exceptions):
                logger.debug(
                    f"🔌 Circuit '{self.name}' exceção excluída: {type(exception).__name__}"
                )
                return
            
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            
            if self._state == CircuitState.HALF_OPEN:
                # Falha em HALF_OPEN volta para OPEN
                self._transition_to(CircuitState.OPEN)
                logger.error(
                    f"🔴 Circuit '{self.name}' falhou em HALF_OPEN - voltando para OPEN"
                )
            
            elif self._state == CircuitState.CLOSED:
                logger.warning(
                    f"🔌 Circuit '{self.name}' falha {self._failure_count}/{self.failure_threshold}"
                )
                
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    logger.error(
                        f"🔴 Circuit '{self.name}' ABERTO após "
                        f"{self._failure_count} falhas consecutivas | "
                        f"Próxima tentativa em {self.recovery_timeout}s"
                    )
    
    def is_available(self) -> bool:
        """Verifica se o circuito permite chamadas"""
        current_state = self.state
        
        if current_state == CircuitState.CLOSED:
            return True
        
        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
        
        # OPEN
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do circuit breaker"""
        with self._lock:
            time_in_state = (datetime.now() - self._last_state_change).total_seconds()
            
            status = {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "time_in_state_seconds": round(time_in_state, 1),
                "is_available": self.is_available(),
            }
            
            if self._state == CircuitState.OPEN and self._last_failure_time:
                remaining = self.recovery_timeout - (datetime.now() - self._last_failure_time).total_seconds()
                status["recovery_remaining_seconds"] = max(0, round(remaining, 1))
            
            if self._state == CircuitState.HALF_OPEN:
                status["success_count"] = self._success_count
                status["success_threshold"] = self.success_threshold
            
            return status
    
    def reset(self):
        """Reset manual do circuit breaker"""
        with self._lock:
            old_state = self._state
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_state_change = datetime.now()
            
            logger.info(
                f"🔌 Circuit '{self.name}' RESET manual | "
                f"{old_state.value} → CLOSED"
            )
    
    def force_open(self, duration_seconds: Optional[int] = None):
        """Força abertura do circuit breaker"""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            self._last_failure_time = datetime.now()
            
            if duration_seconds:
                # Ajustar recovery timeout temporariamente
                original_timeout = self.recovery_timeout
                self.recovery_timeout = duration_seconds
                logger.warning(
                    f"🔴 Circuit '{self.name}' forçado OPEN por {duration_seconds}s"
                )
            else:
                logger.warning(f"🔴 Circuit '{self.name}' forçado OPEN")
    
    def __enter__(self):
        """Context manager - entrada"""
        if not self.is_available():
            raise CircuitBreakerError(
                f"Circuit '{self.name}' está ABERTO - operação bloqueada"
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager - saída"""
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure(exc_val)
        return False  # Não suprime exceção
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.is_available():
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' está ABERTO - {func.__name__} bloqueado"
                )
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure(e)
                raise
        
        return wrapper


# Circuit breakers pré-configurados para o bot
class BotCircuitBreakers:
    """Factory para circuit breakers do bot"""
    
    # MT5 Connection
    MT5_CONNECTION = CircuitBreaker(
        name="mt5_connection",
        failure_threshold=5,
        success_threshold=3,
        recovery_timeout=120,  # 2 minutos
    )
    
    # MT5 Trade Operations
    MT5_TRADE = CircuitBreaker(
        name="mt5_trade",
        failure_threshold=3,
        success_threshold=2,
        recovery_timeout=60,  # 1 minuto
    )
    
    # Telegram Notifications
    TELEGRAM = CircuitBreaker(
        name="telegram",
        failure_threshold=5,
        success_threshold=2,
        recovery_timeout=300,  # 5 minutos
    )
    
    # External APIs (News, Macro)
    EXTERNAL_API = CircuitBreaker(
        name="external_api",
        failure_threshold=5,
        success_threshold=3,
        recovery_timeout=180,  # 3 minutos
    )
    
    # Database Operations
    DATABASE = CircuitBreaker(
        name="database",
        failure_threshold=3,
        success_threshold=2,
        recovery_timeout=30,
    )
    
    @classmethod
    def get_all_status(cls) -> Dict[str, Dict[str, Any]]:
        """Retorna status de todos os circuit breakers"""
        return CircuitBreaker.get_all_status()
    
    @classmethod
    def reset_all(cls):
        """Reset todos os circuit breakers"""
        for name, cb in CircuitBreaker._instances.items():
            cb.reset()
        logger.info("🔌 Todos os Circuit Breakers resetados")


# Exemplo de uso:
"""
from core.circuit_breaker import BotCircuitBreakers, CircuitBreakerError

# Como context manager
try:
    with BotCircuitBreakers.MT5_CONNECTION:
        mt5.initialize()
except CircuitBreakerError:
    logger.error("MT5 bloqueado pelo circuit breaker")

# Como decorator
@BotCircuitBreakers.MT5_TRADE
def place_order(symbol, type, volume):
    return mt5.order_send(request)

# Verificar disponibilidade
if BotCircuitBreakers.MT5_CONNECTION.is_available():
    # Pode tentar conectar
    pass

# Status de todos
status = BotCircuitBreakers.get_all_status()
"""
