# -*- coding: utf-8 -*-
"""
Monte Carlo Simulator
=====================
Simulacao de Monte Carlo para analise de risco e projecao de performance.

Funcionalidades:
- Simulacao de equity curve
- Projecao de drawdown
- Probabilidade de ruina
- Stress testing
- Analise de cenarios
- Confidence intervals
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger
import threading
from concurrent.futures import ThreadPoolExecutor


class ScenarioType(Enum):
    """Tipos de cenario de simulacao"""
    NORMAL = "normal"           # Condicoes normais de mercado
    BULL = "bull"               # Mercado em alta
    BEAR = "bear"               # Mercado em baixa
    HIGH_VOLATILITY = "high_vol" # Alta volatilidade
    LOW_VOLATILITY = "low_vol"   # Baixa volatilidade
    BLACK_SWAN = "black_swan"    # Evento extremo
    STRESS_TEST = "stress_test"  # Stress testing


@dataclass
class TradeStatistics:
    """Estatisticas de trades para simulacao"""
    win_rate: float
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float
    avg_trades_per_day: float
    profit_factor: float
    std_dev: float


@dataclass
class SimulationResult:
    """Resultado de uma simulacao"""
    final_balance: float
    max_drawdown: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    profit_factor: float
    sharpe_ratio: float
    calmar_ratio: float
    recovery_factor: float
    equity_curve: np.ndarray


@dataclass
class MonteCarloReport:
    """Relatorio completo de Monte Carlo"""
    simulations: int
    initial_balance: float
    days_simulated: int
    
    # Estatisticas de resultado final
    mean_final_balance: float
    median_final_balance: float
    std_final_balance: float
    min_final_balance: float
    max_final_balance: float
    
    # Percentis
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    
    # Risco
    probability_of_ruin: float  # Probabilidade de perder X%
    max_drawdown_mean: float
    max_drawdown_worst: float
    
    # Confianca
    confidence_intervals: Dict[int, Tuple[float, float]]  # {95: (low, high)}
    
    # Cenarios
    best_case: SimulationResult
    worst_case: SimulationResult
    median_case: SimulationResult


class MonteCarloSimulator:
    """
    Simulador de Monte Carlo para Trading
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.mc_config = self.config.get('monte_carlo', {})
        
        # Configuracoes
        self.default_simulations = self.mc_config.get('default_simulations', 1000)
        self.default_days = self.mc_config.get('default_days', 252)  # 1 ano de trading
        self.ruin_threshold = self.mc_config.get('ruin_threshold', 0.5)  # 50% perda
        self.max_workers = self.mc_config.get('max_workers', 4)
        
        # Cache de resultados
        self._cache: Dict[str, MonteCarloReport] = {}
        
        logger.info("MonteCarloSimulator inicializado")
    
    def calculate_trade_statistics(self, trades: List[Dict]) -> TradeStatistics:
        """Calcula estatisticas de trades historicos"""
        if not trades:
            # Retornar estatisticas padrao conservadoras
            return TradeStatistics(
                win_rate=0.5,
                avg_win=100.0,
                avg_loss=80.0,
                max_win=500.0,
                max_loss=200.0,
                avg_trades_per_day=2.0,
                profit_factor=1.25,
                std_dev=150.0
            )
        
        profits = [t.get('profit', 0) for t in trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        
        win_rate = len(wins) / len(profits) if profits else 0.5
        avg_win = np.mean(wins) if wins else 100.0
        avg_loss = abs(np.mean(losses)) if losses else 80.0
        max_win = max(wins) if wins else 500.0
        max_loss = abs(min(losses)) if losses else 200.0
        
        # Calcular trades por dia
        if len(trades) >= 2:
            first_date = trades[0].get('open_time', datetime.now())
            last_date = trades[-1].get('open_time', datetime.now())
            if isinstance(first_date, str):
                first_date = datetime.fromisoformat(first_date)
            if isinstance(last_date, str):
                last_date = datetime.fromisoformat(last_date)
            days = (last_date - first_date).days or 1
            avg_trades_per_day = len(trades) / days
        else:
            avg_trades_per_day = 2.0
        
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 1.0
        
        std_dev = np.std(profits) if len(profits) > 1 else 150.0
        
        return TradeStatistics(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_win=max_win,
            max_loss=max_loss,
            avg_trades_per_day=avg_trades_per_day,
            profit_factor=profit_factor,
            std_dev=std_dev
        )
    
    def _simulate_single_run(self, stats: TradeStatistics, initial_balance: float,
                            days: int, scenario: ScenarioType) -> SimulationResult:
        """Executa uma unica simulacao"""
        balance = initial_balance
        equity_curve = [balance]
        peak_balance = balance
        max_drawdown = 0
        winning_trades = 0
        losing_trades = 0
        
        # Ajustar parametros baseado no cenario
        win_rate = stats.win_rate
        avg_win = stats.avg_win
        avg_loss = stats.avg_loss
        trades_per_day = stats.avg_trades_per_day
        
        if scenario == ScenarioType.BULL:
            win_rate = min(0.95, win_rate * 1.2)
            avg_win *= 1.3
        elif scenario == ScenarioType.BEAR:
            win_rate = max(0.2, win_rate * 0.8)
            avg_loss *= 1.3
        elif scenario == ScenarioType.HIGH_VOLATILITY:
            avg_win *= 1.5
            avg_loss *= 1.5
        elif scenario == ScenarioType.LOW_VOLATILITY:
            avg_win *= 0.7
            avg_loss *= 0.7
        elif scenario == ScenarioType.BLACK_SWAN:
            # Evento extremo - grande perda
            balance -= initial_balance * 0.3  # 30% loss
            equity_curve.append(balance)
            win_rate = max(0.1, win_rate * 0.5)
        elif scenario == ScenarioType.STRESS_TEST:
            win_rate = max(0.2, win_rate * 0.6)
            avg_loss *= 2.0
        
        # Simular cada dia
        for _ in range(days):
            # Numero de trades neste dia (distribuicao Poisson)
            num_trades = np.random.poisson(trades_per_day)
            
            for _ in range(num_trades):
                # Determinar se e win ou loss
                if np.random.random() < win_rate:
                    # Trade vencedor
                    profit = np.random.exponential(avg_win)
                    profit = min(profit, stats.max_win)  # Cap
                    balance += profit
                    winning_trades += 1
                else:
                    # Trade perdedor
                    loss = np.random.exponential(avg_loss)
                    loss = min(loss, stats.max_loss)  # Cap
                    balance -= loss
                    losing_trades += 1
                
                equity_curve.append(balance)
                
                # Atualizar drawdown
                if balance > peak_balance:
                    peak_balance = balance
                else:
                    dd = (peak_balance - balance) / peak_balance
                    max_drawdown = max(max_drawdown, dd)
                
                # Verificar ruina
                if balance <= initial_balance * (1 - self.ruin_threshold):
                    break
            
            # Verificar ruina apos cada dia
            if balance <= initial_balance * (1 - self.ruin_threshold):
                break
        
        total_trades = winning_trades + losing_trades
        
        # Calcular metricas
        total_profit = balance - initial_balance
        
        if losing_trades > 0 and winning_trades > 0:
            profit_factor = (winning_trades * avg_win) / (losing_trades * avg_loss)
        else:
            profit_factor = 1.0
        
        # Sharpe ratio simplificado
        returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        # Calmar ratio
        calmar = (total_profit / initial_balance) / max_drawdown if max_drawdown > 0 else 0
        
        # Recovery factor
        recovery = total_profit / (max_drawdown * initial_balance) if max_drawdown > 0 else 0
        
        return SimulationResult(
            final_balance=balance,
            max_drawdown=max_drawdown * initial_balance,
            max_drawdown_pct=max_drawdown * 100,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            calmar_ratio=calmar,
            recovery_factor=recovery,
            equity_curve=np.array(equity_curve)
        )
    
    def run_simulation(self, trades: List[Dict] = None, stats: TradeStatistics = None,
                      initial_balance: float = 10000, simulations: int = None,
                      days: int = None, scenario: ScenarioType = ScenarioType.NORMAL) -> MonteCarloReport:
        """
        Executa simulacao de Monte Carlo completa
        """
        if stats is None:
            stats = self.calculate_trade_statistics(trades or [])
        
        simulations = simulations or self.default_simulations
        days = days or self.default_days
        
        logger.info(f"Iniciando Monte Carlo: {simulations} simulacoes, {days} dias, cenario {scenario.value}")
        
        results: List[SimulationResult] = []
        
        # Executar simulacoes em paralelo
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._simulate_single_run, stats, initial_balance, days, scenario)
                for _ in range(simulations)
            ]
            
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Erro na simulacao: {e}")
        
        # Analisar resultados
        final_balances = np.array([r.final_balance for r in results])
        max_drawdowns = np.array([r.max_drawdown_pct for r in results])
        
        # Calcular probabilidade de ruina
        ruin_count = len([b for b in final_balances if b <= initial_balance * (1 - self.ruin_threshold)])
        prob_ruin = ruin_count / len(results)
        
        # Percentis
        percentiles = np.percentile(final_balances, [5, 25, 50, 75, 95])
        
        # Intervalos de confianca
        confidence_intervals = {
            90: (np.percentile(final_balances, 5), np.percentile(final_balances, 95)),
            95: (np.percentile(final_balances, 2.5), np.percentile(final_balances, 97.5)),
            99: (np.percentile(final_balances, 0.5), np.percentile(final_balances, 99.5))
        }
        
        # Encontrar casos best/worst/median
        sorted_results = sorted(results, key=lambda r: r.final_balance)
        worst_case = sorted_results[0]
        best_case = sorted_results[-1]
        median_idx = len(sorted_results) // 2
        median_case = sorted_results[median_idx]
        
        report = MonteCarloReport(
            simulations=simulations,
            initial_balance=initial_balance,
            days_simulated=days,
            mean_final_balance=np.mean(final_balances),
            median_final_balance=np.median(final_balances),
            std_final_balance=np.std(final_balances),
            min_final_balance=np.min(final_balances),
            max_final_balance=np.max(final_balances),
            percentile_5=percentiles[0],
            percentile_25=percentiles[1],
            percentile_50=percentiles[2],
            percentile_75=percentiles[3],
            percentile_95=percentiles[4],
            probability_of_ruin=prob_ruin,
            max_drawdown_mean=np.mean(max_drawdowns),
            max_drawdown_worst=np.max(max_drawdowns),
            confidence_intervals=confidence_intervals,
            best_case=best_case,
            worst_case=worst_case,
            median_case=median_case
        )
        
        logger.info(f"Monte Carlo concluido. Media: ${report.mean_final_balance:.2f}, P(ruina): {prob_ruin:.2%}")
        
        return report
    
    def stress_test(self, trades: List[Dict] = None, stats: TradeStatistics = None,
                   initial_balance: float = 10000) -> Dict[str, MonteCarloReport]:
        """
        Executa stress test com multiplos cenarios
        """
        if stats is None:
            stats = self.calculate_trade_statistics(trades or [])
        
        scenarios = [
            ScenarioType.NORMAL,
            ScenarioType.BULL,
            ScenarioType.BEAR,
            ScenarioType.HIGH_VOLATILITY,
            ScenarioType.LOW_VOLATILITY,
            ScenarioType.BLACK_SWAN,
            ScenarioType.STRESS_TEST
        ]
        
        results = {}
        
        for scenario in scenarios:
            logger.info(f"Executando cenario: {scenario.value}")
            report = self.run_simulation(
                stats=stats,
                initial_balance=initial_balance,
                simulations=500,  # Menos simulacoes por cenario
                days=90,  # 3 meses
                scenario=scenario
            )
            results[scenario.value] = report
        
        return results
    
    def get_risk_metrics(self, report: MonteCarloReport) -> Dict:
        """
        Retorna metricas de risco resumidas
        """
        return {
            'expected_return': (report.mean_final_balance - report.initial_balance) / report.initial_balance * 100,
            'probability_profit': len([1 for r in [report.best_case, report.median_case, report.worst_case] 
                                      if r.final_balance > report.initial_balance]) / 3 * 100,
            'probability_ruin': report.probability_of_ruin * 100,
            'expected_max_drawdown': report.max_drawdown_mean,
            'worst_drawdown': report.max_drawdown_worst,
            'value_at_risk_95': report.initial_balance - report.percentile_5,
            'best_case_return': (report.max_final_balance - report.initial_balance) / report.initial_balance * 100,
            'worst_case_return': (report.min_final_balance - report.initial_balance) / report.initial_balance * 100,
            'sharpe_estimate': report.median_case.sharpe_ratio,
            'risk_reward_ratio': report.mean_final_balance / report.max_drawdown_mean if report.max_drawdown_mean > 0 else 0
        }
    
    def should_trade(self, report: MonteCarloReport, max_ruin_prob: float = 0.05,
                    min_expected_return: float = 10.0) -> Tuple[bool, str]:
        """
        Decide se deve continuar trading baseado no Monte Carlo
        """
        metrics = self.get_risk_metrics(report)
        
        reasons = []
        
        if report.probability_of_ruin > max_ruin_prob:
            reasons.append(f"Probabilidade de ruina muito alta: {report.probability_of_ruin:.1%}")
        
        expected_return = metrics['expected_return']
        if expected_return < min_expected_return:
            reasons.append(f"Retorno esperado muito baixo: {expected_return:.1f}%")
        
        if report.max_drawdown_mean > 30:
            reasons.append(f"Drawdown medio muito alto: {report.max_drawdown_mean:.1f}%")
        
        if reasons:
            return False, " | ".join(reasons)
        
        return True, f"OK - Retorno esperado: {expected_return:.1f}%, P(ruina): {report.probability_of_ruin:.1%}"


# Singleton
_mc_instance = None

def get_monte_carlo_simulator(config: Dict = None) -> MonteCarloSimulator:
    """Retorna instancia singleton"""
    global _mc_instance
    if _mc_instance is None:
        _mc_instance = MonteCarloSimulator(config)
    return _mc_instance
