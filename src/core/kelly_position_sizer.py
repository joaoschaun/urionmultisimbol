"""
Kelly Position Sizer
Dimensionamento dinâmico de lote baseado no Kelly Criterion

O Kelly Criterion é uma fórmula matemática que determina a fração
ótima do capital a arriscar em cada trade, maximizando o crescimento
do capital no longo prazo.

Fórmula: f = (p × b - q) / b
Onde:
- f = fração do capital a arriscar
- p = probabilidade de ganhar (Win Rate)
- b = razão ganho/perda (avg_win / avg_loss)
- q = probabilidade de perder (1 - p)
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
import threading


@dataclass
class StrategyPerformance:
    """Performance de uma estratégia para cálculo de Kelly"""
    strategy_name: str
    total_trades: int
    wins: int
    losses: int
    total_profit: float
    total_loss: float
    avg_win: float
    avg_loss: float
    win_rate: float
    profit_factor: float
    kelly_fraction: float
    recommended_risk_pct: float
    last_updated: datetime


class KellyPositionSizer:
    """
    Calcula tamanho de posição usando Kelly Criterion
    
    Features:
    - Half-Kelly para segurança (usa 50% do Kelly)
    - Limites mín/máx de risco
    - Ajuste por drawdown atual
    - Cache de performance por estratégia
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa o position sizer
        
        Args:
            config: Configuração opcional
        """
        self.config = config or {}
        
        # Parâmetros de segurança
        self.min_risk_pct = self.config.get('min_risk_pct', 0.5)   # Mínimo 0.5%
        self.max_risk_pct = self.config.get('max_risk_pct', 3.0)   # Máximo 3%
        self.kelly_fraction = self.config.get('kelly_fraction', 0.5)  # Half-Kelly
        
        # Mínimo de trades para usar Kelly
        self.min_trades_for_kelly = self.config.get('min_trades', 20)
        
        # Default risk (quando não tem dados suficientes)
        self.default_risk_pct = self.config.get('default_risk_pct', 1.0)
        
        # Cache de performance
        self._strategy_cache: Dict[str, StrategyPerformance] = {}
        self._cache_ttl = timedelta(hours=1)  # TTL do cache
        
        # Lock para thread safety
        self._lock = threading.RLock()
        
        # Drawdown tracking
        self._current_drawdown_pct = 0.0
        self._max_allowed_drawdown = self.config.get('max_drawdown_pct', 8.0)
        
        logger.info(
            f"💰 Kelly Position Sizer inicializado | "
            f"Fração: {self.kelly_fraction} | "
            f"Risk: {self.min_risk_pct}%-{self.max_risk_pct}%"
        )
    
    def calculate_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calcula o Kelly Criterion
        
        Args:
            win_rate: Taxa de acerto (0.0 a 1.0)
            avg_win: Média de lucro por trade vencedor
            avg_loss: Média de perda por trade perdedor (positivo)
            
        Returns:
            Fração de Kelly (pode ser negativa se edge negativo)
        """
        if avg_loss <= 0 or avg_win <= 0:
            return 0.0
        
        # f = (p × b - q) / b
        p = win_rate
        q = 1 - p
        b = avg_win / avg_loss  # Win/Loss ratio
        
        kelly = (p * b - q) / b
        
        return kelly
    
    def calculate_position_risk(
        self,
        strategy_name: str,
        balance: float,
        stats: Optional[Dict] = None
    ) -> Dict:
        """
        Calcula o risco recomendado para uma posição
        
        Args:
            strategy_name: Nome da estratégia
            balance: Saldo atual da conta
            stats: Estatísticas da estratégia (opcional, busca do cache)
            
        Returns:
            Dict com risk_pct, risk_amount, kelly_raw, etc
        """
        with self._lock:
            try:
                # Verificar cache
                cached = self._get_cached_performance(strategy_name)
                
                if stats:
                    # Atualizar com novos stats
                    perf = self._calculate_performance(strategy_name, stats)
                elif cached:
                    perf = cached
                else:
                    # Sem dados = usar default
                    return self._default_risk(balance, strategy_name)
                
                # Verificar trades mínimos
                if perf.total_trades < self.min_trades_for_kelly:
                    logger.debug(
                        f"Kelly: {strategy_name} tem apenas {perf.total_trades} trades "
                        f"(mín: {self.min_trades_for_kelly}) - usando default"
                    )
                    return self._default_risk(balance, strategy_name)
                
                # Aplicar Half-Kelly (ou fração configurada)
                safe_kelly = perf.kelly_fraction * self.kelly_fraction
                
                # Converter para percentual de risco
                risk_pct = safe_kelly * 100
                
                # Aplicar limites
                risk_pct = max(self.min_risk_pct, min(risk_pct, self.max_risk_pct))
                
                # Ajustar por drawdown atual
                risk_pct = self._adjust_for_drawdown(risk_pct)
                
                # Calcular valor em dólares
                risk_amount = balance * (risk_pct / 100)
                
                result = {
                    'strategy': strategy_name,
                    'risk_pct': round(risk_pct, 2),
                    'risk_amount': round(risk_amount, 2),
                    'kelly_raw': round(perf.kelly_fraction * 100, 2),
                    'kelly_safe': round(safe_kelly * 100, 2),
                    'win_rate': round(perf.win_rate * 100, 2),
                    'profit_factor': round(perf.profit_factor, 2),
                    'total_trades': perf.total_trades,
                    'method': 'kelly',
                    'drawdown_adjusted': self._current_drawdown_pct > 0
                }
                
                logger.debug(
                    f"Kelly {strategy_name}: WR={result['win_rate']}%, "
                    f"PF={result['profit_factor']}, Risk={result['risk_pct']}%"
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Erro ao calcular Kelly para {strategy_name}: {e}")
                return self._default_risk(balance, strategy_name)
    
    def calculate_lot_size(
        self,
        strategy_name: str,
        balance: float,
        stop_loss_pips: float,
        pip_value: float = 1.0,
        stats: Optional[Dict] = None
    ) -> Dict:
        """
        Calcula o tamanho do lote baseado em Kelly
        
        Args:
            strategy_name: Nome da estratégia
            balance: Saldo da conta
            stop_loss_pips: Stop loss em pips
            pip_value: Valor do pip por lote (default 1.0 para XAUUSD mini)
            stats: Estatísticas da estratégia
            
        Returns:
            Dict com lot_size, risk_pct, etc
        """
        # Obter risco recomendado
        risk_info = self.calculate_position_risk(strategy_name, balance, stats)
        
        risk_amount = risk_info['risk_amount']
        
        # Calcular lote
        # risk_amount = lote × SL_pips × pip_value
        # lote = risk_amount / (SL_pips × pip_value)
        
        if stop_loss_pips <= 0 or pip_value <= 0:
            lot_size = 0.01  # Mínimo
        else:
            lot_size = risk_amount / (stop_loss_pips * pip_value)
        
        # Limites de lote
        min_lot = 0.01
        max_lot = 5.0  # Limite de segurança
        
        lot_size = max(min_lot, min(lot_size, max_lot))
        
        # Arredondar para 2 casas
        lot_size = round(lot_size, 2)
        
        result = {
            **risk_info,
            'lot_size': lot_size,
            'stop_loss_pips': stop_loss_pips,
            'pip_value': pip_value
        }
        
        logger.info(
            f"💰 Kelly Lot: {strategy_name} → {lot_size} lotes "
            f"(risk: {risk_info['risk_pct']}%, SL: {stop_loss_pips} pips)"
        )
        
        return result
    
    def _calculate_performance(
        self,
        strategy_name: str,
        stats: Dict
    ) -> StrategyPerformance:
        """Calcula performance e atualiza cache"""
        
        total_trades = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        total_profit = stats.get('total_profit', 0)
        total_loss = abs(stats.get('total_loss', 0))
        
        # Calcular médias
        avg_win = total_profit / wins if wins > 0 else 0
        avg_loss = total_loss / losses if losses > 0 else 0
        
        # Win Rate
        win_rate = wins / total_trades if total_trades > 0 else 0.5
        
        # Profit Factor
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # Kelly
        kelly = self.calculate_kelly(win_rate, avg_win, avg_loss)
        kelly = max(0, kelly)  # Não usar Kelly negativo
        
        # Risco recomendado
        recommended = kelly * self.kelly_fraction * 100
        recommended = max(self.min_risk_pct, min(recommended, self.max_risk_pct))
        
        perf = StrategyPerformance(
            strategy_name=strategy_name,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            total_profit=total_profit,
            total_loss=total_loss,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_rate=win_rate,
            profit_factor=profit_factor,
            kelly_fraction=kelly,
            recommended_risk_pct=recommended,
            last_updated=datetime.now()
        )
        
        # Atualizar cache
        self._strategy_cache[strategy_name] = perf
        
        return perf
    
    def _get_cached_performance(
        self,
        strategy_name: str
    ) -> Optional[StrategyPerformance]:
        """Obtém performance do cache se ainda válida"""
        if strategy_name not in self._strategy_cache:
            return None
        
        perf = self._strategy_cache[strategy_name]
        age = datetime.now() - perf.last_updated
        
        if age > self._cache_ttl:
            return None
        
        return perf
    
    def _default_risk(self, balance: float, strategy_name: str) -> Dict:
        """Retorna risco padrão quando não há dados suficientes"""
        risk_amount = balance * (self.default_risk_pct / 100)
        
        return {
            'strategy': strategy_name,
            'risk_pct': self.default_risk_pct,
            'risk_amount': round(risk_amount, 2),
            'kelly_raw': 0,
            'kelly_safe': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'total_trades': 0,
            'method': 'default',
            'drawdown_adjusted': False
        }
    
    def _adjust_for_drawdown(self, risk_pct: float) -> float:
        """
        Reduz risco quando em drawdown
        
        Lógica:
        - 0-2% DD: 100% do risco
        - 2-4% DD: 75% do risco
        - 4-6% DD: 50% do risco
        - 6-8% DD: 25% do risco
        - >8% DD: risco mínimo
        """
        dd = self._current_drawdown_pct
        
        if dd <= 2:
            multiplier = 1.0
        elif dd <= 4:
            multiplier = 0.75
        elif dd <= 6:
            multiplier = 0.50
        elif dd <= 8:
            multiplier = 0.25
        else:
            return self.min_risk_pct
        
        adjusted = risk_pct * multiplier
        return max(self.min_risk_pct, adjusted)
    
    def update_drawdown(self, current_drawdown_pct: float):
        """Atualiza drawdown atual para ajuste de risco"""
        with self._lock:
            self._current_drawdown_pct = current_drawdown_pct
            
            if current_drawdown_pct > 5:
                logger.warning(
                    f"⚠️ Drawdown alto: {current_drawdown_pct:.2f}% - "
                    f"reduzindo tamanho de posições"
                )
    
    def update_strategy_stats(self, strategy_name: str, stats: Dict):
        """Atualiza estatísticas de uma estratégia"""
        with self._lock:
            self._calculate_performance(strategy_name, stats)
    
    def get_all_recommendations(self, balance: float) -> Dict[str, Dict]:
        """Retorna recomendações para todas as estratégias em cache"""
        with self._lock:
            recommendations = {}
            
            for strategy_name in self._strategy_cache:
                recommendations[strategy_name] = self.calculate_position_risk(
                    strategy_name, balance
                )
            
            return recommendations
    
    def generate_report(self) -> str:
        """Gera relatório de Kelly para todas as estratégias"""
        with self._lock:
            if not self._strategy_cache:
                return "Nenhuma estratégia no cache ainda"
            
            lines = []
            lines.append("=" * 50)
            lines.append("💰 KELLY POSITION SIZING REPORT")
            lines.append("=" * 50)
            lines.append("")
            
            for name, perf in self._strategy_cache.items():
                lines.append(f"📊 {name}:")
                lines.append(f"   Trades: {perf.total_trades}")
                lines.append(f"   Win Rate: {perf.win_rate*100:.1f}%")
                lines.append(f"   Profit Factor: {perf.profit_factor:.2f}")
                lines.append(f"   Kelly Raw: {perf.kelly_fraction*100:.1f}%")
                lines.append(f"   Risco Recomendado: {perf.recommended_risk_pct:.1f}%")
                lines.append("")
            
            lines.append(f"📉 Drawdown Atual: {self._current_drawdown_pct:.1f}%")
            lines.append("=" * 50)
            
            return "\n".join(lines)


# Singleton
_position_sizer: Optional[KellyPositionSizer] = None


def get_kelly_sizer(config: Optional[Dict] = None) -> KellyPositionSizer:
    """Obtém instância singleton do position sizer"""
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = KellyPositionSizer(config)
    return _position_sizer
