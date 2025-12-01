# -*- coding: utf-8 -*-
"""
Backtest Engine - Framework de Backtesting Robusto

Implementa:
- Walk-Forward Analysis
- Out-of-Sample Testing  
- Monte Carlo Simulation
- Custos Reais (spread, slippage, swap, comissão)
- Multi-regime testing
- Validação estatística
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Regimes de mercado"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    CRISIS = "crisis"


@dataclass
class TradeCost:
    """Custos reais de uma operação"""
    spread: float = 0.0          # Custo do spread
    commission: float = 0.0       # Comissão da corretora
    slippage: float = 0.0         # Slippage estimado
    swap: float = 0.0             # Swap overnight
    total: float = 0.0


@dataclass
class Trade:
    """Representa uma operação no backtest"""
    entry_time: datetime
    exit_time: Optional[datetime] = None
    symbol: str = ""
    direction: str = ""  # 'buy' ou 'sell'
    entry_price: float = 0.0
    exit_price: float = 0.0
    volume: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    # Resultados
    gross_profit: float = 0.0
    costs: TradeCost = field(default_factory=TradeCost)
    net_profit: float = 0.0
    
    # Meta
    strategy: str = ""
    regime: MarketRegime = MarketRegime.RANGING
    holding_period: int = 0  # minutos


@dataclass
class BacktestResult:
    """Resultado completo de um backtest"""
    # Identificação
    strategy: str = ""
    symbol: str = ""
    start_date: datetime = None
    end_date: datetime = None
    
    # Performance
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # Retornos
    gross_profit: float = 0.0
    total_costs: float = 0.0
    net_profit: float = 0.0
    
    # Métricas de Risco
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # dias
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Qualidade
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Estatísticas Avançadas
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    avg_holding_period: float = 0.0  # minutos
    
    # Monte Carlo
    mc_95_percentile_drawdown: float = 0.0
    mc_probability_of_ruin: float = 0.0
    
    # Trades individuais
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    # Validação
    is_statistically_significant: bool = False
    t_statistic: float = 0.0
    p_value: float = 0.0


@dataclass
class WalkForwardResult:
    """Resultado de Walk-Forward Analysis"""
    in_sample_results: List[BacktestResult] = field(default_factory=list)
    out_sample_results: List[BacktestResult] = field(default_factory=list)
    
    # Médias
    avg_is_sharpe: float = 0.0
    avg_oos_sharpe: float = 0.0
    
    # Robustez
    efficiency_ratio: float = 0.0  # OOS Sharpe / IS Sharpe
    consistency_score: float = 0.0  # % de períodos OOS lucrativos
    overfitting_score: float = 0.0  # Diferença IS vs OOS
    
    # Recomendação
    is_robust: bool = False
    recommendation: str = ""


class CostCalculator:
    """Calculadora de custos reais de trading"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Custos padrão por símbolo (ajustar conforme corretora)
        self.spread_pips = {
            'XAUUSD': 0.30,
            'EURUSD': 0.10,
            'GBPUSD': 0.15,
            'USDJPY': 0.10,
            'BTCUSD': 50.0,
            'DEFAULT': 0.20
        }
        
        self.commission_per_lot = {
            'XAUUSD': 7.0,
            'EURUSD': 7.0,
            'GBPUSD': 7.0,
            'BTCUSD': 0.0,
            'DEFAULT': 7.0
        }
        
        # Swap diário por lot (positivo/negativo depende da direção)
        self.swap_rates = {
            'XAUUSD': {'buy': -15.0, 'sell': 5.0},
            'EURUSD': {'buy': -8.0, 'sell': 3.0},
            'DEFAULT': {'buy': -5.0, 'sell': 2.0}
        }
    
    def calculate_costs(
        self, 
        symbol: str, 
        direction: str,
        volume: float, 
        holding_days: float,
        is_volatile_period: bool = False
    ) -> TradeCost:
        """Calcula custos totais de uma operação"""
        
        # Spread
        spread_pips = self.spread_pips.get(symbol, self.spread_pips['DEFAULT'])
        if is_volatile_period:
            spread_pips *= 2  # Spread dobra em alta volatilidade
        spread_cost = spread_pips * volume * 10  # pip value aproximado
        
        # Comissão
        commission = self.commission_per_lot.get(symbol, self.commission_per_lot['DEFAULT'])
        commission_cost = commission * volume * 2  # Entrada + saída
        
        # Slippage (estimado)
        slippage_pips = 0.1 if not is_volatile_period else 0.5
        slippage_cost = slippage_pips * volume * 10
        
        # Swap
        swap_rates = self.swap_rates.get(symbol, self.swap_rates['DEFAULT'])
        daily_swap = swap_rates[direction] * volume
        swap_cost = daily_swap * holding_days
        
        total = spread_cost + commission_cost + slippage_cost + swap_cost
        
        return TradeCost(
            spread=spread_cost,
            commission=commission_cost,
            slippage=slippage_cost,
            swap=swap_cost,
            total=total
        )


