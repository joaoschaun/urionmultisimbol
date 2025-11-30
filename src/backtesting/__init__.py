"""
Backtesting Package - Motor de Backtesting e Otimização para Urion
"""
from .engine import BacktestEngine, BaseStrategy, BacktestResult, Trade, Position, OrderType
from .data_manager import DataManager, Timeframe, get_data_manager
from .optimizer import StrategyOptimizer, OptimizationResult, get_param_space

__all__ = [
    'BacktestEngine',
    'BaseStrategy', 
    'BacktestResult',
    'Trade',
    'Position',
    'OrderType',
    'DataManager',
    'Timeframe',
    'get_data_manager',
    'StrategyOptimizer',
    'OptimizationResult',
    'get_param_space'
]
