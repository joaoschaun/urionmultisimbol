"""
Urion Trading Bot - Core Module

Módulos principais:
- MT5Connector: Conexão com MetaTrader5
- ConfigManager: Gerenciamento de configurações
- StateManager: Gerenciamento de estado e recovery
- DisasterRecovery: Sistema de recuperação de desastres
"""
from .mt5_connector import MT5Connector
from .config_manager import ConfigManager
from .logger import setup_logger

# Novos módulos de estado e recovery
try:
    from .state_manager import (
        StateManager,
        BotState,
        PositionState,
        OrderState,
        MLModelState,
        StateSerializer,
        get_state_manager
    )
except ImportError:
    StateManager = None
    BotState = None
    PositionState = None
    OrderState = None
    MLModelState = None
    StateSerializer = None
    get_state_manager = None

try:
    from .disaster_recovery import (
        DisasterRecovery,
        DisasterType,
        RecoveryAction,
        DisasterEvent,
        CircuitBreaker,
        get_disaster_recovery
    )
except ImportError:
    DisasterRecovery = None
    DisasterType = None
    RecoveryAction = None
    DisasterEvent = None
    CircuitBreaker = None
    get_disaster_recovery = None

__all__ = [
    # Core original
    'MT5Connector', 
    'ConfigManager', 
    'setup_logger',
    # State Manager
    'StateManager',
    'BotState',
    'PositionState',
    'OrderState',
    'MLModelState',
    'StateSerializer',
    'get_state_manager',
    # Disaster Recovery
    'DisasterRecovery',
    'DisasterType',
    'RecoveryAction',
    'DisasterEvent',
    'CircuitBreaker',
    'get_disaster_recovery'
]
