"""
Retry Handler - Gestão inteligente de erros com retry
Implementa retry logic para operações críticas do bot
"""
import functools
import time
from typing import Callable, Type, Tuple, Optional
from loguru import logger


class RetryableError(Exception):
    """Erro que deve ser retried"""
    pass


class MT5ConnectionError(RetryableError):
    """Erro de conexão MT5"""
    pass


class MT5TradeError(RetryableError):
    """Erro em operação de trade MT5"""
    pass


class DatabaseError(RetryableError):
    """Erro de database"""
    pass


class NetworkError(RetryableError):
    """Erro de rede (APIs, Telegram)"""
    pass


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (RetryableError,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator para retry automático em caso de erro
    
    Args:
        max_attempts: Número máximo de tentativas
        delay: Delay inicial entre tentativas (segundos)
        backoff: Multiplicador de backoff (exponencial)
        exceptions: Tuple de exceções que devem ser retried
        on_retry: Callback executado antes de cada retry
    
    Usage:
        @retry_on_error(max_attempts=3, delay=1.0, exceptions=(MT5ConnectionError,))
        def place_order(...):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"❌ {func.__name__} falhou após {max_attempts} tentativas: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"⚠️ {func.__name__} falhou (tentativa {attempt}/{max_attempts}): {e}"
                    )
                    
                    # Executar callback se fornecido
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as callback_error:
                            logger.error(f"Erro no callback on_retry: {callback_error}")
                    
                    # Aguardar antes da próxima tentativa
                    logger.info(f"⏳ Aguardando {current_delay:.1f}s antes de tentar novamente...")
                    time.sleep(current_delay)
                    
                    # Backoff exponencial
                    current_delay *= backoff
                    
                except Exception as e:
                    # Erro não-retryable
                    logger.error(f"❌ {func.__name__} falhou com erro não-retryable: {e}")
                    raise
            
            # Nunca deve chegar aqui
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def retry_with_context(
    context: str,
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (RetryableError,)
):
    """
    Decorator de retry com contexto adicional para logs
    
    Args:
        context: Descrição da operação (ex: "abrir posição XAUUSD")
        max_attempts: Número máximo de tentativas
        delay: Delay entre tentativas
        exceptions: Exceções para retry
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"❌ Falha ao {context} após {max_attempts} tentativas: {e}",
                            extra={"context": context, "attempt": attempt, "error": str(e)}
                        )
                        raise
                    
                    logger.warning(
                        f"⚠️ Erro ao {context} (tentativa {attempt}/{max_attempts}): {e}",
                        extra={"context": context, "attempt": attempt}
                    )
                    
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(
                        f"❌ Erro crítico ao {context}: {e}",
                        extra={"context": context, "error": str(e)}
                    )
                    raise
                    
        return wrapper
    return decorator


class RetryContext:
    """Context manager para retry manual"""
    
    def __init__(
        self,
        operation: str,
        max_attempts: int = 3,
        delay: float = 1.0,
        exceptions: Tuple[Type[Exception], ...] = (RetryableError,)
    ):
        self.operation = operation
        self.max_attempts = max_attempts
        self.delay = delay
        self.exceptions = exceptions
        self.attempt = 0
        
    def __enter__(self):
        self.attempt += 1
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            return False
            
        if exc_type in self.exceptions:
            if self.attempt < self.max_attempts:
                logger.warning(
                    f"⚠️ {self.operation} falhou (tentativa {self.attempt}/{self.max_attempts}): {exc_value}"
                )
                time.sleep(self.delay)
                return True  # Suppress exception, retry
            else:
                logger.error(
                    f"❌ {self.operation} falhou após {self.max_attempts} tentativas: {exc_value}"
                )
                return False  # Re-raise exception
        
        # Erro não-retryable
        return False


# Exemplos de uso:
"""
# 1. Decorator simples
@retry_on_error(max_attempts=3, delay=1.0, exceptions=(MT5ConnectionError,))
def connect_mt5():
    if not mt5.initialize():
        raise MT5ConnectionError("Falha ao conectar MT5")
    return True

# 2. Decorator com contexto
@retry_with_context("abrir posição XAUUSD BUY", max_attempts=3)
def place_order(symbol, type, volume):
    result = mt5.place_order(symbol, type, volume)
    if not result:
        raise MT5TradeError("Falha ao abrir posição")
    return result

# 3. Context manager manual
for _ in range(3):
    with RetryContext("conectar ao MT5", max_attempts=3):
        if mt5.initialize():
            break
"""
