"""
Strategy Degradation Detector
Detecta quando estratégias começam a falhar e toma ações preventivas

Sinais de degradação:
1. Win Rate caindo significativamente
2. Losing streak longa
3. Drawdown aumentando
4. Sharpe Ratio negativo
5. Profit Factor < 1.0

Ações:
- Reduzir position size
- Aumentar min_confidence
- Alertar via Telegram
- Pausar estratégia automaticamente
"""

from typing import Dict, Optional, List, Callable, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import threading
import json
import os


class DegradationLevel(Enum):
    """Níveis de degradação"""
    HEALTHY = "healthy"           # Tudo normal
    WARNING = "warning"           # Alerta - monitorar
    DEGRADED = "degraded"         # Degradado - reduzir risco
    CRITICAL = "critical"         # Crítico - pausar estratégia
    PAUSED = "paused"             # Pausada manualmente ou automaticamente


@dataclass
class DegradationAlert:
    """Alerta de degradação"""
    strategy: str
    level: DegradationLevel
    reason: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: datetime
    action_taken: str = ""


@dataclass
class StrategyHealth:
    """Saúde de uma estratégia"""
    name: str
    level: DegradationLevel
    
    # Métricas atuais
    win_rate: float = 0.0
    win_rate_trend: str = "stable"  # improving, declining, stable
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    current_drawdown_pct: float = 0.0
    
    # Streaks
    consecutive_losses: int = 0
    max_consecutive_losses: int = 0
    
    # Histórico
    recent_trades: int = 0
    recent_wins: int = 0
    recent_losses: int = 0
    
    # Ajustes aplicados
    confidence_multiplier: float = 1.0  # Multiplicador de min_confidence
    position_size_multiplier: float = 1.0  # Multiplicador de position size
    is_paused: bool = False
    pause_reason: str = ""
    pause_until: Optional[datetime] = None
    
    # Timestamps
    last_check: datetime = field(default_factory=datetime.now)
    last_trade: Optional[datetime] = None
    degraded_since: Optional[datetime] = None


