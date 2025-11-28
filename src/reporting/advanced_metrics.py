"""
Advanced Performance Metrics Calculator
Calcula métricas usadas por traders profissionais e fundos quantitativos
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger


class AdvancedMetrics:
    """
    Calculadora de métricas avançadas de performance
    
    Métricas:
    - Sharpe Ratio
    - Sortino Ratio
    - Calmar Ratio
    - Profit Factor
    - Recovery Factor
    - Win Rate Weighted
    - Average R Multiple
    - Expectancy
    """
    
    def __init__(self, trades: List[Dict], risk_free_rate: float = 0.04):
        """
        Args:
            trades: Lista de trades com 'profit', 'timestamp', 'strategy'
            risk_free_rate: Taxa livre de risco anualizada (default: 4%)
        """
        self.trades = trades
        self.risk_free_rate = risk_free_rate
        self.df = self._prepare_dataframe()
    
    def _prepare_dataframe(self) -> pd.DataFrame:
        """Converte trades para DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['profit'] = pd.to_numeric(df['profit'])
        return df.sort_values('timestamp')
    
    def calculate_all_metrics(self) -> Dict:
        """
        Calcula todas as métricas avançadas
        
        Returns:
            Dict com todas as métricas
        """
        if len(self.trades) < 10:
            return {
                'error': 'Mínimo 10 trades necessários',
                'trades_count': len(self.trades)
            }
        
        metrics = {
            'sharpe_ratio': self.sharpe_ratio(),
            'sortino_ratio': self.sortino_ratio(),
            'calmar_ratio': self.calmar_ratio(),
            'profit_factor': self.profit_factor(),
            'recovery_factor': self.recovery_factor(),
            'win_rate': self.win_rate(),
            'win_rate_weighted': self.win_rate_weighted(),
            'avg_r_multiple': self.avg_r_multiple(),
            'expectancy': self.expectancy(),
            'max_drawdown': self.max_drawdown(),
            'avg_win': self.avg_win(),
            'avg_loss': self.avg_loss(),
            'largest_win': self.largest_win(),
            'largest_loss': self.largest_loss(),
            'consecutive_wins': self.consecutive_wins(),
            'consecutive_losses': self.consecutive_losses(),
            'total_profit': self.total_profit(),
            'total_trades': len(self.trades)
        }
        
        return metrics
    
    def sharpe_ratio(self, periods_per_year: int = 252) -> float:
        """
        Sharpe Ratio: (Retorno - RiskFree) / Volatilidade
        
        > 1.0 = Bom
        > 2.0 = Muito Bom
        > 3.0 = Excepcional
        
        Args:
            periods_per_year: 252 para trading diário
        """
        returns = self.df['profit'].values
        
        if len(returns) < 2:
            return 0.0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Anualizar
        sharpe = (avg_return - (self.risk_free_rate / periods_per_year)) / std_return
        sharpe_annual = sharpe * np.sqrt(periods_per_year)
        
        return round(sharpe_annual, 2)
    
    def sortino_ratio(self, periods_per_year: int = 252) -> float:
        """
        Sortino Ratio: Similar ao Sharpe mas penaliza apenas volatilidade negativa
        
        Melhor que Sharpe pois não penaliza volatilidade positiva (lucros grandes)
        
        > 1.5 = Bom
        > 2.0 = Muito Bom
        > 3.0 = Excepcional
        """
        returns = self.df['profit'].values
        
        if len(returns) < 2:
            return 0.0
        
        avg_return = np.mean(returns)
        
        # Apenas desvio negativo (downside deviation)
        negative_returns = returns[returns < 0]
        
        if len(negative_returns) == 0:
            return float('inf')  # Sem perdas!
        
        downside_std = np.std(negative_returns)
        
        if downside_std == 0:
            return 0.0
        
        sortino = (avg_return - (self.risk_free_rate / periods_per_year)) / downside_std
        sortino_annual = sortino * np.sqrt(periods_per_year)
        
        return round(sortino_annual, 2)
    
    def calmar_ratio(self) -> float:
        """
        Calmar Ratio: Retorno Anualizado / Max Drawdown
        
        > 1.0 = Bom
        > 3.0 = Muito Bom
        > 5.0 = Excepcional
        """
        max_dd = self.max_drawdown()
        
        if max_dd == 0:
            return float('inf')
        
        # Calcular retorno anualizado
        total_profit = self.total_profit()
        days = (self.df['timestamp'].max() - self.df['timestamp'].min()).days
        
        if days == 0:
            return 0.0
        
        annual_return = (total_profit / days) * 365
        
        calmar = annual_return / abs(max_dd)
        
        return round(calmar, 2)
    
    def profit_factor(self) -> float:
        """
        Profit Factor: Gross Profit / Gross Loss
        
        > 1.5 = Bom
        > 2.0 = Muito Bom
        > 3.0 = Excepcional
        """
        profits = self.df[self.df['profit'] > 0]['profit'].sum()
        losses = abs(self.df[self.df['profit'] < 0]['profit'].sum())
        
        if losses == 0:
            return float('inf')
        
        return round(profits / losses, 2)
    
    def recovery_factor(self) -> float:
        """
        Recovery Factor: Net Profit / Max Drawdown
        
        Mede capacidade de recuperação
        
        > 2.0 = Bom
        > 5.0 = Muito Bom
        > 10.0 = Excepcional
        """
        net_profit = self.total_profit()
        max_dd = abs(self.max_drawdown())
        
        if max_dd == 0:
            return float('inf')
        
        return round(net_profit / max_dd, 2)
    
    def win_rate(self) -> float:
        """Win Rate simples (%)"""
        wins = len(self.df[self.df['profit'] > 0])
        total = len(self.df)
        
        return round((wins / total) * 100, 1) if total > 0 else 0.0
    
    def win_rate_weighted(self) -> float:
        """
        Win Rate ponderado pelo tamanho
        
        Considera que ganhar $100 em 1 trade > ganhar $10 em 10 trades
        """
        total_wins = self.df[self.df['profit'] > 0]['profit'].sum()
        total_amount = abs(self.df['profit']).sum()
        
        if total_amount == 0:
            return 0.0
        
        return round((total_wins / total_amount) * 100, 1)
    
    def avg_r_multiple(self) -> float:
        """
        R Múltiplo médio (quantos R ganha por trade)
        
        > 0.5 = Positivo
        > 1.0 = Bom
        > 2.0 = Excepcional
        """
        # Assumir que 1R = média das perdas
        avg_loss = abs(self.avg_loss())
        
        if avg_loss == 0:
            return 0.0
        
        avg_profit = self.df['profit'].mean()
        
        return round(avg_profit / avg_loss, 2)
    
    def expectancy(self) -> float:
        """
        Expectancy: Quanto espera ganhar por trade
        
        Formula: (WR × AvgWin) - (LR × AvgLoss)
        
        > 0 = Positivo (lucrativo no longo prazo)
        """
        wr = self.win_rate() / 100
        lr = 1 - wr
        avg_win = self.avg_win()
        avg_loss = abs(self.avg_loss())
        
        expectancy = (wr * avg_win) - (lr * avg_loss)
        
        return round(expectancy, 2)
    
    def max_drawdown(self) -> float:
        """Máximo drawdown em $"""
        cumulative = self.df['profit'].cumsum()
        running_max = cumulative.cummax()
        drawdown = cumulative - running_max
        
        return round(drawdown.min(), 2)
    
    def avg_win(self) -> float:
        """Média dos ganhos"""
        wins = self.df[self.df['profit'] > 0]['profit']
        return round(wins.mean(), 2) if len(wins) > 0 else 0.0
    
    def avg_loss(self) -> float:
        """Média das perdas"""
        losses = self.df[self.df['profit'] < 0]['profit']
        return round(losses.mean(), 2) if len(losses) > 0 else 0.0
    
    def largest_win(self) -> float:
        """Maior ganho"""
        return round(self.df['profit'].max(), 2)
    
    def largest_loss(self) -> float:
        """Maior perda"""
        return round(self.df['profit'].min(), 2)
    
    def consecutive_wins(self) -> int:
        """Maior sequência de vitórias"""
        wins = (self.df['profit'] > 0).astype(int)
        return self._max_consecutive(wins)
    
    def consecutive_losses(self) -> int:
        """Maior sequência de perdas"""
        losses = (self.df['profit'] < 0).astype(int)
        return self._max_consecutive(losses)
    
    def _max_consecutive(self, series: pd.Series) -> int:
        """Calcula máximo consecutivo de 1s"""
        max_count = 0
        current_count = 0
        
        for val in series:
            if val == 1:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count
    
    def total_profit(self) -> float:
        """Lucro total"""
        return round(self.df['profit'].sum(), 2)
    
    def print_report(self):
        """Imprime relatório formatado"""
        metrics = self.calculate_all_metrics()
        
        if 'error' in metrics:
            print(f"⚠️  {metrics['error']}")
            return
        
        print("\n" + "="*70)
        print("📊 RELATÓRIO DE PERFORMANCE AVANÇADO")
        print("="*70)
        
        print(f"\n🎯 MÉTRICAS DE QUALIDADE:")
        print(f"   Sharpe Ratio:        {metrics['sharpe_ratio']:>8.2f}  {'✅' if metrics['sharpe_ratio'] > 1.0 else '⚠️'}")
        print(f"   Sortino Ratio:       {metrics['sortino_ratio']:>8.2f}  {'✅' if metrics['sortino_ratio'] > 1.5 else '⚠️'}")
        print(f"   Calmar Ratio:        {metrics['calmar_ratio']:>8.2f}  {'✅' if metrics['calmar_ratio'] > 1.0 else '⚠️'}")
        print(f"   Profit Factor:       {metrics['profit_factor']:>8.2f}  {'✅' if metrics['profit_factor'] > 1.5 else '⚠️'}")
        print(f"   Recovery Factor:     {metrics['recovery_factor']:>8.2f}  {'✅' if metrics['recovery_factor'] > 2.0 else '⚠️'}")
        
        print(f"\n💰 MÉTRICAS DE LUCRO:")
        print(f"   Win Rate:            {metrics['win_rate']:>7.1f}%  {'✅' if metrics['win_rate'] > 50 else '⚠️'}")
        print(f"   Win Rate Weighted:   {metrics['win_rate_weighted']:>7.1f}%")
        print(f"   Avg R Multiple:      {metrics['avg_r_multiple']:>8.2f}R")
        print(f"   Expectancy:         ${metrics['expectancy']:>8.2f}  {'✅' if metrics['expectancy'] > 0 else '❌'}")
        
        print(f"\n📈 ESTATÍSTICAS:")
        print(f"   Total Profit:       ${metrics['total_profit']:>8.2f}")
        print(f"   Max Drawdown:       ${metrics['max_drawdown']:>8.2f}")
        print(f"   Avg Win:            ${metrics['avg_win']:>8.2f}")
        print(f"   Avg Loss:           ${metrics['avg_loss']:>8.2f}")
        print(f"   Largest Win:        ${metrics['largest_win']:>8.2f}")
        print(f"   Largest Loss:       ${metrics['largest_loss']:>8.2f}")
        
        print(f"\n🔄 SEQUÊNCIAS:")
        print(f"   Max Consecutive Wins:   {metrics['consecutive_wins']}")
        print(f"   Max Consecutive Losses: {metrics['consecutive_losses']}")
        
        print(f"\n📊 TOTAL: {metrics['total_trades']} trades")
        print("="*70 + "\n")


