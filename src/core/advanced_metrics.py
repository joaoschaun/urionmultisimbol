"""
Advanced Performance Metrics
Métricas profissionais de performance de trading

Métricas implementadas:
- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Maximum Drawdown
- Recovery Factor
- Win Rate Ponderado
- Profit Factor
- Average RRR
- Expectancy
"""

import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from loguru import logger
import threading


@dataclass
class TradeResult:
    """Resultado de um trade para cálculo de métricas"""
    profit: float
    profit_pips: float
    duration_minutes: float
    timestamp: datetime
    strategy: str
    symbol: str


@dataclass
class PerformanceMetrics:
    """Métricas de performance calculadas"""
    # Básicas
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Financeiras
    total_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    
    # Médias
    avg_profit: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_rrr: float = 0.0  # Risk/Reward Ratio
    
    # Avançadas
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    sqn: float = 0.0  # 🆕 System Quality Number
    sqn_rating: str = "N/A"  # 🆕 Rating do SQN
    
    # Drawdown
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    current_drawdown: float = 0.0
    current_drawdown_pct: float = 0.0
    avg_drawdown: float = 0.0  # 🆕 Drawdown médio
    
    # Recovery
    recovery_factor: float = 0.0
    
    # Expectancy
    expectancy: float = 0.0
    expectancy_pips: float = 0.0
    
    # Consistência
    best_trade: float = 0.0
    worst_trade: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # 🆕 Métricas de Duração
    avg_trade_duration_minutes: float = 0.0
    avg_win_duration_minutes: float = 0.0
    avg_loss_duration_minutes: float = 0.0
    
    # 🆕 R-Múltiplo
    avg_r_multiple: float = 0.0
    r_expectancy: float = 0.0
    
    # Período
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trading_days: int = 0