class MarketRegimeDetector:
    """Detecta regime de mercado"""
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
    
    def detect_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Detecta o regime atual do mercado"""
        if len(df) < self.lookback:
            return MarketRegime.RANGING
        
        recent = df.tail(self.lookback)
        
        # Calcular métricas
        returns = recent['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)  # Anualizada
        avg_return = returns.mean() * 252
        
        # ATR para volatilidade
        atr = self._calculate_atr(recent)
        atr_pct = atr / recent['close'].iloc[-1]
        
        # Tendência
        sma_fast = recent['close'].rolling(5).mean().iloc[-1]
        sma_slow = recent['close'].rolling(20).mean().iloc[-1]
        
        # Classificar regime
        if volatility > 0.30:  # Alta volatilidade
            if avg_return < -0.20:
                return MarketRegime.CRISIS
            return MarketRegime.HIGH_VOLATILITY
        
        if volatility < 0.10:
            return MarketRegime.LOW_VOLATILITY
        
        if sma_fast > sma_slow * 1.01:  # 1% acima
            return MarketRegime.TRENDING_UP
        elif sma_fast < sma_slow * 0.99:  # 1% abaixo
            return MarketRegime.TRENDING_DOWN
        
        return MarketRegime.RANGING
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcula ATR"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        
        return atr if not pd.isna(atr) else 0.0


class BacktestEngine:
    """
    Engine de Backtesting Robusto
    
    Features:
    - Walk-Forward Analysis
    - Out-of-Sample Testing
    - Monte Carlo Simulation
    - Custos Reais
    - Validação Estatística
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.cost_calculator = CostCalculator(self.config)
        self.regime_detector = MarketRegimeDetector()
        
        # Configurações
        self.initial_capital = self.config.get('backtest', {}).get('initial_capital', 10000)
        self.risk_per_trade = self.config.get('risk', {}).get('max_risk_per_trade', 0.02)
        
        logger.info("BacktestEngine inicializado")
    
    def run_backtest(
        self,
        strategy: Callable,
        data: pd.DataFrame,
        symbol: str = "XAUUSD",
        include_costs: bool = True
    ) -> BacktestResult:
        """
        Executa backtest em dados históricos
        
        Args:
            strategy: Função que gera sinais (recebe df, retorna 'buy', 'sell', 'hold')
            data: DataFrame com OHLCV
            symbol: Símbolo do ativo
            include_costs: Se deve incluir custos reais
            
        Returns:
            BacktestResult com métricas completas
        """
        result = BacktestResult(
            strategy=strategy.__name__ if hasattr(strategy, '__name__') else 'Unknown',
            symbol=symbol,
            start_date=data.index[0] if isinstance(data.index[0], datetime) else datetime.now(),
            end_date=data.index[-1] if isinstance(data.index[-1], datetime) else datetime.now()
        )
        
        trades = []
        equity = [self.initial_capital]
        current_position = None
        
        for i in range(100, len(data)):  # Precisa de histórico para indicadores
            current_data = data.iloc[:i+1]
            current_bar = data.iloc[i]
            
            # Detectar regime
            regime = self.regime_detector.detect_regime(current_data)
            
            # Gerar sinal
            try:
                signal = strategy(current_data)
            except Exception as e:
                logger.warning(f"Erro ao gerar sinal: {e}")
                signal = 'hold'
            
            # Processar sinal
            if current_position is None:
                # Sem posição, verificar entrada
                if signal in ['buy', 'sell']:
                    current_position = self._open_position(
                        current_bar, signal, symbol, regime, equity[-1]
                    )
            else:
                # Com posição, verificar saída
                exit_reason = self._check_exit(current_position, current_bar, signal)
                
                if exit_reason:
                    # Fechar posição
                    trade = self._close_position(
                        current_position, current_bar, include_costs
                    )
                    trades.append(trade)
                    equity.append(equity[-1] + trade.net_profit)
                    current_position = None
        
        # Fechar posição aberta no final
        if current_position:
            trade = self._close_position(current_position, data.iloc[-1], include_costs)
            trades.append(trade)
            equity.append(equity[-1] + trade.net_profit)
        
        # Calcular métricas
        result.trades = trades
        result.equity_curve = equity
        result = self._calculate_metrics(result)
        result = self._validate_statistically(result)
        
        return result
    
    def _open_position(
        self, 
        bar: pd.Series, 
        direction: str, 
        symbol: str,
        regime: MarketRegime,
        equity: float
    ) -> Trade:
        """Abre uma posição"""
        # Position sizing baseado em risco
        risk_amount = equity * self.risk_per_trade
        
        # ATR para SL (simplificado)
        atr = bar.get('atr', bar['high'] - bar['low'])
        sl_distance = atr * 2
        
        # Calcular volume
        pip_value = 10  # Simplificado
        volume = risk_amount / (sl_distance * pip_value)
        volume = max(0.01, min(volume, 1.0))  # Limitar entre 0.01 e 1.0
        
        entry_price = bar['close']
        
        if direction == 'buy':
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + (sl_distance * 2)  # RR 1:2
        else:
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - (sl_distance * 2)
        
        return Trade(
            entry_time=bar.name if isinstance(bar.name, datetime) else datetime.now(),
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime=regime
        )
    
    def _check_exit(self, position: Trade, bar: pd.Series, signal: str) -> Optional[str]:
        """Verifica condições de saída"""
        # Stop Loss
        if position.direction == 'buy':
            if bar['low'] <= position.stop_loss:
                return 'stop_loss'
            if bar['high'] >= position.take_profit:
                return 'take_profit'
        else:
            if bar['high'] >= position.stop_loss:
                return 'stop_loss'
            if bar['low'] <= position.take_profit:
                return 'take_profit'
        
        # Sinal contrário
        if position.direction == 'buy' and signal == 'sell':
            return 'signal_reversal'
        if position.direction == 'sell' and signal == 'buy':
            return 'signal_reversal'
        
        return None
    
    def _close_position(
        self, 
        position: Trade, 
        bar: pd.Series,
        include_costs: bool
    ) -> Trade:
        """Fecha uma posição"""
        position.exit_time = bar.name if isinstance(bar.name, datetime) else datetime.now()
        position.exit_price = bar['close']
        
        # Calcular lucro bruto
        if position.direction == 'buy':
            points = position.exit_price - position.entry_price
        else:
            points = position.entry_price - position.exit_price
        
        position.gross_profit = points * position.volume * 100  # Simplificado
        
        # Calcular holding period
        if position.entry_time and position.exit_time:
            delta = position.exit_time - position.entry_time
            position.holding_period = int(delta.total_seconds() / 60)
        
        # Calcular custos
        if include_costs:
            holding_days = position.holding_period / (60 * 24)
            position.costs = self.cost_calculator.calculate_costs(
                position.symbol,
                position.direction,
                position.volume,
                holding_days,
                is_volatile_period=position.regime == MarketRegime.HIGH_VOLATILITY
            )
            position.net_profit = position.gross_profit - position.costs.total
        else:
            position.net_profit = position.gross_profit
        
        return position
    
    def _calculate_metrics(self, result: BacktestResult) -> BacktestResult:
        """Calcula todas as métricas de performance"""
        trades = result.trades
        
        if not trades:
            return result
        
        # Básicas
        result.total_trades = len(trades)
        profits = [t.net_profit for t in trades]
        
        result.winning_trades = len([p for p in profits if p > 0])
        result.losing_trades = len([p for p in profits if p < 0])
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0
        
        # Retornos
        result.gross_profit = sum(t.gross_profit for t in trades)
        result.total_costs = sum(t.costs.total for t in trades)
        result.net_profit = sum(profits)
        
        # Wins/Losses
        wins = [p for p in profits if p > 0]
        losses = [abs(p) for p in profits if p < 0]
        
        result.avg_win = np.mean(wins) if wins else 0
        result.avg_loss = np.mean(losses) if losses else 0
        result.largest_win = max(wins) if wins else 0
        result.largest_loss = max(losses) if losses else 0
        
        # Profit Factor
        total_wins = sum(wins)
        total_losses = sum(losses)
        result.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Expectancy
        result.expectancy = (
            (result.win_rate * result.avg_win) - 
            ((1 - result.win_rate) * result.avg_loss)
        )
        
        # Drawdown
        equity = result.equity_curve
        peak = equity[0]
        max_dd = 0
        dd_start = 0
        max_dd_duration = 0
        
        for i, eq in enumerate(equity):
            if eq > peak:
                peak = eq
                dd_start = i
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
                max_dd_duration = i - dd_start
        
        result.max_drawdown = max_dd
        result.max_drawdown_duration = max_dd_duration
        
        # Sharpe Ratio (assumindo 252 dias de trading)
        returns = pd.Series(profits) / self.initial_capital
        if len(returns) > 1 and returns.std() > 0:
            result.sharpe_ratio = (returns.mean() * 252) / (returns.std() * np.sqrt(252))
        
        # Sortino Ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            result.sortino_ratio = (returns.mean() * 252) / (downside_returns.std() * np.sqrt(252))
        
        # Calmar Ratio
        if result.max_drawdown > 0:
            annual_return = result.net_profit / self.initial_capital
            result.calmar_ratio = annual_return / result.max_drawdown
        
        # Consecutive wins/losses
        result.consecutive_wins = self._max_consecutive(profits, lambda x: x > 0)
        result.consecutive_losses = self._max_consecutive(profits, lambda x: x < 0)
        
        # Holding period
        result.avg_holding_period = np.mean([t.holding_period for t in trades])
        
        return result
    
    def _max_consecutive(self, values: List[float], condition: Callable) -> int:
        """Calcula máximo de valores consecutivos que atendem condição"""
        max_count = 0
        current_count = 0
        
        for v in values:
            if condition(v):
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count
    
    def _validate_statistically(self, result: BacktestResult) -> BacktestResult:
        """Valida se resultados são estatisticamente significativos"""
        profits = [t.net_profit for t in result.trades]
        
        if len(profits) < 30:
            result.is_statistically_significant = False
            result.recommendation = "Poucos trades para validação estatística"
            return result
        
        # T-test: média de profits é significativamente > 0?
        from scipy import stats
        t_stat, p_value = stats.ttest_1samp(profits, 0)
        
        result.t_statistic = t_stat
        result.p_value = p_value
        
        # Significativo se p-value < 0.05 e t positivo
        result.is_statistically_significant = (p_value < 0.05 and t_stat > 0)
        
        return result
    
    def walk_forward_analysis(
        self,
        strategy: Callable,
        data: pd.DataFrame,
        symbol: str = "XAUUSD",
        n_splits: int = 5,
        train_ratio: float = 0.7
    ) -> WalkForwardResult:
        """
        Walk-Forward Analysis para evitar overfitting
        
        Divide dados em períodos e testa:
        - Treino em período N
        - Teste em período N+1
        
        Args:
            strategy: Função de estratégia
            data: Dados históricos
            symbol: Símbolo
            n_splits: Número de divisões
            train_ratio: Proporção de treino
            
        Returns:
            WalkForwardResult
        """
        result = WalkForwardResult()
        
        split_size = len(data) // n_splits
        
        for i in range(n_splits - 1):  # -1 porque último período é só teste
            # Período de treino (in-sample)
            train_start = i * split_size
            train_end = train_start + int(split_size * train_ratio)
            
            # Período de teste (out-of-sample)
            test_start = train_end
            test_end = (i + 1) * split_size
            
            train_data = data.iloc[train_start:train_end]
            test_data = data.iloc[test_start:test_end]
            
            # Backtest in-sample
            is_result = self.run_backtest(strategy, train_data, symbol)
            result.in_sample_results.append(is_result)
            
            # Backtest out-of-sample
            oos_result = self.run_backtest(strategy, test_data, symbol)
            result.out_sample_results.append(oos_result)
            
            logger.info(
                f"WF Split {i+1}: IS Sharpe={is_result.sharpe_ratio:.2f}, "
                f"OOS Sharpe={oos_result.sharpe_ratio:.2f}"
            )
        
        # Calcular métricas agregadas
        result.avg_is_sharpe = np.mean([r.sharpe_ratio for r in result.in_sample_results])
        result.avg_oos_sharpe = np.mean([r.sharpe_ratio for r in result.out_sample_results])
        
        # Efficiency Ratio (quão bem IS prevê OOS)
        if result.avg_is_sharpe > 0:
            result.efficiency_ratio = result.avg_oos_sharpe / result.avg_is_sharpe
        
        # Consistency (% de períodos OOS lucrativos)
        profitable_oos = sum(1 for r in result.out_sample_results if r.net_profit > 0)
        result.consistency_score = profitable_oos / len(result.out_sample_results)
        
        # Overfitting Score (quanto piora de IS para OOS)
        result.overfitting_score = result.avg_is_sharpe - result.avg_oos_sharpe
        
        # Determinar se é robusto
        result.is_robust = (
            result.efficiency_ratio > 0.5 and
            result.consistency_score >= 0.6 and
            result.avg_oos_sharpe > 0.5
        )
        
        # Recomendação
        if result.is_robust:
            result.recommendation = "✓ Estratégia robusta - Pronta para paper trading"
        elif result.efficiency_ratio < 0.3:
            result.recommendation = "⚠ Possível overfitting severo - Revisar estratégia"
        elif result.consistency_score < 0.5:
            result.recommendation = "⚠ Inconsistente - Necessita mais validação"
        else:
            result.recommendation = "⚠ Resultados marginais - Continuar otimização"
        
        return result
    
    def monte_carlo_simulation(
        self,
        result: BacktestResult,
        n_simulations: int = 10000
    ) -> Dict[str, float]:
        """
        Simulação Monte Carlo para avaliar robustez
        
        Embaralha a ordem dos trades para ver:
        - Distribuição de drawdowns possíveis
        - Probabilidade de ruína
        - Intervalo de confiança de retornos
        """
        profits = [t.net_profit for t in result.trades]
        
        if len(profits) < 10:
            return {
                'error': 'Poucos trades para Monte Carlo',
                'min_trades_required': 10
            }
        
        final_equities = []
        max_drawdowns = []
        
        for _ in range(n_simulations):
            # Embaralhar trades
            shuffled = np.random.permutation(profits)
            
            # Simular equity curve
            equity = [self.initial_capital]
            peak = self.initial_capital
            max_dd = 0
            
            for p in shuffled:
                new_equity = equity[-1] + p
                equity.append(new_equity)
                
                if new_equity > peak:
                    peak = new_equity
                
                dd = (peak - new_equity) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)
            
            final_equities.append(equity[-1])
            max_drawdowns.append(max_dd)
        
        # Calcular estatísticas
        mc_results = {
            'mean_final_equity': np.mean(final_equities),
            'median_final_equity': np.median(final_equities),
            'std_final_equity': np.std(final_equities),
            
            # Percentis de retorno
            'return_5th_percentile': np.percentile(final_equities, 5),
            'return_25th_percentile': np.percentile(final_equities, 25),
            'return_75th_percentile': np.percentile(final_equities, 75),
            'return_95th_percentile': np.percentile(final_equities, 95),
            
            # Drawdown
            'mean_max_drawdown': np.mean(max_drawdowns),
            'drawdown_95th_percentile': np.percentile(max_drawdowns, 95),
            'worst_case_drawdown': np.max(max_drawdowns),
            
            # Probabilidade de ruína (perder > 50%)
            'probability_of_ruin': sum(1 for eq in final_equities if eq < self.initial_capital * 0.5) / n_simulations,
            
            # Probabilidade de lucro
            'probability_of_profit': sum(1 for eq in final_equities if eq > self.initial_capital) / n_simulations,
        }
        
        # Atualizar result com MC
        result.mc_95_percentile_drawdown = mc_results['drawdown_95th_percentile']
        result.mc_probability_of_ruin = mc_results['probability_of_ruin']
        
        return mc_results
    
    def generate_report(self, result: BacktestResult, wf_result: WalkForwardResult = None) -> str:
        """Gera relatório completo do backtest"""
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         RELATÓRIO DE BACKTEST - URION                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

