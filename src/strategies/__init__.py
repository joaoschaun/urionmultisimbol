"""
Módulo de Estratégias de Trading
"""

from .base_strategy import BaseStrategy
from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .news_trading import NewsTradingStrategy
from .strategy_manager import StrategyManager

__all__ = [
    'BaseStrategy',
    'TrendFollowingStrategy',
    'MeanReversionStrategy',
    'BreakoutStrategy',
    'NewsTradingStrategy',
    'StrategyManager',
]
