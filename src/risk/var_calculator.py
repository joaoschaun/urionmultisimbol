# -*- coding: utf-8 -*-
"""
Value at Risk (VaR) Calculator
==============================
Calcula Value at Risk e metricas relacionadas de risco.

Metodos implementados:
- VaR Historico
- VaR Parametrico (Gaussiano)
- VaR Monte Carlo
- Expected Shortfall (CVaR)
- Component VaR
- Marginal VaR
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
from scipy import stats as scipy_stats


class VaRMethod(Enum):
    """Metodos de calculo de VaR"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"
    EWMA = "ewma"  # Exponentially Weighted Moving Average


@dataclass
class VaRResult:
    """Resultado do calculo de VaR"""
    method: VaRMethod
    confidence_level: float  # Ex: 0.95 para 95%
    time_horizon: int  # Dias
    var_value: float  # Valor absoluto em risco
    var_percentage: float  # Percentual do portfolio
    expected_shortfall: float  # CVaR
    portfolio_value: float
    calculation_date: datetime = field(default_factory=datetime.now)


@dataclass
class RiskMetrics:
    """Metricas de risco completas"""
    var_95_1d: float  # VaR 95% 1 dia
    var_99_1d: float  # VaR 99% 1 dia
    var_95_10d: float  # VaR 95% 10 dias
    cvar_95: float  # Expected Shortfall 95%
    cvar_99: float  # Expected Shortfall 99%
    volatility_daily: float
    volatility_annual: float
    max_loss_historical: float
    beta: float  # Beta em relacao ao mercado
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float