📊 INFORMAÇÕES GERAIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Estratégia: {result.strategy}
Símbolo: {result.symbol}
Período: {result.start_date} até {result.end_date}
Capital Inicial: ${self.initial_capital:,.2f}

📈 PERFORMANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total de Trades: {result.total_trades}
Trades Vencedores: {result.winning_trades} ({result.win_rate*100:.1f}%)
Trades Perdedores: {result.losing_trades}

Lucro Bruto: ${result.gross_profit:,.2f}
Custos Totais: ${result.total_costs:,.2f}
Lucro Líquido: ${result.net_profit:,.2f}
Retorno: {(result.net_profit/self.initial_capital)*100:.2f}%

📉 MÉTRICAS DE RISCO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Max Drawdown: {result.max_drawdown*100:.2f}%
Sharpe Ratio: {result.sharpe_ratio:.2f}
Sortino Ratio: {result.sortino_ratio:.2f}
Calmar Ratio: {result.calmar_ratio:.2f}

📊 QUALIDADE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Profit Factor: {result.profit_factor:.2f}
Expectancy: ${result.expectancy:.2f}
Média de Ganhos: ${result.avg_win:.2f}
Média de Perdas: ${result.avg_loss:.2f}
Maior Ganho: ${result.largest_win:.2f}
Maior Perda: ${result.largest_loss:.2f}

