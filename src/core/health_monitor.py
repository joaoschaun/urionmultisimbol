"""
Bot Health Monitor
Monitora saúde e performance do bot em tempo real

Componentes monitorados:
- Conexão MT5
- Threads ativas
- Uso de memória
- Latência de ordens
- Falhas de componentes
"""
import threading
import time
import psutil
import os
from typing import Dict, Optional, Any, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class HealthStatus(Enum):
    """Status de saúde de um componente"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Severidade de alertas"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ComponentHealth:
    """Saúde de um componente individual"""
    name: str
    status: HealthStatus
    last_check: datetime
    message: str = ""
    latency_ms: float = 0.0
    error_count: int = 0
    details: Dict = field(default_factory=dict)


@dataclass
class HealthAlert:
    """Alerta de saúde"""
    component: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class HealthMonitor:
    """
    Monitor de saúde do bot
    
    Monitora:
    - Conexões externas (MT5, Telegram)
    - Threads do sistema
    - Recursos do sistema (CPU, Memória)
    - Latência de operações
    - Falhas e recuperações
    """
    
    def __init__(
        self,
        check_interval: int = 30,
        alert_callback: Optional[Callable[[HealthAlert], None]] = None
    ):
        """
        Inicializa o monitor
        
        Args:
            check_interval: Intervalo entre verificações em segundos
            alert_callback: Callback para alertas
        """
        self.check_interval = check_interval
        self.alert_callback = alert_callback
        
        # Estado
        self._components: Dict[str, ComponentHealth] = {}
        self._alerts: List[HealthAlert] = []
        self._checks: Dict[str, Callable[[], ComponentHealth]] = {}
        
        # Thread de monitoramento
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Métricas
        self._start_time = datetime.now()
        self._check_count = 0
        self._alert_count = 0
        
        # Thresholds
        self.thresholds = {
            "cpu_warning": 70,
            "cpu_critical": 90,
            "memory_warning": 75,
            "memory_critical": 90,
            "latency_warning_ms": 500,
            "latency_critical_ms": 2000,
            "error_warning_count": 3,
            "error_critical_count": 10,
            "thread_min": 5,
        }
        
        # Registrar checks padrão
        self._register_default_checks()
        
        logger.info(
            f"🏥 Health Monitor inicializado | "
            f"Intervalo: {check_interval}s"
        )
    
    def _register_default_checks(self):
        """Registra verificações padrão de saúde"""
        
        # Check de sistema
        self.register_check("system", self._check_system)
        
        # Check de threads
        self.register_check("threads", self._check_threads)
        
        # Check de memória do processo
        self.register_check("process_memory", self._check_process_memory)
    
    def register_check(
        self,
        name: str,
        check_fn: Callable[[], ComponentHealth]
    ):
        """
        Registra uma verificação de saúde personalizada
        
        Args:
            name: Nome do componente
            check_fn: Função que retorna ComponentHealth
        """
        with self._lock:
            self._checks[name] = check_fn
            logger.debug(f"Check registrado: {name}")
    
    def register_component(
        self,
        name: str,
        status: HealthStatus = HealthStatus.UNKNOWN,
        message: str = ""
    ):
        """
        Registra um componente para monitoramento
        
        Args:
            name: Nome do componente
            status: Status inicial
            message: Mensagem inicial
        """
        with self._lock:
            self._components[name] = ComponentHealth(
                name=name,
                status=status,
                last_check=datetime.now(),
                message=message
            )
    
    def update_component(
        self,
        name: str,
        status: HealthStatus,
        message: str = "",
        latency_ms: float = 0,
        error_count: Optional[int] = None,
        details: Optional[Dict] = None
    ):
        """
        Atualiza status de um componente
        
        Args:
            name: Nome do componente
            status: Novo status
            message: Mensagem
            latency_ms: Latência em ms
            error_count: Contagem de erros (se None, não altera)
            details: Detalhes adicionais
        """
        with self._lock:
            old_status = None
            if name in self._components:
                old_status = self._components[name].status
            
            if name not in self._components:
                self._components[name] = ComponentHealth(
                    name=name,
                    status=status,
                    last_check=datetime.now(),
                    message=message,
                    latency_ms=latency_ms,
                    error_count=error_count or 0,
                    details=details or {}
                )
            else:
                component = self._components[name]
                component.status = status
                component.message = message
                component.last_check = datetime.now()
                component.latency_ms = latency_ms
                if error_count is not None:
                    component.error_count = error_count
                if details:
                    component.details.update(details)
            
            # Verificar se precisa gerar alerta
            if old_status and old_status != status:
                self._handle_status_change(name, old_status, status, message)
    
    def _handle_status_change(
        self,
        component: str,
        old_status: HealthStatus,
        new_status: HealthStatus,
        message: str
    ):
        """Trata mudança de status de componente"""
        
        # Determinar severidade
        if new_status == HealthStatus.CRITICAL:
            severity = AlertSeverity.CRITICAL
        elif new_status == HealthStatus.DEGRADED:
            severity = AlertSeverity.WARNING
        elif old_status in (HealthStatus.CRITICAL, HealthStatus.DEGRADED):
            severity = AlertSeverity.INFO
            message = f"Recuperado: {message}"
        else:
            return  # Sem mudança significativa
        
        self._create_alert(component, severity, message)
    
    def _create_alert(
        self,
        component: str,
        severity: AlertSeverity,
        message: str
    ):
        """Cria um novo alerta"""
        alert = HealthAlert(
            component=component,
            severity=severity,
            message=message,
            timestamp=datetime.now()
        )
        
        with self._lock:
            self._alerts.append(alert)
            self._alert_count += 1
            
            # Manter apenas últimos 100 alertas
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-100:]
        
        # Callback
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Erro no callback de alerta: {e}")
        
        # Log
        emoji_map = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "🔴",
            AlertSeverity.CRITICAL: "🚨"
        }
        emoji = emoji_map.get(severity, "❓")
        logger.warning(f"{emoji} Alerta [{component}]: {message}")
    
    def _check_system(self) -> ComponentHealth:
        """Verifica saúde do sistema"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status = HealthStatus.HEALTHY
            messages = []
            
            # CPU
            if cpu_percent >= self.thresholds["cpu_critical"]:
                status = HealthStatus.CRITICAL
                messages.append(f"CPU crítica: {cpu_percent:.1f}%")
            elif cpu_percent >= self.thresholds["cpu_warning"]:
                status = HealthStatus.DEGRADED
                messages.append(f"CPU alta: {cpu_percent:.1f}%")
            
            # Memória
            if memory.percent >= self.thresholds["memory_critical"]:
                status = HealthStatus.CRITICAL
                messages.append(f"Memória crítica: {memory.percent:.1f}%")
            elif memory.percent >= self.thresholds["memory_warning"]:
                if status != HealthStatus.CRITICAL:
                    status = HealthStatus.DEGRADED
                messages.append(f"Memória alta: {memory.percent:.1f}%")
            
            message = "; ".join(messages) if messages else "Sistema normal"
            
            return ComponentHealth(
                name="system",
                status=status,
                last_check=datetime.now(),
                message=message,
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                    "disk_percent": disk.percent,
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="system",
                status=HealthStatus.UNKNOWN,
                last_check=datetime.now(),
                message=f"Erro ao verificar: {e}"
            )
    
    def _check_threads(self) -> ComponentHealth:
        """Verifica threads ativas"""
        try:
            active_threads = threading.active_count()
            thread_names = [t.name for t in threading.enumerate()]
            
            # Verificar threads esperadas
            expected = ["MainThread", "MT5", "Telegram", "Strategy"]
            found = sum(1 for exp in expected if any(exp.lower() in t.lower() for t in thread_names))
            
            status = HealthStatus.HEALTHY
            message = f"{active_threads} threads ativas"
            
            if active_threads < self.thresholds["thread_min"]:
                status = HealthStatus.DEGRADED
                message = f"Poucas threads: {active_threads}"
            
            return ComponentHealth(
                name="threads",
                status=status,
                last_check=datetime.now(),
                message=message,
                details={
                    "active_count": active_threads,
                    "thread_names": thread_names[:20],  # Limitar
                    "expected_found": found
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="threads",
                status=HealthStatus.UNKNOWN,
                last_check=datetime.now(),
                message=f"Erro: {e}"
            )
    
    def _check_process_memory(self) -> ComponentHealth:
        """Verifica memória do processo atual"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            status = HealthStatus.HEALTHY
            message = f"Usando {memory_mb:.1f} MB"
            
            # Alertar se > 500MB
            if memory_mb > 1000:
                status = HealthStatus.CRITICAL
                message = f"Memória muito alta: {memory_mb:.1f} MB"
            elif memory_mb > 500:
                status = HealthStatus.DEGRADED
                message = f"Memória elevada: {memory_mb:.1f} MB"
            
            return ComponentHealth(
                name="process_memory",
                status=status,
                last_check=datetime.now(),
                message=message,
                details={
                    "rss_mb": round(memory_mb, 2),
                    "vms_mb": round(memory_info.vms / (1024 * 1024), 2),
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="process_memory",
                status=HealthStatus.UNKNOWN,
                last_check=datetime.now(),
                message=f"Erro: {e}"
            )
    
    def run_all_checks(self) -> Dict[str, ComponentHealth]:
        """Executa todas as verificações registradas"""
        results = {}
        
        with self._lock:
            checks = self._checks.copy()
        
        for name, check_fn in checks.items():
            try:
                start = time.time()
                health = check_fn()
                health.latency_ms = (time.time() - start) * 1000
                
                self.update_component(
                    name=name,
                    status=health.status,
                    message=health.message,
                    latency_ms=health.latency_ms,
                    details=health.details
                )
                
                results[name] = health
                
            except Exception as e:
                logger.error(f"Erro no check {name}: {e}")
                results[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    last_check=datetime.now(),
                    message=f"Erro: {e}"
                )
        
        self._check_count += 1
        return results
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Retorna saúde geral do bot"""
        with self._lock:
            components = list(self._components.values())
        
        if not components:
            return {
                "status": "unknown",
                "message": "Nenhum componente registrado",
                "components": 0
            }
        
        # Determinar status geral
        statuses = [c.status for c in components]
        
        if HealthStatus.CRITICAL in statuses:
            overall = HealthStatus.CRITICAL
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        elif HealthStatus.UNKNOWN in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY
        
        # Componentes problemáticos
        issues = [
            c for c in components 
            if c.status in (HealthStatus.CRITICAL, HealthStatus.DEGRADED)
        ]
        
        # Uptime
        uptime = datetime.now() - self._start_time
        
        return {
            "status": overall.value,
            "healthy_components": len([c for c in components if c.status == HealthStatus.HEALTHY]),
            "total_components": len(components),
            "issues": [
                {
                    "component": c.name,
                    "status": c.status.value,
                    "message": c.message
                }
                for c in issues
            ],
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": str(uptime).split('.')[0],
            "check_count": self._check_count,
            "alert_count": self._alert_count,
            "last_check": datetime.now().isoformat()
        }
    
    def get_component_health(self, name: str) -> Optional[Dict]:
        """Retorna saúde de um componente específico"""
        with self._lock:
            if name not in self._components:
                return None
            
            c = self._components[name]
            return {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
                "latency_ms": c.latency_ms,
                "error_count": c.error_count,
                "last_check": c.last_check.isoformat(),
                "details": c.details
            }
    
    def get_all_components(self) -> List[Dict]:
        """Retorna saúde de todos os componentes"""
        with self._lock:
            return [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 2),
                    "last_check": c.last_check.isoformat(),
                }
                for c in self._components.values()
            ]
    
    def get_recent_alerts(self, count: int = 10) -> List[Dict]:
        """Retorna alertas recentes"""
        with self._lock:
            recent = self._alerts[-count:]
            return [
                {
                    "component": a.component,
                    "severity": a.severity.value,
                    "message": a.message,
                    "timestamp": a.timestamp.isoformat(),
                    "resolved": a.resolved
                }
                for a in reversed(recent)
            ]
    
    def start(self):
        """Inicia monitoramento em background"""
        if self._running:
            logger.warning("Monitor já está rodando")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="HealthMonitor",
            daemon=True
        )
        self._thread.start()
        logger.info("🏥 Health Monitor iniciado")
    
    def stop(self):
        """Para o monitoramento"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("🏥 Health Monitor parado")
    
    def _monitor_loop(self):
        """Loop principal de monitoramento"""
        while self._running:
            try:
                self.run_all_checks()
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento: {e}")
            
            # Aguardar próximo ciclo
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def generate_status_report(self) -> str:
        """Gera relatório de status em texto"""
        overall = self.get_overall_health()
        components = self.get_all_components()
        alerts = self.get_recent_alerts(5)
        
        report = []
        report.append("=" * 50)
        report.append("🏥 HEALTH STATUS REPORT - URION BOT")
        report.append("=" * 50)
        report.append("")
        
        # Status geral
        status_emoji = {
            "healthy": "🟢",
            "degraded": "🟡",
            "critical": "🔴",
            "unknown": "⚪"
        }
        
        emoji = status_emoji.get(overall['status'], "❓")
        report.append(f"Status Geral: {emoji} {overall['status'].upper()}")
        report.append(f"Uptime: {overall['uptime_human']}")
        report.append(f"Componentes: {overall['healthy_components']}/{overall['total_components']} saudáveis")
        report.append("")
        
        # Componentes
        report.append("📊 COMPONENTES:")
        for c in components:
            emoji = status_emoji.get(c['status'], "❓")
            report.append(f"  {emoji} {c['name']}: {c['message']} ({c['latency_ms']:.0f}ms)")
        report.append("")
        
        # Alertas recentes
        if alerts:
            report.append("⚠️ ALERTAS RECENTES:")
            for a in alerts:
                report.append(f"  [{a['severity'].upper()}] {a['component']}: {a['message']}")
        
        report.append("")
        report.append("=" * 50)
        
        return "\n".join(report)


# Singleton
_monitor: Optional[HealthMonitor] = None


def get_health_monitor(
    check_interval: int = 30,
    alert_callback: Optional[Callable] = None
) -> HealthMonitor:
    """Obtém instância singleton do monitor"""
    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor(check_interval, alert_callback)
    return _monitor


# Exemplo de uso:
"""
from core.health_monitor import get_health_monitor, HealthStatus

monitor = get_health_monitor(check_interval=60)

# Registrar check personalizado
def check_mt5():
    # Sua lógica de verificação
    if connected:
        return ComponentHealth("mt5", HealthStatus.HEALTHY, "Conectado")
    return ComponentHealth("mt5", HealthStatus.CRITICAL, "Desconectado")

monitor.register_check("mt5", check_mt5)

# Iniciar monitoramento
monitor.start()

# Atualizar status manualmente
monitor.update_component("telegram", HealthStatus.HEALTHY, "Bot ativo")

# Obter status
overall = monitor.get_overall_health()
print(f"Status: {overall['status']}")

# Relatório
print(monitor.generate_status_report())
"""