class AdvancedMetricsCalculator:
    """
    Calculador de métricas avançadas de trading
    
    Features:
    - Cálculo em tempo real
    - Análise por estratégia
    - Análise por período
    - Benchmarking
    """
    
    # Taxa livre de risco anualizada (US Treasury 1Y ~ 5%)
    RISK_FREE_RATE_ANNUAL = 0.05
    
    def __init__(self, initial_balance: float = 10000.0):
        """
        Inicializa o calculador
        
        Args:
            initial_balance: Saldo inicial para cálculos de retorno
        """
        self.initial_balance = initial_balance
        self._trades: List[TradeResult] = []
        self._equity_curve: List[Tuple[datetime, float]] = []
        self._lock = threading.RLock()
        
        # Peak para drawdown
        self._peak_balance = initial_balance
        self._current_balance = initial_balance
        
        logger.info(f"📊 Advanced Metrics inicializado | Balance: ${initial_balance:,.2f}")
    
    def add_trade(
        self,
        profit: float,
        profit_pips: float = 0,
        duration_minutes: float = 0,
        strategy: str = "unknown",
        symbol: str = "XAUUSD"
    ):
        """Adiciona resultado de trade"""
        with self._lock:
            trade = TradeResult(
                profit=profit,
                profit_pips=profit_pips,
                duration_minutes=duration_minutes,
                timestamp=datetime.now(),
                strategy=strategy,
                symbol=symbol
            )
            self._trades.append(trade)
            
            # Atualizar equity
            self._current_balance += profit
            self._peak_balance = max(self._peak_balance, self._current_balance)
            self._equity_curve.append((trade.timestamp, self._current_balance))
    
    def update_balance(self, balance: float):
        """Atualiza balance atual"""
        with self._lock:
            self._current_balance = balance
            self._peak_balance = max(self._peak_balance, balance)
            self._equity_curve.append((datetime.now(), balance))
    
    def calculate_metrics(
        self,
        strategy: Optional[str] = None,
        days: Optional[int] = None
    ) -> PerformanceMetrics:
        """
        Calcula todas as métricas
        
        Args:
            strategy: Filtrar por estratégia (None = todas)
            days: Últimos N dias (None = todos)
            
        Returns:
            PerformanceMetrics com todas as métricas
        """
        with self._lock:
            try:
                # Filtrar trades
                trades = self._filter_trades(strategy, days)
                
                if not trades:
                    return PerformanceMetrics()
                
                metrics = PerformanceMetrics()
                
                # === MÉTRICAS BÁSICAS ===
                profits = [t.profit for t in trades]
                
                metrics.total_trades = len(trades)
                metrics.winning_trades = sum(1 for p in profits if p > 0)
                metrics.losing_trades = sum(1 for p in profits if p < 0)
                metrics.win_rate = metrics.winning_trades / metrics.total_trades
                
                # === FINANCEIRAS ===
                metrics.total_profit = sum(profits)
                metrics.gross_profit = sum(p for p in profits if p > 0)
                metrics.gross_loss = abs(sum(p for p in profits if p < 0))
                
                if metrics.gross_loss > 0:
                    metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
                else:
                    metrics.profit_factor = float('inf') if metrics.gross_profit > 0 else 0
                
                # === MÉDIAS ===
                metrics.avg_profit = metrics.total_profit / metrics.total_trades
                
                wins = [p for p in profits if p > 0]
                losses = [abs(p) for p in profits if p < 0]
                
                metrics.avg_win = sum(wins) / len(wins) if wins else 0
                metrics.avg_loss = sum(losses) / len(losses) if losses else 0
                
                if metrics.avg_loss > 0:
                    metrics.avg_rrr = metrics.avg_win / metrics.avg_loss
                
                # === BEST/WORST ===
                metrics.best_trade = max(profits)
                metrics.worst_trade = min(profits)
                
                # === SHARPE RATIO ===
                metrics.sharpe_ratio = self._calculate_sharpe(profits)
                
                # === SORTINO RATIO ===
                metrics.sortino_ratio = self._calculate_sortino(profits)
                
                # === DRAWDOWN ===
                dd_info = self._calculate_drawdown(trades)
                metrics.max_drawdown = dd_info['max_dd']
                metrics.max_drawdown_pct = dd_info['max_dd_pct']
                metrics.current_drawdown = dd_info['current_dd']
                metrics.current_drawdown_pct = dd_info['current_dd_pct']
                
                # === CALMAR RATIO ===
                if metrics.max_drawdown_pct > 0:
                    annual_return = self._calculate_annual_return(trades)
                    metrics.calmar_ratio = annual_return / metrics.max_drawdown_pct
                
                # === SQN (System Quality Number) ===
                sqn_result = self._calculate_sqn(profits)
                metrics.sqn = sqn_result['sqn']
                metrics.sqn_rating = sqn_result['rating']
                
                # === R-MULTIPLE E EXPECTANCY ===
                r_stats = self._calculate_r_multiple(trades)
                metrics.avg_r_multiple = r_stats['avg_r']
                metrics.r_expectancy = r_stats['r_expectancy']
                
                # === DURAÇÃO MÉDIA ===
                durations = self._calculate_duration_stats(trades)
                metrics.avg_trade_duration_minutes = durations['avg_all']
                metrics.avg_win_duration_minutes = durations['avg_win']
                metrics.avg_loss_duration_minutes = durations['avg_loss']
                
                # === RECOVERY FACTOR ===
                if metrics.max_drawdown > 0:
                    metrics.recovery_factor = metrics.total_profit / metrics.max_drawdown
                
                # === EXPECTANCY ===
                metrics.expectancy = (
                    (metrics.win_rate * metrics.avg_win) -
                    ((1 - metrics.win_rate) * metrics.avg_loss)
                )
                
                pips = [t.profit_pips for t in trades]
                win_pips = [p for p in pips if p > 0]
                loss_pips = [abs(p) for p in pips if p < 0]
                
                avg_win_pips = sum(win_pips) / len(win_pips) if win_pips else 0
                avg_loss_pips = sum(loss_pips) / len(loss_pips) if loss_pips else 0
                
                metrics.expectancy_pips = (
                    (metrics.win_rate * avg_win_pips) -
                    ((1 - metrics.win_rate) * avg_loss_pips)
                )
                
                # === CONSECUTIVE WINS/LOSSES ===
                streaks = self._calculate_streaks(profits)
                metrics.consecutive_wins = streaks['current_wins']
                metrics.consecutive_losses = streaks['current_losses']
                metrics.max_consecutive_wins = streaks['max_wins']
                metrics.max_consecutive_losses = streaks['max_losses']
                
                # === PERÍODO ===
                metrics.start_date = trades[0].timestamp
                metrics.end_date = trades[-1].timestamp
                
                if metrics.start_date and metrics.end_date:
                    delta = metrics.end_date - metrics.start_date
                    metrics.trading_days = max(1, delta.days)
                
                return metrics
                
            except Exception as e:
                logger.error(f"Erro ao calcular métricas: {e}")
                return PerformanceMetrics()
    
    def _filter_trades(
        self,
        strategy: Optional[str],
        days: Optional[int]
    ) -> List[TradeResult]:
        """Filtra trades por estratégia e período"""
        trades = self._trades.copy()
        
        if strategy:
            trades = [t for t in trades if t.strategy == strategy]
        
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            trades = [t for t in trades if t.timestamp >= cutoff]
        
        return trades
    
    def _calculate_sharpe(self, profits: List[float]) -> float:
        """
        Calcula Sharpe Ratio
        
        Sharpe = (Retorno Médio - Risk Free Rate) / Desvio Padrão
        """
        if len(profits) < 2:
            return 0.0
        
        # Retorno médio por trade
        mean_return = sum(profits) / len(profits)
        
        # Desvio padrão
        variance = sum((p - mean_return) ** 2 for p in profits) / len(profits)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
        
        # Assumindo ~252 trading days/ano, ~10 trades/dia
        # Risk free rate por trade
        daily_rf = self.RISK_FREE_RATE_ANNUAL / 252
        trade_rf = daily_rf / 10  # Aproximação
        
        sharpe = (mean_return - trade_rf) / std_dev
        
        # Anualizar (aproximação)
        # Assumindo 2500 trades/ano
        sharpe_annual = sharpe * math.sqrt(2500)
        
        return round(sharpe_annual, 2)
    
    def _calculate_sortino(self, profits: List[float]) -> float:
        """
        Calcula Sortino Ratio
        
        Sortino = (Retorno Médio - Risk Free) / Downside Deviation
        
        Similar ao Sharpe, mas só penaliza volatilidade negativa
        """
        if len(profits) < 2:
            return 0.0
        
        mean_return = sum(profits) / len(profits)
        
        # Apenas retornos negativos
        negative_returns = [p for p in profits if p < 0]
        
        if not negative_returns:
            return float('inf') if mean_return > 0 else 0.0
        
        # Downside deviation
        variance = sum(p ** 2 for p in negative_returns) / len(profits)
        downside_dev = math.sqrt(variance)
        
        if downside_dev == 0:
            return 0.0
        
        daily_rf = self.RISK_FREE_RATE_ANNUAL / 252
        trade_rf = daily_rf / 10
        
        sortino = (mean_return - trade_rf) / downside_dev
        
        # Anualizar
        sortino_annual = sortino * math.sqrt(2500)
        
        return round(sortino_annual, 2)
    
    def _calculate_drawdown(self, trades: List[TradeResult]) -> Dict:
        """Calcula drawdown máximo e atual"""
        if not trades:
            return {
                'max_dd': 0, 'max_dd_pct': 0,
                'current_dd': 0, 'current_dd_pct': 0
            }
        
        # Reconstruir equity curve
        balance = self.initial_balance
        peak = balance
        max_dd = 0
        max_dd_pct = 0
        
        for trade in trades:
            balance += trade.profit
            
            if balance > peak:
                peak = balance
            
            dd = peak - balance
            dd_pct = (dd / peak) * 100 if peak > 0 else 0
            
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        
        # Drawdown atual
        current_dd = self._peak_balance - self._current_balance
        current_dd_pct = (current_dd / self._peak_balance) * 100 if self._peak_balance > 0 else 0
        
        return {
            'max_dd': round(max_dd, 2),
            'max_dd_pct': round(max_dd_pct, 2),
            'current_dd': round(current_dd, 2),
            'current_dd_pct': round(current_dd_pct, 2)
        }
    
    def _calculate_annual_return(self, trades: List[TradeResult]) -> float:
        """Calcula retorno anualizado"""
        if not trades:
            return 0.0
        
        total_profit = sum(t.profit for t in trades)
        
        # Período em dias
        first = trades[0].timestamp
        last = trades[-1].timestamp
        days = max(1, (last - first).days)
        
        # Retorno total
        total_return = total_profit / self.initial_balance
        
        # Anualizar
        annual_return = total_return * (365 / days)
        
        return round(annual_return * 100, 2)
    
    def _calculate_sqn(self, profits: List[float]) -> Dict:
        """
        Calcula SQN (System Quality Number)
        
        Desenvolvido por Van K. Tharp
        SQN = (Média dos R-múltiplos / Desvio Padrão) × √N
        
        Onde N = número de trades (limitado a 100 para comparabilidade)
        
        Escala de Rating:
        - 1.6 - 1.9: Below average
        - 2.0 - 2.4: Average
        - 2.5 - 2.9: Good
        - 3.0 - 5.0: Excellent
        - 5.1 - 6.9: Superb
        - 7.0+: Holy Grail
        """
        if len(profits) < 10:
            return {'sqn': 0.0, 'rating': 'Dados insuficientes'}
        
        mean = sum(profits) / len(profits)
        
        # Desvio padrão
        variance = sum((p - mean) ** 2 for p in profits) / len(profits)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return {'sqn': 0.0, 'rating': 'N/A'}
        
        # Limitar N a 100 para comparabilidade
        n = min(len(profits), 100)
        
        sqn = (mean / std_dev) * math.sqrt(n)
        sqn = round(sqn, 2)
        
        # Rating
        if sqn < 1.6:
            rating = "⚠️ Fraco"
        elif sqn < 2.0:
            rating = "📉 Abaixo da média"
        elif sqn < 2.5:
            rating = "📊 Médio"
        elif sqn < 3.0:
            rating = "📈 Bom"
        elif sqn < 5.0:
            rating = "🌟 Excelente"
        elif sqn < 7.0:
            rating = "⭐ Soberbo"
        else:
            rating = "🏆 Holy Grail"
        
        return {'sqn': sqn, 'rating': rating}
    
    def _calculate_r_multiple(self, trades: List[TradeResult]) -> Dict:
        """
        Calcula R-múltiplos
        
        R = Risco inicial (distância do stop loss)
        R-múltiplo = Lucro/Prejuízo ÷ R
        
        Exemplo:
        - Trade ganhou $150, risco era $50 → R-múltiplo = 3R
        - Trade perdeu $25, risco era $50 → R-múltiplo = -0.5R
        """
        if not trades:
            return {'avg_r': 0.0, 'r_expectancy': 0.0}
        
        # Assumir R = avg_loss como proxy do risco médio
        losses = [abs(t.profit) for t in trades if t.profit < 0]
        
        if not losses:
            return {'avg_r': 0.0, 'r_expectancy': 0.0}
        
        avg_risk = sum(losses) / len(losses)
        
        if avg_risk == 0:
            return {'avg_r': 0.0, 'r_expectancy': 0.0}
        
        # Calcular R-múltiplos
        r_multiples = [t.profit / avg_risk for t in trades]
        
        avg_r = sum(r_multiples) / len(r_multiples)
        
        # R-Expectancy = média dos R-múltiplos
        r_expectancy = avg_r
        
        return {
            'avg_r': round(avg_r, 2),
            'r_expectancy': round(r_expectancy, 2)
        }
    
    def _calculate_duration_stats(self, trades: List[TradeResult]) -> Dict:
        """Calcula estatísticas de duração dos trades"""
        if not trades:
            return {'avg_all': 0, 'avg_win': 0, 'avg_loss': 0}
        
        all_durations = [t.duration_minutes for t in trades if t.duration_minutes > 0]
        win_durations = [t.duration_minutes for t in trades if t.profit > 0 and t.duration_minutes > 0]
        loss_durations = [t.duration_minutes for t in trades if t.profit < 0 and t.duration_minutes > 0]
        
        return {
            'avg_all': sum(all_durations) / len(all_durations) if all_durations else 0,
            'avg_win': sum(win_durations) / len(win_durations) if win_durations else 0,
            'avg_loss': sum(loss_durations) / len(loss_durations) if loss_durations else 0
        }
    
    def _calculate_streaks(self, profits: List[float]) -> Dict:
        """Calcula sequências de wins/losses"""
        if not profits:
            return {
                'current_wins': 0, 'current_losses': 0,
                'max_wins': 0, 'max_losses': 0
            }
        
        current_wins = 0
        current_losses = 0
        max_wins = 0
        max_losses = 0
        
        wins = 0
        losses = 0
        
        for p in profits:
            if p > 0:
                wins += 1
                losses = 0
                max_wins = max(max_wins, wins)
            elif p < 0:
                losses += 1
                wins = 0
                max_losses = max(max_losses, losses)
            else:
                # Break even - reset ambos
                wins = 0
                losses = 0
        
        return {
            'current_wins': wins,
            'current_losses': losses,
            'max_wins': max_wins,
            'max_losses': max_losses
        }
    
    def get_strategy_comparison(self) -> Dict[str, PerformanceMetrics]:
        """Compara métricas de todas as estratégias"""
        with self._lock:
            strategies = set(t.strategy for t in self._trades)
            
            comparison = {}
            for strategy in strategies:
                comparison[strategy] = self.calculate_metrics(strategy=strategy)
            
            return comparison
    
    def generate_report(self) -> str:
        """Gera relatório de performance"""
        metrics = self.calculate_metrics()
        
        lines = []
        lines.append("=" * 60)
        lines.append("📊 ADVANCED PERFORMANCE METRICS REPORT")
        lines.append("=" * 60)
        lines.append("")
        
        # Básicas
        lines.append("📈 MÉTRICAS BÁSICAS:")
        lines.append(f"  Total Trades: {metrics.total_trades}")
        lines.append(f"  Win Rate: {metrics.win_rate*100:.1f}%")
        lines.append(f"  Profit Factor: {metrics.profit_factor:.2f}")
        lines.append("")
        
        # Financeiras
        lines.append("💰 FINANCEIRAS:")
        lines.append(f"  Total Profit: ${metrics.total_profit:,.2f}")
        lines.append(f"  Gross Profit: ${metrics.gross_profit:,.2f}")
        lines.append(f"  Gross Loss: ${metrics.gross_loss:,.2f}")
        lines.append(f"  Avg Profit/Trade: ${metrics.avg_profit:,.2f}")
        lines.append("")
        
        # Avançadas
        lines.append("📐 MÉTRICAS AVANÇADAS:")
        lines.append(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        lines.append(f"  Sortino Ratio: {metrics.sortino_ratio:.2f}")
        lines.append(f"  Calmar Ratio: {metrics.calmar_ratio:.2f}")
        lines.append(f"  Recovery Factor: {metrics.recovery_factor:.2f}")
        lines.append("")
        
        # SQN
        lines.append("🎯 SYSTEM QUALITY NUMBER (SQN):")
        lines.append(f"  SQN: {metrics.sqn:.2f}")
        lines.append(f"  Rating: {metrics.sqn_rating}")
        lines.append("")
        
        # R-Multiple
        lines.append("📊 R-MÚLTIPLO:")
        lines.append(f"  Avg R-Multiple: {metrics.avg_r_multiple:.2f}R")
        lines.append(f"  R-Expectancy: {metrics.r_expectancy:.2f}R")
        lines.append("")
        
        # Drawdown
        lines.append("📉 DRAWDOWN:")
        lines.append(f"  Max Drawdown: ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.1f}%)")
        lines.append(f"  Current DD: ${metrics.current_drawdown:,.2f} ({metrics.current_drawdown_pct:.1f}%)")
        lines.append("")
        
        # Expectancy
        lines.append("🎯 EXPECTANCY:")
        lines.append(f"  Por Trade: ${metrics.expectancy:,.2f}")
        lines.append(f"  Em Pips: {metrics.expectancy_pips:.1f} pips")
        lines.append("")
        
        # Duração
        lines.append("⏱️ DURAÇÃO MÉDIA:")
        lines.append(f"  Todos: {metrics.avg_trade_duration_minutes:.0f} min")
        lines.append(f"  Wins: {metrics.avg_win_duration_minutes:.0f} min")
        lines.append(f"  Losses: {metrics.avg_loss_duration_minutes:.0f} min")
        lines.append("")
        
        # Streaks
        lines.append("🔥 SEQUÊNCIAS:")
        lines.append(f"  Max Wins Consecutivas: {metrics.max_consecutive_wins}")
        lines.append(f"  Max Losses Consecutivas: {metrics.max_consecutive_losses}")
        lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Singleton
_calculator: Optional[AdvancedMetricsCalculator] = None


def get_metrics_calculator(
    initial_balance: float = 10000.0
) -> AdvancedMetricsCalculator:
    """Obtém instância singleton do calculador"""
    global _calculator
    if _calculator is None:
        _calculator = AdvancedMetricsCalculator(initial_balance)
    return _calculator