🔄 CONSISTÊNCIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Max Wins Consecutivos: {result.consecutive_wins}
Max Losses Consecutivos: {result.consecutive_losses}
Holding Period Médio: {result.avg_holding_period:.0f} minutos

🎯 MONTE CARLO (95% Confidence)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Drawdown 95th Percentile: {result.mc_95_percentile_drawdown*100:.2f}%
Probabilidade de Ruína: {result.mc_probability_of_ruin*100:.2f}%

📐 VALIDAÇÃO ESTATÍSTICA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
T-Statistic: {result.t_statistic:.3f}
P-Value: {result.p_value:.4f}
Estatisticamente Significativo: {"✓ SIM" if result.is_statistically_significant else "✗ NÃO"}
"""
        
        if wf_result:
            report += f"""

🔄 WALK-FORWARD ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sharpe In-Sample Médio: {wf_result.avg_is_sharpe:.2f}
Sharpe Out-of-Sample Médio: {wf_result.avg_oos_sharpe:.2f}
Efficiency Ratio: {wf_result.efficiency_ratio:.2f}
Consistency Score: {wf_result.consistency_score*100:.1f}%
Overfitting Score: {wf_result.overfitting_score:.2f}

Estratégia Robusta: {"✓ SIM" if wf_result.is_robust else "✗ NÃO"}
Recomendação: {wf_result.recommendation}
"""
        
        # Checklist final
        checks = [
            ("Sharpe > 1.0", result.sharpe_ratio > 1.0),
            ("Profit Factor > 1.5", result.profit_factor > 1.5),
            ("Max DD < 20%", result.max_drawdown < 0.20),
            ("Win Rate > 40%", result.win_rate > 0.40),
            ("Estatisticamente Significativo", result.is_statistically_significant),
            ("Prob. Ruína < 5%", result.mc_probability_of_ruin < 0.05),
        ]
        
        if wf_result:
            checks.append(("Walk-Forward Robusto", wf_result.is_robust))
        
        report += f"""