class StrategyDegradationDetector:
    """
    Detecta degradação de estratégias e toma ações preventivas
    
    Features:
    - Monitoramento contínuo de performance
    - Detecção de losing streaks
    - Ajuste automático de parâmetros
    - Pause automático em casos críticos
    - Alertas via callback
    """
    
    def __init__(
        self,
        config: Optional[Dict] = None,
        alert_callback: Optional[Callable[[DegradationAlert], None]] = None
    ):
        """
        Inicializa o detector
        
        Args:
            config: Configuração de thresholds
            alert_callback: Callback para alertas (ex: telegram)
        """
        self.config = config or {}
        self.alert_callback = alert_callback
        
        # Thresholds
        self.thresholds = {
            # Win Rate
            'wr_warning': self.config.get('wr_warning', 0.40),      # < 40%
            'wr_degraded': self.config.get('wr_degraded', 0.30),    # < 30%
            'wr_critical': self.config.get('wr_critical', 0.20),    # < 20%
            
            # Profit Factor
            'pf_warning': self.config.get('pf_warning', 1.2),       # < 1.2
            'pf_degraded': self.config.get('pf_degraded', 1.0),     # < 1.0 (perdendo)
            'pf_critical': self.config.get('pf_critical', 0.5),     # < 0.5
            
            # Consecutive Losses
            'streak_warning': self.config.get('streak_warning', 4),
            'streak_degraded': self.config.get('streak_degraded', 6),
            'streak_critical': self.config.get('streak_critical', 8),
            
            # Drawdown
            'dd_warning': self.config.get('dd_warning', 3.0),       # > 3%
            'dd_degraded': self.config.get('dd_degraded', 5.0),     # > 5%
            'dd_critical': self.config.get('dd_critical', 8.0),     # > 8%
            
            # Mínimo de trades para avaliar
            'min_trades': self.config.get('min_trades', 10),
            
            # Período de análise (dias)
            'analysis_period_days': self.config.get('analysis_period_days', 7),
        }
        
        # Estado das estratégias
        self._strategies: Dict[str, StrategyHealth] = {}
        self._alerts: List[DegradationAlert] = []
        self._trade_history: Dict[str, List[Dict]] = {}  # strategy -> trades
        
        # Lock
        self._lock = threading.RLock()
        
        # Arquivo de estado
        self._state_file = self.config.get('state_file', 'data/degradation_state.json')
        self._load_state()
        
        logger.info("🔍 Strategy Degradation Detector inicializado")
    
    def record_trade(
        self,
        strategy: str,
        profit: float,
        profit_pips: float = 0,
        details: Optional[Dict] = None
    ):
        """
        Registra resultado de trade para análise
        
        Args:
            strategy: Nome da estratégia
            profit: Lucro/prejuízo
            profit_pips: Lucro em pips
            details: Detalhes adicionais
        """
        with self._lock:
            # Garantir que estratégia existe
            if strategy not in self._strategies:
                self._strategies[strategy] = StrategyHealth(
                    name=strategy,
                    level=DegradationLevel.HEALTHY
                )
            
            if strategy not in self._trade_history:
                self._trade_history[strategy] = []
            
            # Adicionar trade
            trade = {
                'profit': profit,
                'profit_pips': profit_pips,
                'timestamp': datetime.now().isoformat(),
                'details': details or {}
            }
            self._trade_history[strategy].append(trade)
            
            # Manter apenas últimos 100 trades
            if len(self._trade_history[strategy]) > 100:
                self._trade_history[strategy] = self._trade_history[strategy][-100:]
            
            # Atualizar estado
            health = self._strategies[strategy]
            health.last_trade = datetime.now()
            
            # Atualizar streak
            if profit > 0:
                health.consecutive_losses = 0
            else:
                health.consecutive_losses += 1
                health.max_consecutive_losses = max(
                    health.max_consecutive_losses,
                    health.consecutive_losses
                )
            
            # Avaliar saúde
            self._evaluate_strategy(strategy)
            
            # Salvar estado
            self._save_state()
    
    def _evaluate_strategy(self, strategy: str):
        """Avalia saúde de uma estratégia"""
        if strategy not in self._strategies:
            return
        
        health = self._strategies[strategy]
        trades = self._trade_history.get(strategy, [])
        
        # Filtrar trades recentes
        cutoff = datetime.now() - timedelta(days=self.thresholds['analysis_period_days'])
        recent = [
            t for t in trades 
            if datetime.fromisoformat(t['timestamp']) >= cutoff
        ]
        
        health.recent_trades = len(recent)
        
        if health.recent_trades < self.thresholds['min_trades']:
            # Poucos trades para avaliar
            health.level = DegradationLevel.HEALTHY
            return
        
        # Calcular métricas
        profits = [t['profit'] for t in recent]
        
        wins = [p for p in profits if p > 0]
        losses = [abs(p) for p in profits if p < 0]
        
        health.recent_wins = len(wins)
        health.recent_losses = len(losses)
        
        # Win Rate
        health.win_rate = len(wins) / len(recent) if recent else 0
        
        # Profit Factor
        total_profit = sum(wins)
        total_loss = sum(losses)
        health.profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Determinar nível
        old_level = health.level
        new_level = self._determine_level(health)
        health.level = new_level
        
        # Aplicar ações
        self._apply_actions(health, old_level, new_level)
        
        health.last_check = datetime.now()
    
    def _determine_level(self, health: StrategyHealth) -> DegradationLevel:
        """Determina nível de degradação baseado nas métricas"""
        
        if health.is_paused:
            return DegradationLevel.PAUSED
        
        # Verificar cada métrica (do mais grave para menos)
        
        # === CRÍTICO ===
        if health.win_rate < self.thresholds['wr_critical']:
            return DegradationLevel.CRITICAL
        
        if health.profit_factor < self.thresholds['pf_critical']:
            return DegradationLevel.CRITICAL
        
        if health.consecutive_losses >= self.thresholds['streak_critical']:
            return DegradationLevel.CRITICAL
        
        if health.current_drawdown_pct >= self.thresholds['dd_critical']:
            return DegradationLevel.CRITICAL
        
        # === DEGRADADO ===
        if health.win_rate < self.thresholds['wr_degraded']:
            return DegradationLevel.DEGRADED
        
        if health.profit_factor < self.thresholds['pf_degraded']:
            return DegradationLevel.DEGRADED
        
        if health.consecutive_losses >= self.thresholds['streak_degraded']:
            return DegradationLevel.DEGRADED
        
        if health.current_drawdown_pct >= self.thresholds['dd_degraded']:
            return DegradationLevel.DEGRADED
        
        # === WARNING ===
        if health.win_rate < self.thresholds['wr_warning']:
            return DegradationLevel.WARNING
        
        if health.profit_factor < self.thresholds['pf_warning']:
            return DegradationLevel.WARNING
        
        if health.consecutive_losses >= self.thresholds['streak_warning']:
            return DegradationLevel.WARNING
        
        if health.current_drawdown_pct >= self.thresholds['dd_warning']:
            return DegradationLevel.WARNING
        
        # === HEALTHY ===
        return DegradationLevel.HEALTHY
    
    def _apply_actions(
        self,
        health: StrategyHealth,
        old_level: DegradationLevel,
        new_level: DegradationLevel
    ):
        """Aplica ações baseado na mudança de nível"""
        
        action_taken = ""
        
        if new_level == DegradationLevel.HEALTHY:
            # Resetar ajustes
            health.confidence_multiplier = 1.0
            health.position_size_multiplier = 1.0
            health.degraded_since = None
            action_taken = "Parâmetros normalizados"
            
        elif new_level == DegradationLevel.WARNING:
            # Aumentar cautela levemente
            health.confidence_multiplier = 1.1  # +10% confidence
            health.position_size_multiplier = 0.9  # -10% size
            health.degraded_since = health.degraded_since or datetime.now()
            action_taken = "Confidence +10%, Size -10%"
            
        elif new_level == DegradationLevel.DEGRADED:
            # Aumentar cautela significativamente
            health.confidence_multiplier = 1.25  # +25% confidence
            health.position_size_multiplier = 0.5  # -50% size
            health.degraded_since = health.degraded_since or datetime.now()
            action_taken = "Confidence +25%, Size -50%"
            
        elif new_level == DegradationLevel.CRITICAL:
            # Pausar automaticamente
            health.is_paused = True
            health.pause_reason = f"Degradação crítica: WR={health.win_rate*100:.1f}%, PF={health.profit_factor:.2f}"
            health.pause_until = datetime.now() + timedelta(hours=24)
            health.confidence_multiplier = 1.5
            health.position_size_multiplier = 0.25
            action_taken = "PAUSADA por 24h"
        
        # Criar alerta se mudou de nível
        if old_level != new_level:
            self._create_alert(health, new_level, action_taken)
    
    def _create_alert(
        self,
        health: StrategyHealth,
        level: DegradationLevel,
        action_taken: str
    ):
        """Cria alerta de degradação"""
        
        # Determinar razão principal
        if health.win_rate < self.thresholds['wr_degraded']:
            reason = f"Win Rate baixo"
            metric = "win_rate"
            value = health.win_rate * 100
            threshold = self.thresholds['wr_degraded'] * 100
        elif health.profit_factor < self.thresholds['pf_degraded']:
            reason = "Profit Factor baixo"
            metric = "profit_factor"
            value = health.profit_factor
            threshold = self.thresholds['pf_degraded']
        elif health.consecutive_losses >= self.thresholds['streak_degraded']:
            reason = "Losing streak longa"
            metric = "consecutive_losses"
            value = health.consecutive_losses
            threshold = self.thresholds['streak_degraded']
        else:
            reason = "Múltiplos indicadores"
            metric = "multiple"
            value = 0
            threshold = 0
        
        alert = DegradationAlert(
            strategy=health.name,
            level=level,
            reason=reason,
            metric_name=metric,
            current_value=value,
            threshold=threshold,
            timestamp=datetime.now(),
            action_taken=action_taken
        )
        
        self._alerts.append(alert)
        
        # Manter últimos 100 alertas
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
            DegradationLevel.WARNING: "⚠️",
            DegradationLevel.DEGRADED: "🟠",
            DegradationLevel.CRITICAL: "🔴",
            DegradationLevel.PAUSED: "⏸️",
            DegradationLevel.HEALTHY: "🟢"
        }
        
        emoji = emoji_map.get(level, "❓")
        logger.warning(
            f"{emoji} Degradação [{health.name}]: {level.value} - {reason} | "
            f"Ação: {action_taken}"
        )
    
    def get_strategy_health(self, strategy: str) -> Optional[StrategyHealth]:
        """Retorna saúde de uma estratégia"""
        with self._lock:
            return self._strategies.get(strategy)
    
    def get_all_health(self) -> Dict[str, StrategyHealth]:
        """Retorna saúde de todas as estratégias"""
        with self._lock:
            return self._strategies.copy()
    
    def get_confidence_multiplier(self, strategy: str) -> float:
        """Retorna multiplicador de confidence para uma estratégia"""
        with self._lock:
            health = self._strategies.get(strategy)
            return health.confidence_multiplier if health else 1.0
    
    def get_position_multiplier(self, strategy: str) -> float:
        """Retorna multiplicador de position size para uma estratégia"""
        with self._lock:
            health = self._strategies.get(strategy)
            return health.position_size_multiplier if health else 1.0
    
    def is_strategy_paused(self, strategy: str) -> Tuple[bool, str]:
        """Verifica se estratégia está pausada"""
        with self._lock:
            health = self._strategies.get(strategy)
            
            if not health:
                return False, ""
            
            if not health.is_paused:
                return False, ""
            
            # Verificar se pause expirou
            if health.pause_until and datetime.now() >= health.pause_until:
                health.is_paused = False
                health.pause_reason = ""
                health.pause_until = None
                return False, ""
            
            return True, health.pause_reason
    
    def pause_strategy(self, strategy: str, reason: str, hours: int = 24):
        """Pausa uma estratégia manualmente"""
        with self._lock:
            if strategy not in self._strategies:
                self._strategies[strategy] = StrategyHealth(
                    name=strategy,
                    level=DegradationLevel.PAUSED
                )
            
            health = self._strategies[strategy]
            health.is_paused = True
            health.pause_reason = reason
            health.pause_until = datetime.now() + timedelta(hours=hours)
            health.level = DegradationLevel.PAUSED
            
            self._save_state()
            
            logger.info(f"⏸️ {strategy} pausada por {hours}h: {reason}")
    
    def unpause_strategy(self, strategy: str):
        """Retoma uma estratégia pausada"""
        with self._lock:
            if strategy in self._strategies:
                health = self._strategies[strategy]
                health.is_paused = False
                health.pause_reason = ""
                health.pause_until = None
                health.level = DegradationLevel.HEALTHY
                
                self._save_state()
                
                logger.info(f"▶️ {strategy} retomada")
    
    def update_drawdown(self, strategy: str, drawdown_pct: float):
        """Atualiza drawdown de uma estratégia"""
        with self._lock:
            if strategy in self._strategies:
                self._strategies[strategy].current_drawdown_pct = drawdown_pct
    
    def get_recent_alerts(self, count: int = 10) -> List[Dict]:
        """Retorna alertas recentes"""
        with self._lock:
            recent = self._alerts[-count:]
            return [
                {
                    'strategy': a.strategy,
                    'level': a.level.value,
                    'reason': a.reason,
                    'metric': a.metric_name,
                    'value': a.current_value,
                    'threshold': a.threshold,
                    'action': a.action_taken,
                    'timestamp': a.timestamp.isoformat()
                }
                for a in reversed(recent)
            ]
    
    def _load_state(self):
        """Carrega estado do arquivo"""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r') as f:
                    data = json.load(f)
                
                for name, state in data.get('strategies', {}).items():
                    self._strategies[name] = StrategyHealth(
                        name=name,
                        level=DegradationLevel(state.get('level', 'healthy')),
                        win_rate=state.get('win_rate', 0),
                        profit_factor=state.get('profit_factor', 0),
                        consecutive_losses=state.get('consecutive_losses', 0),
                        is_paused=state.get('is_paused', False),
                        pause_reason=state.get('pause_reason', ''),
                        confidence_multiplier=state.get('confidence_multiplier', 1.0),
                        position_size_multiplier=state.get('position_size_multiplier', 1.0)
                    )
                
                logger.debug(f"Estado de degradação carregado: {len(self._strategies)} estratégias")
        except Exception as e:
            logger.error(f"Erro ao carregar estado de degradação: {e}")
    
    def _save_state(self):
        """Salva estado no arquivo"""
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            
            data = {
                'strategies': {
                    name: {
                        'level': h.level.value,
                        'win_rate': h.win_rate,
                        'profit_factor': h.profit_factor,
                        'consecutive_losses': h.consecutive_losses,
                        'is_paused': h.is_paused,
                        'pause_reason': h.pause_reason,
                        'confidence_multiplier': h.confidence_multiplier,
                        'position_size_multiplier': h.position_size_multiplier
                    }
                    for name, h in self._strategies.items()
                },
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self._state_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Erro ao salvar estado de degradação: {e}")
    
    def generate_report(self) -> str:
        """Gera relatório de saúde das estratégias"""
        lines = []
        lines.append("=" * 55)
        lines.append("🔍 STRATEGY DEGRADATION REPORT")
        lines.append("=" * 55)
        lines.append("")
        
        emoji_map = {
            DegradationLevel.HEALTHY: "🟢",
            DegradationLevel.WARNING: "🟡",
            DegradationLevel.DEGRADED: "🟠",
            DegradationLevel.CRITICAL: "🔴",
            DegradationLevel.PAUSED: "⏸️"
        }
        
        with self._lock:
            for name, health in self._strategies.items():
                emoji = emoji_map.get(health.level, "❓")
                lines.append(f"{emoji} {name}: {health.level.value.upper()}")
                lines.append(f"   WR: {health.win_rate*100:.1f}% | PF: {health.profit_factor:.2f}")
                lines.append(f"   Losses consecutivas: {health.consecutive_losses}")
                lines.append(f"   Multiplicadores: conf={health.confidence_multiplier}x, size={health.position_size_multiplier}x")
                
                if health.is_paused:
                    lines.append(f"   ⏸️ PAUSADA: {health.pause_reason}")
                
                lines.append("")
        
        lines.append("=" * 55)
        
        return "\n".join(lines)


# Singleton
_detector: Optional[StrategyDegradationDetector] = None


def get_degradation_detector(
    config: Optional[Dict] = None,
    alert_callback: Optional[Callable] = None
) -> StrategyDegradationDetector:
    """Obtém instância singleton do detector"""
    global _detector
    if _detector is None:
        _detector = StrategyDegradationDetector(config, alert_callback)
    return _detector
