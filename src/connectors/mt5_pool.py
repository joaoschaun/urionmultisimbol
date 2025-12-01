# -*- coding: utf-8 -*-
"""
MT5 Connection Pool - Gerenciador de Conexões MT5 com Pool

Implementa:
- Pool de conexões reutilizáveis
- Reconexão automática
- Health checks periódicos
- Thread safety
- Métricas de uso
"""

import MetaTrader5 as mt5
import threading
import queue
import time
import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from contextlib import contextmanager
import atexit

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Estados possíveis de uma conexão"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    STALE = "stale"


@dataclass
class ConnectionMetrics:
    """Métricas de uma conexão"""
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    total_uses: int = 0
    total_errors: int = 0
    consecutive_errors: int = 0
    total_reconnects: int = 0
    avg_response_time: float = 0.0
    last_health_check: Optional[datetime] = None


@dataclass 
class PoolMetrics:
    """Métricas do pool de conexões"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    total_requests: int = 0
    total_timeouts: int = 0
    total_errors: int = 0
    avg_wait_time: float = 0.0
    uptime_start: datetime = field(default_factory=datetime.now)


class MT5Connection:
    """
    Wrapper para uma conexão MT5 individual
    """
    
    def __init__(self, connection_id: int, config: Dict[str, Any]):
        self.connection_id = connection_id
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.metrics = ConnectionMetrics()
        self._lock = threading.Lock()
        self._in_use = False
        
    def connect(self) -> bool:
        """Estabelece conexão com MT5"""
        with self._lock:
            if self.state == ConnectionState.CONNECTED:
                return True
            
            self.state = ConnectionState.CONNECTING
            
            try:
                # Inicializa MT5
                if not mt5.initialize(
                    path=self.config.get('path'),
                    login=self.config.get('login'),
                    password=self.config.get('password'),
                    server=self.config.get('server'),
                    timeout=self.config.get('timeout', 60000),
                    portable=self.config.get('portable', False)
                ):
                    error = mt5.last_error()
                    logger.error(f"Falha ao conectar MT5 (conn {self.connection_id}): {error}")
                    self.state = ConnectionState.ERROR
                    self.metrics.total_errors += 1
                    self.metrics.consecutive_errors += 1
                    return False
                
                self.state = ConnectionState.CONNECTED
                self.metrics.consecutive_errors = 0
                self.metrics.last_used = datetime.now()
                logger.info(f"Conexão MT5 {self.connection_id} estabelecida")
                return True
                
            except Exception as e:
                logger.error(f"Exceção ao conectar MT5 (conn {self.connection_id}): {e}")
                self.state = ConnectionState.ERROR
                self.metrics.total_errors += 1
                self.metrics.consecutive_errors += 1
                return False
    
    def disconnect(self) -> bool:
        """Desconecta do MT5"""
        with self._lock:
            try:
                mt5.shutdown()
                self.state = ConnectionState.DISCONNECTED
                logger.info(f"Conexão MT5 {self.connection_id} encerrada")
                return True
            except Exception as e:
                logger.error(f"Erro ao desconectar MT5 (conn {self.connection_id}): {e}")
                return False
    
    def reconnect(self) -> bool:
        """Reconecta ao MT5"""
        self.disconnect()
        time.sleep(0.5)  # Pequeno delay antes de reconectar
        result = self.connect()
        if result:
            self.metrics.total_reconnects += 1
        return result
    
    def health_check(self) -> bool:
        """Verifica se a conexão está saudável"""
        with self._lock:
            if self.state != ConnectionState.CONNECTED:
                return False
            
            try:
                start = time.time()
                terminal_info = mt5.terminal_info()
                elapsed = time.time() - start
                
                if terminal_info is None:
                    self.state = ConnectionState.STALE
                    return False
                
                # Atualiza métricas
                self.metrics.last_health_check = datetime.now()
                self._update_response_time(elapsed)
                
                return terminal_info.connected
                
            except Exception as e:
                logger.error(f"Health check falhou (conn {self.connection_id}): {e}")
                self.state = ConnectionState.ERROR
                return False
    
    def _update_response_time(self, new_time: float):
        """Atualiza tempo médio de resposta"""
        if self.metrics.avg_response_time == 0:
            self.metrics.avg_response_time = new_time
        else:
            # Média móvel exponencial
            self.metrics.avg_response_time = 0.9 * self.metrics.avg_response_time + 0.1 * new_time
    
    def acquire(self) -> bool:
        """Marca conexão como em uso"""
        with self._lock:
            if self._in_use:
                return False
            self._in_use = True
            self.metrics.total_uses += 1
            self.metrics.last_used = datetime.now()
            return True
    
    def release(self):
        """Libera conexão para reuso"""
        with self._lock:
            self._in_use = False
    
    @property
    def is_available(self) -> bool:
        """Verifica se conexão está disponível"""
        return (
            not self._in_use and 
            self.state == ConnectionState.CONNECTED
        )
    
    @property
    def is_healthy(self) -> bool:
        """Verifica se conexão está saudável"""
        return (
            self.state == ConnectionState.CONNECTED and
            self.metrics.consecutive_errors < 3
        )


class MT5ConnectionPool:
    """
    Pool de conexões MT5 com gerenciamento automático
    
    Features:
    - Pool configurável de conexões
    - Reconexão automática
    - Health checks periódicos
    - Retry com backoff exponencial
    - Métricas de uso
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        min_connections: int = 1,
        max_connections: int = 5,
        connection_timeout: float = 30.0,
        health_check_interval: float = 60.0,
        max_idle_time: float = 300.0
    ):
        """
        Inicializa o pool de conexões
        
        Args:
            config: Configuração da conta MT5 (login, password, server, path)
            min_connections: Mínimo de conexões a manter
            max_connections: Máximo de conexões permitidas
            connection_timeout: Timeout para obter conexão (segundos)
            health_check_interval: Intervalo entre health checks (segundos)
            max_idle_time: Tempo máximo de ociosidade antes de fechar conexão
        """
        self.config = config
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.health_check_interval = health_check_interval
        self.max_idle_time = max_idle_time
        
        # Pool de conexões
        self._connections: List[MT5Connection] = []
        self._connection_queue: queue.Queue = queue.Queue()
        self._lock = threading.RLock()
        
        # Métricas
        self.metrics = PoolMetrics()
        
        # Thread de health check
        self._health_check_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Callback para eventos
        self._on_connection_error: Optional[Callable] = None
        self._on_reconnect: Optional[Callable] = None
        
        logger.info(f"MT5ConnectionPool inicializado (min={min_connections}, max={max_connections})")
    
    def start(self) -> bool:
        """Inicia o pool de conexões"""
        with self._lock:
            if self._running:
                return True
            
            self._running = True
            
            # Cria conexões mínimas
            for i in range(self.min_connections):
                conn = self._create_connection()
                if conn and conn.connect():
                    self._connections.append(conn)
                    self._connection_queue.put(conn)
            
            # Inicia health check thread
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop,
                daemon=True,
                name="MT5-HealthCheck"
            )
            self._health_check_thread.start()
            
            # Registra shutdown
            atexit.register(self.stop)
            
            self._update_metrics()
            logger.info(f"Pool iniciado com {len(self._connections)} conexões")
            
            return len(self._connections) > 0
    
    def stop(self):
        """Para o pool e fecha todas as conexões"""
        with self._lock:
            self._running = False
            
            for conn in self._connections:
                try:
                    conn.disconnect()
                except:
                    pass
            
            self._connections.clear()
            
            # Limpa queue
            while not self._connection_queue.empty():
                try:
                    self._connection_queue.get_nowait()
                except queue.Empty:
                    break
            
            logger.info("Pool de conexões MT5 encerrado")
    
    def _create_connection(self) -> Optional[MT5Connection]:
        """Cria nova conexão"""
        connection_id = len(self._connections)
        return MT5Connection(connection_id, self.config)
    
    def _get_available_connection(self) -> Optional[MT5Connection]:
        """Obtém conexão disponível do pool"""
        for conn in self._connections:
            if conn.is_available and conn.acquire():
                return conn
        return None
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obter conexão do pool
        
        Usage:
            with pool.get_connection() as conn:
                if conn:
                    # usar conexão
        """
        conn = None
        start_time = time.time()
        
        try:
            # Tenta obter conexão existente
            with self._lock:
                conn = self._get_available_connection()
                
                # Se não há disponível, tenta criar nova
                if not conn and len(self._connections) < self.max_connections:
                    new_conn = self._create_connection()
                    if new_conn and new_conn.connect():
                        new_conn.acquire()
                        self._connections.append(new_conn)
                        conn = new_conn
            
            # Se ainda não tem, espera por uma
            if not conn:
                try:
                    conn = self._connection_queue.get(timeout=self.connection_timeout)
                    if conn:
                        conn.acquire()
                except queue.Empty:
                    self.metrics.total_timeouts += 1
                    logger.warning("Timeout ao aguardar conexão MT5")
            
            self.metrics.total_requests += 1
            wait_time = time.time() - start_time
            self._update_wait_time(wait_time)
            
            yield conn
            
        except Exception as e:
            logger.error(f"Erro ao obter conexão: {e}")
            self.metrics.total_errors += 1
            yield None
            
        finally:
            if conn:
                conn.release()
                # Devolve para a fila se ainda saudável
                if conn.is_healthy:
                    self._connection_queue.put(conn)
            self._update_metrics()
    
    def execute(self, func: Callable, *args, retries: int = 3, **kwargs) -> Any:
        """
        Executa função com conexão do pool
        
        Args:
            func: Função a executar (recebe conexão como primeiro arg)
            *args: Argumentos para a função
            retries: Número de tentativas em caso de erro
            **kwargs: Kwargs para a função
            
        Returns:
            Resultado da função
        """
        last_error = None
        
        for attempt in range(retries):
            with self.get_connection() as conn:
                if not conn:
                    time.sleep(0.5 * (attempt + 1))  # Backoff
                    continue
                
                try:
                    result = func(conn, *args, **kwargs)
                    return result
                    
                except Exception as e:
                    last_error = e
                    conn.metrics.total_errors += 1
                    conn.metrics.consecutive_errors += 1
                    
                    logger.warning(f"Erro na execução (tentativa {attempt + 1}/{retries}): {e}")
                    
                    # Tenta reconectar se muitos erros
                    if conn.metrics.consecutive_errors >= 3:
                        conn.reconnect()
                    
                    time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
        
        if last_error:
            raise last_error
        return None
    
    def _health_check_loop(self):
        """Loop de health check em background"""
        while self._running:
            try:
                time.sleep(self.health_check_interval)
                
                if not self._running:
                    break
                
                self._perform_health_checks()
                self._cleanup_stale_connections()
                self._ensure_min_connections()
                
            except Exception as e:
                logger.error(f"Erro no health check loop: {e}")
    
    def _perform_health_checks(self):
        """Executa health check em todas as conexões"""
        with self._lock:
            for conn in self._connections:
                if not conn._in_use:
                    if not conn.health_check():
                        logger.warning(f"Conexão {conn.connection_id} falhou health check")
                        
                        # Tenta reconectar
                        if conn.reconnect():
                            logger.info(f"Conexão {conn.connection_id} reconectada")
                            if self._on_reconnect:
                                self._on_reconnect(conn)
                        else:
                            if self._on_connection_error:
                                self._on_connection_error(conn)
    
    def _cleanup_stale_connections(self):
        """Remove conexões ociosas além do mínimo"""
        with self._lock:
            now = datetime.now()
            
            if len(self._connections) <= self.min_connections:
                return
            
            stale_connections = []
            for conn in self._connections:
                if not conn._in_use:
                    idle_time = (now - conn.metrics.last_used).total_seconds()
                    if idle_time > self.max_idle_time:
                        stale_connections.append(conn)
            
            # Remove conexões ociosas (mantém mínimo)
            for conn in stale_connections:
                if len(self._connections) > self.min_connections:
                    conn.disconnect()
                    self._connections.remove(conn)
                    logger.info(f"Conexão {conn.connection_id} removida por ociosidade")
    
    def _ensure_min_connections(self):
        """Garante mínimo de conexões saudáveis"""
        with self._lock:
            healthy_count = sum(1 for c in self._connections if c.is_healthy)
            
            while healthy_count < self.min_connections:
                new_conn = self._create_connection()
                if new_conn and new_conn.connect():
                    self._connections.append(new_conn)
                    self._connection_queue.put(new_conn)
                    healthy_count += 1
                else:
                    break
    
    def _update_wait_time(self, new_time: float):
        """Atualiza tempo médio de espera"""
        if self.metrics.avg_wait_time == 0:
            self.metrics.avg_wait_time = new_time
        else:
            self.metrics.avg_wait_time = 0.9 * self.metrics.avg_wait_time + 0.1 * new_time
    
    def _update_metrics(self):
        """Atualiza métricas do pool"""
        with self._lock:
            self.metrics.total_connections = len(self._connections)
            self.metrics.active_connections = sum(1 for c in self._connections if c._in_use)
            self.metrics.idle_connections = sum(1 for c in self._connections if c.is_available)
    
    def set_on_connection_error(self, callback: Callable):
        """Define callback para erros de conexão"""
        self._on_connection_error = callback
    
    def set_on_reconnect(self, callback: Callable):
        """Define callback para reconexões"""
        self._on_reconnect = callback
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do pool"""
        self._update_metrics()
        
        uptime = (datetime.now() - self.metrics.uptime_start).total_seconds()
        
        connection_stats = []
        for conn in self._connections:
            connection_stats.append({
                'id': conn.connection_id,
                'state': conn.state.value,
                'in_use': conn._in_use,
                'total_uses': conn.metrics.total_uses,
                'total_errors': conn.metrics.total_errors,
                'avg_response_time': round(conn.metrics.avg_response_time * 1000, 2),
                'reconnects': conn.metrics.total_reconnects
            })
        
        return {
            'pool': {
                'total_connections': self.metrics.total_connections,
                'active_connections': self.metrics.active_connections,
                'idle_connections': self.metrics.idle_connections,
                'total_requests': self.metrics.total_requests,
                'total_timeouts': self.metrics.total_timeouts,
                'total_errors': self.metrics.total_errors,
                'avg_wait_time_ms': round(self.metrics.avg_wait_time * 1000, 2),
                'uptime_seconds': round(uptime, 0)
            },
            'connections': connection_stats,
            'config': {
                'min_connections': self.min_connections,
                'max_connections': self.max_connections,
                'connection_timeout': self.connection_timeout,
                'health_check_interval': self.health_check_interval
            }
        }


