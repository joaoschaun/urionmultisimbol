"""
Urion Trading Bot
Virtus Investimentos

Sistema de Trading Automatizado de Nível Institucional
"""

__version__ = "0.1.0-alpha"
__author__ = "Virtus Investimentos"
__email__ = "suporte@virtusinvestimentos.com.br"

from .core import MT5Connector, ConfigManager, setup_logger

__all__ = ['MT5Connector', 'ConfigManager', 'setup_logger']
