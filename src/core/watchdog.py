"""
System Watchdog
Monitora threads e processos para detectar freezes e deadlocks
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Callable
from loguru import logger


class ThreadWatchdog:
    """
    Watchdog para monitorar threads e detectar freezes
    
    Cada thread monitorada deve fazer "heartbeat" periodicamente.
    Se não houver heartbeat por X segundos, watchdog detecta freeze.
    """
    
    def __init__(self, timeout_seconds: int = 300):
        """
        Inicializa watchdog
        
        Args:
            timeout_seconds: Tempo sem heartbeat para considerar freeze (padrão 5min)
        """
        self.timeout_seconds = timeout_seconds
        self.threads: Dict[str, datetime] = {}
        self.callbacks: Dict[str, Callable] = {}
        self.running = False
        self.monitor_thread = None
        
        logger.info(f"ThreadWatchdog inicializado (timeout: {timeout_seconds}s)")
    
    def register_thread(self, thread_name: str, callback: Callable = None):
        """
        Registra thread para monitoramento
        
        Args:
            thread_name: Nome da thread
            callback: Função a executar se thread congelar (opcional)
        """
        self.threads[thread_name] = datetime.now()
        if callback:
            self.callbacks[thread_name] = callback
        
        logger.info(f"Thread registrada no watchdog: {thread_name}")
    
    def heartbeat(self, thread_name: str):
        """
        Atualiza heartbeat de uma thread
        Thread deve chamar isto periodicamente para indicar que está viva
        
        Args:
            thread_name: Nome da thread
        """
        if thread_name in self.threads:
            self.threads[thread_name] = datetime.now()
    
    def _monitor_loop(self):
        """Loop de monitoramento interno"""
        logger.info("Watchdog monitor loop iniciado")
        
        while self.running:
            try:
                now = datetime.now()
                
                for thread_name, last_heartbeat in self.threads.items():
                    # Calcular tempo desde último heartbeat
                    elapsed = (now - last_heartbeat).total_seconds()
                    
                    if elapsed > self.timeout_seconds:
                        # Thread congelada detectada!
                        logger.error(
                            f"⚠️ FREEZE DETECTADO: Thread '{thread_name}' "
                            f"sem heartbeat há {elapsed:.0f}s "
                            f"(timeout: {self.timeout_seconds}s)"
                        )
                        
                        # Executar callback se definido
                        if thread_name in self.callbacks:
                            try:
                                logger.warning(
                                    f"Executando callback de recovery para '{thread_name}'"
                                )
                                self.callbacks[thread_name]()
                            except Exception as e:
                                logger.exception(
                                    f"Erro ao executar callback de '{thread_name}': {e}"
                                )
                        
                        # Reset heartbeat para evitar spam de alertas
                        self.threads[thread_name] = now
                
                # Check a cada 30 segundos
                time.sleep(30)
                
            except Exception as e:
                logger.exception(f"Erro no watchdog monitor loop: {e}")
                time.sleep(30)
        
        logger.info("Watchdog monitor loop finalizado")
    
    def start(self):
        """Inicia monitoramento"""
        if self.running:
            logger.warning("Watchdog já está rodando")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="WatchdogMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.success("Watchdog iniciado")
    
    def stop(self):
        """Para monitoramento"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Watchdog parado")
    
    def get_status(self) -> Dict[str, dict]:
        """
        Retorna status de todas threads monitoradas
        
        Returns:
            Dict com thread_name: {last_heartbeat, elapsed_seconds, is_frozen}
        """
        now = datetime.now()
        status = {}
        
        for thread_name, last_heartbeat in self.threads.items():
            elapsed = (now - last_heartbeat).total_seconds()
            status[thread_name] = {
                'last_heartbeat': last_heartbeat.isoformat(),
                'elapsed_seconds': elapsed,
                'is_frozen': elapsed > self.timeout_seconds
            }
        
        return status


class ProcessHealthCheck:
    """
    Health check para serviços externos (MT5, APIs, etc)
    """
    
    def __init__(self, check_interval: int = 60):
        """
        Inicializa health checker
        
        Args:
            check_interval: Intervalo entre checks (segundos)
        """
        self.check_interval = check_interval
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, bool] = {}
        self.running = False
        self.check_thread = None
        
        logger.info(f"ProcessHealthCheck inicializado (intervalo: {check_interval}s)")
    
    def register_check(self, name: str, check_func: Callable[[], bool]):
        """
        Registra health check
        
        Args:
            name: Nome do check
            check_func: Função que retorna True se saudável, False se não
        """
        self.checks[name] = check_func
        self.last_results[name] = None
        
        logger.info(f"Health check registrado: {name}")
    
    def _check_loop(self):
        """Loop de checks interno"""
        logger.info("Health check loop iniciado")
        
        while self.running:
            try:
                for name, check_func in self.checks.items():
                    try:
                        # Executar check
                        is_healthy = check_func()
                        
                        # Comparar com resultado anterior
                        previous = self.last_results.get(name)
                        
                        if is_healthy and previous is False:
                            logger.success(f"✅ {name}: Recuperado")
                        elif not is_healthy and previous is not False:
                            logger.error(f"❌ {name}: Falha detectada")
                        
                        self.last_results[name] = is_healthy
                        
                    except Exception as e:
                        logger.error(f"Erro ao executar check '{name}': {e}")
                        self.last_results[name] = False
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.exception(f"Erro no health check loop: {e}")
                time.sleep(self.check_interval)
        
        logger.info("Health check loop finalizado")
    
    def start(self):
        """Inicia health checks"""
        if self.running:
            logger.warning("Health checker já está rodando")
            return
        
        self.running = True
        self.check_thread = threading.Thread(
            target=self._check_loop,
            name="HealthCheckMonitor",
            daemon=True
        )
        self.check_thread.start()
        
        logger.success("Health checker iniciado")
    
    def stop(self):
        """Para health checks"""
        if not self.running:
            return
        
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=5)
        
        logger.info("Health checker parado")
    
    def get_status(self) -> Dict[str, bool]:
        """
        Retorna status de todos os health checks
        
        Returns:
            Dict com name: is_healthy
        """
        return self.last_results.copy()
