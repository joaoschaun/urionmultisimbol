"""
Tests for Risk Manager
"""
import pytest
from unittest.mock import Mock, MagicMock
from src.risk_manager import RiskManager


@pytest.fixture
def mock_config():
    """Mock configuration"""
    return {
        'risk': {
            'max_risk_per_trade': 0.02,
            'max_drawdown': 0.15,
            'max_daily_loss': 0.05,
            'stop_loss_pips': 20,
            'take_profit_multiplier': 2.0,
            'trailing_stop_distance': 15,
            'break_even_enabled': True,
            'break_even_trigger': 15
        },
        'trading': {
            'symbol': 'XAUUSD',
            'max_daily_trades': 10,
            'max_open_positions': 3,
            'max_lot_size': 1.0,
            'spread_threshold': 30
        }
    }


@pytest.fixture
def mock_mt5():
    """Mock MT5 connector"""
    mt5 = Mock()
    
    # Mock account info
    mt5.get_account_info.return_value = {
        'balance': 10000.0,
        'equity': 10000.0,
        'margin': 0.0,
        'free_margin': 10000.0,
        'margin_level': 0.0,
        'leverage': 100
    }
    
    # Mock symbol info
    mt5.get_symbol_info.return_value = {
        'trade_contract_size': 100,
        'point': 0.01,
        'volume_min': 0.01,
        'volume_max': 100.0,
        'volume_step': 0.01,
        'digits': 2,
        'ask': 1950.00,
        'bid': 1949.90,
        'spread': 10
    }
    
    # Mock open positions
    mt5.get_open_positions.return_value = []
    
    return mt5


@pytest.fixture
def risk_manager(mock_config, mock_mt5):
    """Create Risk Manager instance"""
    return RiskManager(mock_config, mock_mt5)


def test_risk_manager_initialization(risk_manager):
    """Test Risk Manager initialization"""
    assert risk_manager.max_risk_per_trade == 0.02
    assert risk_manager.max_drawdown == 0.15
    assert risk_manager.max_daily_loss == 0.05
    assert risk_manager.daily_trades == 0
    assert risk_manager.daily_profit == 0.0


def test_calculate_position_size(risk_manager):
    """Test position size calculation"""
    lot_size = risk_manager.calculate_position_size(
        symbol='XAUUSD',
        entry_price=1950.00,
        stop_loss=1945.00,
        risk_percent=0.02
    )
    
    assert lot_size > 0
    assert lot_size <= 1.0  # Max lot size
    assert lot_size >= 0.01  # Min lot size


def test_calculate_stop_loss_buy(risk_manager):
    """Test stop loss calculation for BUY"""
    stop_loss = risk_manager.calculate_stop_loss(
        symbol='XAUUSD',
        order_type='BUY',
        entry_price=1950.00
    )
    
    assert stop_loss < 1950.00
    assert stop_loss > 0


def test_calculate_stop_loss_sell(risk_manager):
    """Test stop loss calculation for SELL"""
    stop_loss = risk_manager.calculate_stop_loss(
        symbol='XAUUSD',
        order_type='SELL',
        entry_price=1950.00
    )
    
    assert stop_loss > 1950.00


def test_calculate_take_profit(risk_manager):
    """Test take profit calculation"""
    entry_price = 1950.00
    stop_loss = 1945.00
    
    take_profit = risk_manager.calculate_take_profit(
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_reward_ratio=2.0
    )
    
    # TP should be 2x SL distance from entry
    sl_distance = entry_price - stop_loss
    expected_tp = entry_price + (sl_distance * 2)
    
    assert abs(take_profit - expected_tp) < 0.01


def test_can_open_position_allowed(risk_manager):
    """Test position validation - should allow"""
    result = risk_manager.can_open_position(
        symbol='XAUUSD',
        order_type='BUY',
        lot_size=0.01
    )
    
    assert result['allowed'] is True
    assert 'passed' in result['reason'].lower()


def test_can_open_position_daily_limit(risk_manager):
    """Test position validation - daily limit reached"""
    risk_manager.daily_trades = 10
    
    result = risk_manager.can_open_position(
        symbol='XAUUSD',
        order_type='BUY',
        lot_size=0.01
    )
    
    assert result['allowed'] is False
    assert 'daily trade limit' in result['reason'].lower()


def test_can_open_position_max_positions(risk_manager, mock_mt5):
    """Test position validation - max positions reached"""
    # Mock 3 open positions
    mock_mt5.get_open_positions.return_value = [
        {'ticket': 1}, {'ticket': 2}, {'ticket': 3}
    ]
    
    result = risk_manager.can_open_position(
        symbol='XAUUSD',
        order_type='BUY',
        lot_size=0.01
    )
    
    assert result['allowed'] is False
    assert 'max open positions' in result['reason'].lower()


def test_register_trade(risk_manager):
    """Test trade registration"""
    risk_manager.register_trade(profit=100.0)
    
    assert risk_manager.daily_trades == 1
    assert risk_manager.daily_profit == 100.0
    
    risk_manager.register_trade(profit=-50.0)
    
    assert risk_manager.daily_trades == 2
    assert risk_manager.daily_profit == 50.0


def test_get_risk_stats(risk_manager):
    """Test risk statistics"""
    stats = risk_manager.get_risk_stats()
    
    assert 'balance' in stats
    assert 'equity' in stats
    assert 'current_drawdown' in stats
    assert 'daily_trades' in stats
    assert 'can_trade' in stats
    assert stats['can_trade'] is True


def test_trailing_stop_buy(risk_manager):
    """Test trailing stop for BUY position"""
    position = {
        'symbol': 'XAUUSD',
        'type': 'BUY',
        'price_open': 1950.00,
        'sl': 1945.00,
        'tp': 1960.00
    }
    
    # Price moved up, should trail
    new_sl = risk_manager.calculate_trailing_stop(
        position=position,
        current_price=1955.00
    )
    
    assert new_sl is not None
    assert new_sl > position['sl']


def test_trailing_stop_sell(risk_manager):
    """Test trailing stop for SELL position"""
    position = {
        'symbol': 'XAUUSD',
        'type': 'SELL',
        'price_open': 1950.00,
        'sl': 1955.00,
        'tp': 1940.00
    }
    
    # Price moved down, should trail
    new_sl = risk_manager.calculate_trailing_stop(
        position=position,
        current_price=1945.00
    )
    
    assert new_sl is not None
    assert new_sl < position['sl']


def test_should_move_to_breakeven_buy(risk_manager):
    """Test break-even trigger for BUY"""
    position = {
        'symbol': 'XAUUSD',
        'type': 'BUY',
        'price_open': 1950.00,
        'sl': 1945.00,
        'tp': 1960.00
    }
    
    # Price moved enough, should trigger break-even
    should_move = risk_manager.should_move_to_breakeven(
        position=position,
        current_price=1951.50  # 1.5 points profit
    )
    
    assert should_move is True


def test_should_move_to_breakeven_sell(risk_manager):
    """Test break-even trigger for SELL"""
    position = {
        'symbol': 'XAUUSD',
        'type': 'SELL',
        'price_open': 1950.00,
        'sl': 1955.00,
        'tp': 1940.00
    }
    
    # Price moved enough, should trigger break-even
    should_move = risk_manager.should_move_to_breakeven(
        position=position,
        current_price=1948.50  # 1.5 points profit
    )
    
    assert should_move is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
