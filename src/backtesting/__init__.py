"""
Backtesting Package - Motor de Backtesting e Otimização para Urion

Inclui:
- Engine de backtest com walk-forward analysis
- Paper trading para simulação realista
- Data manager para dados históricos
- Optimizer para otimização de parâmetros
"""
from .engine import BacktestEngine, BaseStrategy, BacktestResult, Trade, Position, OrderType
from .data_manager import DataManager, Timeframe, get_data_manager
from .optimizer import StrategyOptimizer, OptimizationResult, get_param_space

# Novos módulos robustos
try:
    from .backtest_engine import (
        BacktestEngine as RobustBacktestEngine,
        BacktestResult as RobustBacktestResult
    )
except ImportError:
    RobustBacktestEngine = None
    RobustBacktestResult = None

try:
    from .paper_trading import (
        PaperTradingEngine,
        PaperTrade,
        SimulatedFill
    )
except ImportError:
    PaperTradingEngine = None
    PaperTrade = None
    SimulatedFill = None

__all__ = [
    # Engine original
    'BacktestEngine',
    'BaseStrategy', 
    'BacktestResult',
    'Trade',
    'Position',
    'OrderType',
    # Data Manager
    'DataManager',
    'Timeframe',
    'get_data_manager',
    # Optimizer
    'StrategyOptimizer',
    'OptimizationResult',
    'get_param_space',
    # Novos módulos robustos
    'RobustBacktestEngine',
    'RobustBacktestResult',
    'PaperTradingEngine',
    'PaperTrade',
    'SimulatedFill'
]