✅ CHECKLIST DE VALIDAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        passed = 0
        for check, status in checks:
            icon = "✓" if status else "✗"
            report += f"  {icon} {check}\n"
            if status:
                passed += 1
        
        score = passed / len(checks) * 100
        report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE FINAL: {passed}/{len(checks)} ({score:.0f}%)

"""
        if score >= 80:
            report += "🟢 RECOMENDAÇÃO: Pronto para PAPER TRADING"
        elif score >= 60:
            report += "🟡 RECOMENDAÇÃO: Necessita otimização antes de paper trading"
        else:
            report += "🔴 RECOMENDAÇÃO: Não usar em produção - Revisar estratégia"
        
        report += "\n"
        
        return report


# Instância global
_backtest_engine: Optional[BacktestEngine] = None


def get_backtest_engine(config: Dict[str, Any] = None) -> BacktestEngine:
    """Retorna instância singleton do backtest engine"""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine(config)
    return _backtest_engine


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Criar dados de exemplo
    np.random.seed(42)
    dates = pd.date_range(start='2020-01-01', end='2024-12-31', freq='1H')
    n = len(dates)
    
    # Simular preços
    returns = np.random.randn(n) * 0.001
    prices = 100 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.randn(n) * 0.001),
        'high': prices * (1 + abs(np.random.randn(n)) * 0.002),
        'low': prices * (1 - abs(np.random.randn(n)) * 0.002),
        'close': prices,
        'volume': np.random.randint(1000, 10000, n)
    }, index=dates)
    
    # Estratégia de exemplo
    def simple_ma_strategy(data: pd.DataFrame) -> str:
        if len(data) < 50:
            return 'hold'
        
        ma_fast = data['close'].rolling(20).mean().iloc[-1]
        ma_slow = data['close'].rolling(50).mean().iloc[-1]
        
        if ma_fast > ma_slow * 1.001:
            return 'buy'
        elif ma_fast < ma_slow * 0.999:
            return 'sell'
        return 'hold'
    
    # Executar backtest
    engine = get_backtest_engine()
    
    print("Executando backtest...")
    result = engine.run_backtest(simple_ma_strategy, df, "XAUUSD")
    
    print("\nExecutando Monte Carlo...")
    mc_results = engine.monte_carlo_simulation(result)
    
    print("\nExecutando Walk-Forward Analysis...")
    wf_result = engine.walk_forward_analysis(simple_ma_strategy, df, "XAUUSD")
    
    print("\n" + engine.generate_report(result, wf_result))