class VaRCalculator:
    """
    Calculadora de Value at Risk
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.var_config = self.config.get('var', {})
        
        # Configuracoes padrao
        self.default_confidence = self.var_config.get('default_confidence', 0.95)
        self.default_horizon = self.var_config.get('default_horizon', 1)
        self.ewma_lambda = self.var_config.get('ewma_lambda', 0.94)
        self.min_observations = self.var_config.get('min_observations', 30)
        
        logger.info("VaRCalculator inicializado")
    
    def calculate_returns(self, prices: np.ndarray, method: str = 'log') -> np.ndarray:
        """Calcula retornos a partir de precos"""
        if method == 'log':
            return np.log(prices[1:] / prices[:-1])
        else:  # simple
            return (prices[1:] - prices[:-1]) / prices[:-1]
    
    def var_historical(self, returns: np.ndarray, portfolio_value: float,
                      confidence: float = 0.95, horizon: int = 1) -> VaRResult:
        """
        VaR Historico - usa distribuicao empirica dos retornos
        """
        if len(returns) < self.min_observations:
            logger.warning(f"Poucos dados para VaR historico: {len(returns)} < {self.min_observations}")
        
        # Percentil correspondente
        percentile = (1 - confidence) * 100
        var_return = np.percentile(returns, percentile)
        
        # Ajustar para horizonte (raiz quadrada do tempo)
        var_return_horizon = var_return * np.sqrt(horizon)
        
        # Valor em risco
        var_value = abs(var_return_horizon) * portfolio_value
        
        # Expected Shortfall (media das perdas alem do VaR)
        losses_beyond_var = returns[returns <= var_return]
        if len(losses_beyond_var) > 0:
            es_return = np.mean(losses_beyond_var)
            es_value = abs(es_return) * portfolio_value * np.sqrt(horizon)
        else:
            es_value = var_value
        
        return VaRResult(
            method=VaRMethod.HISTORICAL,
            confidence_level=confidence,
            time_horizon=horizon,
            var_value=var_value,
            var_percentage=abs(var_return_horizon) * 100,
            expected_shortfall=es_value,
            portfolio_value=portfolio_value
        )
    
    def var_parametric(self, returns: np.ndarray, portfolio_value: float,
                      confidence: float = 0.95, horizon: int = 1) -> VaRResult:
        """
        VaR Parametrico - assume distribuicao normal
        """
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Z-score para o nivel de confianca
        z_score = scipy_stats.norm.ppf(1 - confidence)
        
        # VaR
        var_return = mean_return + z_score * std_return
        var_return_horizon = var_return * np.sqrt(horizon)
        var_value = abs(var_return_horizon) * portfolio_value
        
        # Expected Shortfall para distribuicao normal
        # ES = mean - std * phi(z) / (1 - confidence)
        pdf_z = scipy_stats.norm.pdf(z_score)
        es_return = mean_return - std_return * pdf_z / (1 - confidence)
        es_value = abs(es_return) * portfolio_value * np.sqrt(horizon)
        
        return VaRResult(
            method=VaRMethod.PARAMETRIC,
            confidence_level=confidence,
            time_horizon=horizon,
            var_value=var_value,
            var_percentage=abs(var_return_horizon) * 100,
            expected_shortfall=es_value,
            portfolio_value=portfolio_value
        )
    
    def var_ewma(self, returns: np.ndarray, portfolio_value: float,
                confidence: float = 0.95, horizon: int = 1) -> VaRResult:
        """
        VaR com volatilidade EWMA (Exponentially Weighted Moving Average)
        Da mais peso a observacoes recentes
        """
        # Calcular volatilidade EWMA
        squared_returns = returns ** 2
        ewma_variance = np.zeros(len(squared_returns))
        ewma_variance[0] = squared_returns[0]
        
        for i in range(1, len(squared_returns)):
            ewma_variance[i] = self.ewma_lambda * ewma_variance[i-1] + \
                              (1 - self.ewma_lambda) * squared_returns[i]
        
        current_volatility = np.sqrt(ewma_variance[-1])
        
        # Z-score
        z_score = scipy_stats.norm.ppf(1 - confidence)
        
        # VaR
        var_return = z_score * current_volatility
        var_return_horizon = var_return * np.sqrt(horizon)
        var_value = abs(var_return_horizon) * portfolio_value
        
        # ES
        pdf_z = scipy_stats.norm.pdf(z_score)
        es_return = -current_volatility * pdf_z / (1 - confidence)
        es_value = abs(es_return) * portfolio_value * np.sqrt(horizon)
        
        return VaRResult(
            method=VaRMethod.EWMA,
            confidence_level=confidence,
            time_horizon=horizon,
            var_value=var_value,
            var_percentage=abs(var_return_horizon) * 100,
            expected_shortfall=es_value,
            portfolio_value=portfolio_value
        )
    
    def var_monte_carlo(self, returns: np.ndarray, portfolio_value: float,
                       confidence: float = 0.95, horizon: int = 1,
                       simulations: int = 10000) -> VaRResult:
        """
        VaR Monte Carlo - simula caminhos de preco
        """
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Simular retornos
        simulated_returns = np.random.normal(mean_return, std_return, (simulations, horizon))
        
        # Retorno acumulado para cada simulacao
        cumulative_returns = np.sum(simulated_returns, axis=1)
        
        # VaR
        percentile = (1 - confidence) * 100
        var_return = np.percentile(cumulative_returns, percentile)
        var_value = abs(var_return) * portfolio_value
        
        # ES
        losses_beyond_var = cumulative_returns[cumulative_returns <= var_return]
        if len(losses_beyond_var) > 0:
            es_return = np.mean(losses_beyond_var)
            es_value = abs(es_return) * portfolio_value
        else:
            es_value = var_value
        
        return VaRResult(
            method=VaRMethod.MONTE_CARLO,
            confidence_level=confidence,
            time_horizon=horizon,
            var_value=var_value,
            var_percentage=abs(var_return) * 100,
            expected_shortfall=es_value,
            portfolio_value=portfolio_value
        )
    
    def calculate_var(self, returns: np.ndarray, portfolio_value: float,
                     method: VaRMethod = VaRMethod.HISTORICAL,
                     confidence: float = 0.95, horizon: int = 1) -> VaRResult:
        """
        Calcula VaR usando o metodo especificado
        """
        if method == VaRMethod.HISTORICAL:
            return self.var_historical(returns, portfolio_value, confidence, horizon)
        elif method == VaRMethod.PARAMETRIC:
            return self.var_parametric(returns, portfolio_value, confidence, horizon)
        elif method == VaRMethod.EWMA:
            return self.var_ewma(returns, portfolio_value, confidence, horizon)
        elif method == VaRMethod.MONTE_CARLO:
            return self.var_monte_carlo(returns, portfolio_value, confidence, horizon)
        else:
            raise ValueError(f"Metodo VaR desconhecido: {method}")
    
    def calculate_all_vars(self, returns: np.ndarray, portfolio_value: float,
                          confidence: float = 0.95, horizon: int = 1) -> Dict[str, VaRResult]:
        """
        Calcula VaR usando todos os metodos
        """
        results = {}
        
        for method in VaRMethod:
            try:
                result = self.calculate_var(returns, portfolio_value, method, confidence, horizon)
                results[method.value] = result
            except Exception as e:
                logger.error(f"Erro no metodo {method.value}: {e}")
        
        return results
    
    def calculate_component_var(self, returns_matrix: np.ndarray, 
                               weights: np.ndarray,
                               portfolio_value: float,
                               confidence: float = 0.95) -> Dict[str, float]:
        """
        Calcula Component VaR para portfolio com multiplos ativos
        Mostra contribuicao de cada ativo para o VaR total
        """
        # Calcular VaR total do portfolio
        portfolio_returns = np.dot(returns_matrix, weights)
        total_var = self.var_parametric(portfolio_returns, portfolio_value, confidence)
        
        # Calcular contribuicao de cada componente
        cov_matrix = np.cov(returns_matrix.T)
        portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
        
        z_score = scipy_stats.norm.ppf(1 - confidence)
        
        component_vars = {}
        for i in range(len(weights)):
            # Marginal VaR
            marginal_var = z_score * np.dot(cov_matrix[i], weights) / np.sqrt(portfolio_variance)
            
            # Component VaR
            component_var = marginal_var * weights[i] * portfolio_value
            component_vars[f'asset_{i}'] = abs(component_var)
        
        component_vars['total'] = total_var.var_value
        
        return component_vars
    
    def calculate_risk_metrics(self, returns: np.ndarray, 
                              portfolio_value: float,
                              risk_free_rate: float = 0.02) -> RiskMetrics:
        """
        Calcula conjunto completo de metricas de risco
        """
        # VaRs
        var_95_1d = self.var_historical(returns, portfolio_value, 0.95, 1)
        var_99_1d = self.var_historical(returns, portfolio_value, 0.99, 1)
        var_95_10d = self.var_historical(returns, portfolio_value, 0.95, 10)
        
        # Volatilidade
        vol_daily = np.std(returns)
        vol_annual = vol_daily * np.sqrt(252)
        
        # Sharpe Ratio
        mean_return_annual = np.mean(returns) * 252
        sharpe = (mean_return_annual - risk_free_rate) / vol_annual if vol_annual > 0 else 0
        
        # Sortino Ratio (usa apenas downside deviation)
        negative_returns = returns[returns < 0]
        downside_deviation = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else vol_annual
        sortino = (mean_return_annual - risk_free_rate) / downside_deviation if downside_deviation > 0 else 0
        
        # Drawdown e Calmar
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = abs(np.min(drawdowns))
        calmar = mean_return_annual / max_drawdown if max_drawdown > 0 else 0
        
        # Max loss
        max_loss = abs(np.min(returns)) * portfolio_value
        
        return RiskMetrics(
            var_95_1d=var_95_1d.var_value,
            var_99_1d=var_99_1d.var_value,
            var_95_10d=var_95_10d.var_value,
            cvar_95=var_95_1d.expected_shortfall,
            cvar_99=var_99_1d.expected_shortfall,
            volatility_daily=vol_daily * 100,
            volatility_annual=vol_annual * 100,
            max_loss_historical=max_loss,
            beta=1.0,  # Placeholder - precisaria de dados do benchmark
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar
        )
    
    def stress_var(self, returns: np.ndarray, portfolio_value: float,
                  stress_factor: float = 2.0) -> VaRResult:
        """
        VaR estressado - aumenta volatilidade por um fator
        Usado em stress testing
        """
        stressed_returns = returns * stress_factor
        return self.var_historical(stressed_returns, portfolio_value, 0.99, 10)
    
    def check_var_breach(self, actual_loss: float, var_result: VaRResult) -> Dict:
        """
        Verifica se houve violacao do VaR
        """
        breached = actual_loss > var_result.var_value
        
        return {
            'breached': breached,
            'actual_loss': actual_loss,
            'var_limit': var_result.var_value,
            'excess': actual_loss - var_result.var_value if breached else 0,
            'excess_percentage': ((actual_loss / var_result.var_value) - 1) * 100 if breached else 0,
            'severity': 'critical' if actual_loss > var_result.expected_shortfall else 'high' if breached else 'normal'
        }
    
    def get_position_size_from_var(self, max_var: float, returns: np.ndarray,
                                   confidence: float = 0.95) -> float:
        """
        Calcula tamanho maximo de posicao baseado no VaR desejado
        """
        # VaR percentual
        percentile = (1 - confidence) * 100
        var_pct = abs(np.percentile(returns, percentile))
        
        if var_pct == 0:
            return 0
        
        # Tamanho maximo = VaR desejado / VaR percentual
        max_position = max_var / var_pct
        
        return max_position
    
    def generate_risk_report(self, returns: np.ndarray, 
                            portfolio_value: float) -> Dict:
        """
        Gera relatorio completo de risco
        """
        # Calcular todas as metricas
        metrics = self.calculate_risk_metrics(returns, portfolio_value)
        
        # VaR por diferentes metodos
        all_vars = self.calculate_all_vars(returns, portfolio_value)
        
        # Stress VaR
        stress_var = self.stress_var(returns, portfolio_value)
        
        return {
            'portfolio_value': portfolio_value,
            'metrics': {
                'var_95_1d': metrics.var_95_1d,
                'var_99_1d': metrics.var_99_1d,
                'var_95_10d': metrics.var_95_10d,
                'cvar_95': metrics.cvar_95,
                'cvar_99': metrics.cvar_99,
                'volatility_daily': f"{metrics.volatility_daily:.2f}%",
                'volatility_annual': f"{metrics.volatility_annual:.2f}%",
                'sharpe_ratio': metrics.sharpe_ratio,
                'sortino_ratio': metrics.sortino_ratio,
                'calmar_ratio': metrics.calmar_ratio,
                'max_loss': metrics.max_loss_historical
            },
            'var_by_method': {
                method: {
                    'value': result.var_value,
                    'percentage': f"{result.var_percentage:.2f}%",
                    'expected_shortfall': result.expected_shortfall
                }
                for method, result in all_vars.items()
            },
            'stress_test': {
                'var_stressed': stress_var.var_value,
                'percentage': f"{stress_var.var_percentage:.2f}%"
            },
            'recommendations': self._generate_recommendations(metrics)
        }
    
    def _generate_recommendations(self, metrics: RiskMetrics) -> List[str]:
        """Gera recomendacoes baseadas nas metricas"""
        recommendations = []
        
        if metrics.volatility_annual > 30:
            recommendations.append("Volatilidade alta - considere reduzir tamanho das posicoes")
        
        if metrics.sharpe_ratio < 0.5:
            recommendations.append("Sharpe ratio baixo - revisar estrategia de risco/retorno")
        
        if metrics.var_99_1d > metrics.var_95_1d * 2:
            recommendations.append("Fat tails detectadas - aumentar margem de seguranca")
        
        if metrics.calmar_ratio < 1:
            recommendations.append("Drawdown historico alto - implementar stops mais apertados")
        
        if not recommendations:
            recommendations.append("Metricas de risco dentro dos parametros aceitaveis")
        
        return recommendations


# Singleton
_var_instance = None

def get_var_calculator(config: Dict = None) -> VaRCalculator:
    """Retorna instancia singleton"""
    global _var_instance
    if _var_instance is None:
        _var_instance = VaRCalculator(config)
    return _var_instance