# Instância global
_mt5_pool: Optional[MT5ConnectionPool] = None


def get_mt5_pool(config: Optional[Dict[str, Any]] = None) -> MT5ConnectionPool:
    """
    Retorna instância singleton do pool MT5
    
    Args:
        config: Configuração MT5 (necessário na primeira chamada)
        
    Returns:
        MT5ConnectionPool instance
    """
    global _mt5_pool
    
    if _mt5_pool is None:
        if config is None:
            raise ValueError("Config é necessário na primeira inicialização do pool")
        _mt5_pool = MT5ConnectionPool(config)
    
    return _mt5_pool


def initialize_pool(config: Dict[str, Any], **kwargs) -> MT5ConnectionPool:
    """
    Inicializa e inicia o pool de conexões
    
    Args:
        config: Configuração MT5
        **kwargs: Argumentos adicionais para MT5ConnectionPool
        
    Returns:
        MT5ConnectionPool inicializado
    """
    global _mt5_pool
    
    _mt5_pool = MT5ConnectionPool(config, **kwargs)
    _mt5_pool.start()
    
    return _mt5_pool


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Configuração de exemplo
    config = {
        'login': 12345678,
        'password': 'sua_senha',
        'server': 'seu_broker-server',
        'path': r'C:\Program Files\MetaTrader 5\terminal64.exe'
    }
    
    # Cria e inicia pool
    pool = initialize_pool(
        config,
        min_connections=1,
        max_connections=3,
        health_check_interval=30.0
    )
    
    # Usa conexão
    def get_account_info(conn):
        info = mt5.account_info()
        return info._asdict() if info else None
    
    try:
        result = pool.execute(get_account_info)
        print(f"Account info: {result}")
        
        # Ou via context manager
        with pool.get_connection() as conn:
            if conn:
                symbols = mt5.symbols_get()
                print(f"Total symbols: {len(symbols) if symbols else 0}")
        
        # Estatísticas
        stats = pool.get_stats()
        print(f"Pool stats: {stats}")
        
    finally:
        pool.stop()