def analyze_strategy_performance(strategy_name: str, trades: List[Dict]):
    """
    Analisa performance de uma estratégia específica
    
    Args:
        strategy_name: Nome da estratégia
        trades: Lista de trades da estratégia
    """
    print(f"\n{'='*70}")
    print(f"📊 ANÁLISE: {strategy_name.upper()}")
    print(f"{'='*70}")
    
    calculator = AdvancedMetrics(trades)
    calculator.print_report()


# Exemplo de uso
if __name__ == "__main__":
    # Dados de teste
    test_trades = [
        {'profit': 50, 'timestamp': '2025-01-01 10:00', 'strategy': 'scalping'},
        {'profit': -20, 'timestamp': '2025-01-01 11:00', 'strategy': 'scalping'},
        {'profit': 75, 'timestamp': '2025-01-01 12:00', 'strategy': 'scalping'},
        {'profit': -15, 'timestamp': '2025-01-01 13:00', 'strategy': 'scalping'},
        {'profit': 100, 'timestamp': '2025-01-01 14:00', 'strategy': 'scalping'},
        {'profit': -30, 'timestamp': '2025-01-01 15:00', 'strategy': 'scalping'},
        {'profit': 60, 'timestamp': '2025-01-01 16:00', 'strategy': 'scalping'},
        {'profit': 45, 'timestamp': '2025-01-02 10:00', 'strategy': 'scalping'},
        {'profit': -25, 'timestamp': '2025-01-02 11:00', 'strategy': 'scalping'},
        {'profit': 80, 'timestamp': '2025-01-02 12:00', 'strategy': 'scalping'},
    ]
    
    calculator = AdvancedMetrics(test_trades)
    calculator.print_report()
