# -*- coding: utf-8 -*-
"""
Advanced Monitoring Dashboard

Sistema de monitoramento em tempo real:
- Métricas de performance
- Alertas e notificações
- Visualizações
- Health checks
"""

import threading
import time
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import deque
import statistics

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """Uma métrica individual"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass 
class Alert:
    """Um alerta"""
    id: str
    level: str  # info, warning, error, critical
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    """Status de saúde de um componente"""
    component: str
    status: str  # healthy, degraded, unhealthy
    last_check: datetime = field(default_factory=datetime.now)
    latency_ms: float = 0.0
    message: str = ""
    checks: Dict[str, bool] = field(default_factory=dict)


class MetricsCollector:
    """
    Coletor de métricas em memória
    
    Features:
    - Agregação temporal
    - Cálculo de estatísticas
    - Export para Prometheus/InfluxDB
    """
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics: Dict[str, deque] = {}
        self._lock = threading.Lock()
    
    def record(self, name: str, value: float, tags: Dict[str, str] = None):
        """Registra uma métrica"""
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = deque(maxlen=self.max_history)
            
            self.metrics[name].append(Metric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {}
            ))
    
    def get_latest(self, name: str) -> Optional[Metric]:
        """Retorna última métrica"""
        with self._lock:
            if name in self.metrics and self.metrics[name]:
                return self.metrics[name][-1]
        return None
    
    def get_history(
        self, 
        name: str, 
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Metric]:
        """Retorna histórico de métricas"""
        with self._lock:
            if name not in self.metrics:
                return []
            
            metrics = list(self.metrics[name])
            
            if since:
                metrics = [m for m in metrics if m.timestamp >= since]
            
            return metrics[-limit:]
    
    def get_stats(self, name: str, window_minutes: int = 60) -> Dict[str, float]:
        """Retorna estatísticas de uma métrica"""
        since = datetime.now() - timedelta(minutes=window_minutes)
        history = self.get_history(name, since=since)
        
        if not history:
            return {}
        
        values = [m.value for m in history]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'std': statistics.stdev(values) if len(values) > 1 else 0,
            'p95': sorted(values)[int(len(values) * 0.95)] if len(values) > 1 else values[0],
            'p99': sorted(values)[int(len(values) * 0.99)] if len(values) > 1 else values[0]
        }
    
    def get_all_metrics(self) -> Dict[str, Dict]:
        """Retorna todas as métricas com stats"""
        with self._lock:
            result = {}
            for name in self.metrics:
                latest = self.get_latest(name)
                stats = self.get_stats(name)
                
                result[name] = {
                    'latest': latest.value if latest else None,
                    'timestamp': latest.timestamp.isoformat() if latest else None,
                    'stats': stats
                }
            
            return result
    
    def export_prometheus(self) -> str:
        """Exporta métricas em formato Prometheus"""
        lines = []
        
        with self._lock:
            for name, history in self.metrics.items():
                if not history:
                    continue
                
                latest = history[-1]
                metric_name = name.replace('.', '_').replace('-', '_')
                
                # Adicionar HELP e TYPE
                lines.append(f"# HELP {metric_name} {name}")
                lines.append(f"# TYPE {metric_name} gauge")
                
                # Valor
                tags_str = ""
                if latest.tags:
                    tags_parts = [f'{k}="{v}"' for k, v in latest.tags.items()]
                    tags_str = "{" + ",".join(tags_parts) + "}"
                
                lines.append(f"{metric_name}{tags_str} {latest.value}")
        
        return "\n".join(lines)


class AlertManager:
    """
    Gerenciador de alertas
    
    Features:
    - Regras de alerta
    - Deduplicação
    - Escalonamento
    - Notificações
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.alerts: deque = deque(maxlen=1000)
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_rules: List[Dict] = []
        self.notification_handlers: List[Callable] = []
        self._lock = threading.Lock()
        
        # Alert ID counter
        self._alert_counter = 0
    
    def add_rule(
        self,
        name: str,
        condition: Callable,
        level: str,
        message_template: str,
        cooldown_seconds: int = 300
    ):
        """Adiciona regra de alerta"""
        self.alert_rules.append({
            'name': name,
            'condition': condition,
            'level': level,
            'message_template': message_template,
            'cooldown_seconds': cooldown_seconds,
            'last_triggered': None
        })
    
    def check_rules(self, metrics: Dict[str, Any], context: Dict[str, Any] = None):
        """Verifica todas as regras"""
        for rule in self.alert_rules:
            try:
                # Verificar cooldown
                if rule['last_triggered']:
                    elapsed = (datetime.now() - rule['last_triggered']).total_seconds()
                    if elapsed < rule['cooldown_seconds']:
                        continue
                
                # Avaliar condição
                if rule['condition'](metrics, context or {}):
                    self._trigger_alert(rule, metrics, context)
                    
            except Exception as e:
                logger.error(f"Erro ao verificar regra {rule['name']}: {e}")
    
    def _trigger_alert(self, rule: Dict, metrics: Dict, context: Dict):
        """Dispara alerta"""
        with self._lock:
            self._alert_counter += 1
            
            alert = Alert(
                id=f"alert_{self._alert_counter}",
                level=rule['level'],
                message=rule['message_template'].format(**{**metrics, **(context or {})}),
                source=rule['name'],
                data={'metrics': metrics, 'context': context}
            )
            
            self.alerts.append(alert)
            self.active_alerts[alert.id] = alert
            rule['last_triggered'] = datetime.now()
            
            logger.warning(f"ALERTA [{alert.level.upper()}]: {alert.message}")
            
            # Notificar handlers
            for handler in self.notification_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Erro no handler de notificação: {e}")
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge um alerta"""
        with self._lock:
            if alert_id in self.active_alerts:
                self.active_alerts[alert_id].acknowledged = True
                del self.active_alerts[alert_id]
    
    def get_active_alerts(self) -> List[Alert]:
        """Retorna alertas ativos"""
        with self._lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 50) -> List[Alert]:
        """Retorna histórico de alertas"""
        with self._lock:
            return list(self.alerts)[-limit:]
    
    def register_notification_handler(self, handler: Callable):
        """Registra handler de notificação"""
        self.notification_handlers.append(handler)


class HealthChecker:
    """
    Verificador de saúde do sistema
    
    Features:
    - Health checks periódicos
    - Dependency checks
    - Self-healing
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.components: Dict[str, HealthStatus] = {}
        self.health_checks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
    
    def register_component(self, name: str, check_func: Callable):
        """Registra componente para health check"""
        self.health_checks[name] = check_func
        self.components[name] = HealthStatus(
            component=name,
            status='unknown'
        )
    
    def check_all(self) -> Dict[str, HealthStatus]:
        """Executa todos os health checks"""
        for name, check_func in self.health_checks.items():
            start = time.time()
            
            try:
                result = check_func()
                latency = (time.time() - start) * 1000
                
                with self._lock:
                    self.components[name] = HealthStatus(
                        component=name,
                        status='healthy' if result else 'unhealthy',
                        latency_ms=latency,
                        message='OK' if result else 'Check failed'
                    )
                    
            except Exception as e:
                latency = (time.time() - start) * 1000
                
                with self._lock:
                    self.components[name] = HealthStatus(
                        component=name,
                        status='unhealthy',
                        latency_ms=latency,
                        message=str(e)
                    )
        
        return self.components.copy()
    
    def is_healthy(self) -> bool:
        """Verifica se sistema está saudável"""
        with self._lock:
            return all(
                c.status == 'healthy' 
                for c in self.components.values()
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status geral"""
        with self._lock:
            healthy_count = sum(1 for c in self.components.values() if c.status == 'healthy')
            total_count = len(self.components)
            
            return {
                'overall_status': 'healthy' if healthy_count == total_count else 'degraded',
                'healthy_components': healthy_count,
                'total_components': total_count,
                'components': {
                    name: {
                        'status': c.status,
                        'latency_ms': c.latency_ms,
                        'message': c.message,
                        'last_check': c.last_check.isoformat()
                    }
                    for name, c in self.components.items()
                }
            }


class AdvancedMonitor:
    """
    Monitor Avançado Principal
    
    Integra:
    - Métricas
    - Alertas
    - Health Checks
    - Dashboard
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Componentes
        self.metrics = MetricsCollector(
            max_history=self.config.get('max_metrics_history', 10000)
        )
        self.alerts = AlertManager(config)
        self.health = HealthChecker(config)
        
        # Trading metrics
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.positions_count = 0
        
        # Threading
        self.running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        
        # Configurar regras de alerta padrão
        self._setup_default_alerts()
        
        logger.info("AdvancedMonitor inicializado")
    
    def _setup_default_alerts(self):
        """Configura alertas padrão"""
        
        # Alerta de drawdown alto
        self.alerts.add_rule(
            name='high_drawdown',
            condition=lambda m, c: m.get('drawdown', 0) > 0.05,
            level='critical',
            message_template='Drawdown crítico: {drawdown:.2%}',
            cooldown_seconds=600
        )
        
        # Alerta de perda diária
        self.alerts.add_rule(
            name='daily_loss',
            condition=lambda m, c: m.get('daily_pnl', 0) < -200,
            level='warning',
            message_template='Perda diária significativa: ${daily_pnl:.2f}',
            cooldown_seconds=3600
        )
        
        # Alerta de latência alta
        self.alerts.add_rule(
            name='high_latency',
            condition=lambda m, c: m.get('execution_latency', 0) > 500,
            level='warning',
            message_template='Latência de execução alta: {execution_latency:.0f}ms',
            cooldown_seconds=300
        )
        
        # Alerta de muitos trades
        self.alerts.add_rule(
            name='excessive_trades',
            condition=lambda m, c: m.get('trades_today', 0) > 50,
            level='warning',
            message_template='Número excessivo de trades: {trades_today}',
            cooldown_seconds=3600
        )
    
    def start(self):
        """Inicia monitoramento"""
        if self.running:
            return
        
        self.running = True
        
        # Thread de monitoramento de métricas
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="AdvancedMonitor"
        )
        self._monitor_thread.start()
        
        # Thread de health check
        self._health_thread = threading.Thread(
            target=self._health_loop,
            daemon=True,
            name="HealthChecker"
        )
        self._health_thread.start()
        
        logger.info("AdvancedMonitor iniciado")
    
    def stop(self):
        """Para monitoramento"""
        self.running = False
        logger.info("AdvancedMonitor parado")
    
    def _monitor_loop(self):
        """Loop principal de monitoramento"""
        while self.running:
            try:
                # Coletar métricas
                current_metrics = self._collect_trading_metrics()
                
                # Verificar regras de alerta
                self.alerts.check_rules(current_metrics)
                
                time.sleep(10)  # A cada 10 segundos
                
            except Exception as e:
                logger.error(f"Erro no monitor loop: {e}")
                time.sleep(30)
    
    def _health_loop(self):
        """Loop de health check"""
        while self.running:
            try:
                self.health.check_all()
                time.sleep(60)  # A cada 60 segundos
                
            except Exception as e:
                logger.error(f"Erro no health loop: {e}")
                time.sleep(60)
    
    def _collect_trading_metrics(self) -> Dict[str, Any]:
        """Coleta métricas de trading"""
        return {
            'trades_today': self.trades_today,
            'daily_pnl': self.daily_pnl,
            'positions_count': self.positions_count,
            'drawdown': self.metrics.get_latest('drawdown').value if self.metrics.get_latest('drawdown') else 0,
            'execution_latency': self.metrics.get_latest('execution_latency').value if self.metrics.get_latest('execution_latency') else 0
        }
    
    # =========================================================================
    # API para registrar métricas
    # =========================================================================
    
    def record_trade(self, profit: float, symbol: str, strategy: str):
        """Registra um trade"""
        self.trades_today += 1
        self.daily_pnl += profit
        
        self.metrics.record('trade_profit', profit, {'symbol': symbol, 'strategy': strategy})
        self.metrics.record('trades_today', self.trades_today)
        self.metrics.record('daily_pnl', self.daily_pnl)
        
        logger.info(f"Trade registrado: {symbol} {profit:+.2f} ({strategy})")
    
    def record_position_change(self, count: int):
        """Registra mudança em posições"""
        self.positions_count = count
        self.metrics.record('positions_count', count)
    
    def record_drawdown(self, drawdown: float):
        """Registra drawdown"""
        self.metrics.record('drawdown', drawdown)
    
    def record_latency(self, latency_ms: float, operation: str):
        """Registra latência"""
        self.metrics.record('execution_latency', latency_ms, {'operation': operation})
    
    def record_signal(self, symbol: str, direction: str, confidence: float):
        """Registra sinal gerado"""
        self.metrics.record('signal_confidence', confidence, {'symbol': symbol, 'direction': direction})
    
    def record_balance(self, balance: float, equity: float):
        """Registra balanço"""
        self.metrics.record('account_balance', balance)
        self.metrics.record('account_equity', equity)
    
    # =========================================================================
    # API para health checks
    # =========================================================================
    
    def register_health_check(self, name: str, check_func: Callable):
        """Registra health check"""
        self.health.register_component(name, check_func)
    
    # =========================================================================
    # Dashboard API
    # =========================================================================
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Retorna dados para dashboard"""
        return {
            'timestamp': datetime.now().isoformat(),
            'trading': {
                'trades_today': self.trades_today,
                'daily_pnl': self.daily_pnl,
                'positions_count': self.positions_count
            },
            'metrics': self.metrics.get_all_metrics(),
            'alerts': {
                'active': [asdict(a) for a in self.alerts.get_active_alerts()],
                'recent': [asdict(a) for a in self.alerts.get_alert_history(10)]
            },
            'health': self.health.get_status()
        }
    
    def get_prometheus_metrics(self) -> str:
        """Retorna métricas em formato Prometheus"""
        return self.metrics.export_prometheus()
    
    def reset_daily_metrics(self):
        """Reseta métricas diárias"""
        self.trades_today = 0
        self.daily_pnl = 0.0
        logger.info("Métricas diárias resetadas")


# Instância global
_advanced_monitor: Optional[AdvancedMonitor] = None


def get_advanced_monitor(config: Dict[str, Any] = None) -> AdvancedMonitor:
    """Retorna instância singleton"""
    global _advanced_monitor
    if _advanced_monitor is None:
        _advanced_monitor = AdvancedMonitor(config)
    return _advanced_monitor


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Criar monitor
    monitor = get_advanced_monitor()
    
    # Registrar health checks
    monitor.register_health_check('mt5', lambda: True)
    monitor.register_health_check('redis', lambda: True)
    
    # Iniciar
    monitor.start()
    
    # Simular trades
    monitor.record_trade(50.0, 'XAUUSD', 'scalping')
    monitor.record_trade(-20.0, 'XAUUSD', 'scalping')
    monitor.record_drawdown(0.02)
    monitor.record_latency(150, 'order_execution')
    
    # Dashboard data
    print(json.dumps(monitor.get_dashboard_data(), indent=2, default=str))
    
    # Prometheus metrics
    print("\n--- Prometheus Metrics ---")
    print(monitor.get_prometheus_metrics())
    
    monitor.stop()
