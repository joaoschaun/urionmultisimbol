"""
Risk Manager - Example Usage
Demonstrates how to use the Risk Manager
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager
from src.risk_manager import RiskManager


def main():
    """Example usage of Risk Manager"""
    
    print("=" * 60)
    print("RISK MANAGER - EXAMPLE USAGE")
    print("=" * 60)
    
    # Initialize configuration
    config = ConfigManager('config/config.yaml')
    
    # Initialize MT5 connection
    mt5 = MT5Connector(config.get_all())
    if not mt5.connect():
        print("❌ Failed to connect to MT5")
        return
    
    print("✅ Connected to MT5")
    
    # Initialize Risk Manager
    risk_manager = RiskManager(config.get_all(), mt5)
    
    print("\n" + "=" * 60)
    print("CURRENT RISK STATISTICS")
    print("=" * 60)
    
    # Get risk statistics
    stats = risk_manager.get_risk_stats()
    
    print(f"Balance: ${stats['balance']:.2f}")
    print(f"Equity: ${stats['equity']:.2f}")
    print(f"Peak Balance: ${stats['peak_balance']:.2f}")
    print(f"Current Drawdown: {stats['current_drawdown_percent']:.2f}%")
    print(f"Max Drawdown: {stats['max_drawdown_percent']:.2f}%")
    print(f"\nOpen Positions: {stats['open_positions']}/{stats['max_open_positions']}")
    print(f"Daily P/L: ${stats['daily_profit']:.2f}")
    print(f"Max Daily Loss: ${stats['max_daily_loss']:.2f}")
    print(f"Daily Loss Remaining: ${stats['daily_loss_remaining']:.2f}")
    print(f"\nRisk per Trade: {stats['risk_per_trade_percent']:.1f}%")
    print(f"Can Trade: {'✅ YES' if stats['can_trade'] else '❌ NO'}")
    
    print("\n" + "=" * 60)
    print("POSITION SIZE CALCULATION")
    print("=" * 60)
    
    # Example: Calculate position size
    symbol = 'XAUUSD'
    entry_price = 1950.00
    
    # Calculate stop loss
    stop_loss = risk_manager.calculate_stop_loss(
        symbol=symbol,
        order_type='BUY',
        entry_price=entry_price
    )
    
    print(f"\nEntry Price: ${entry_price:.2f}")
    print(f"Stop Loss: ${stop_loss:.2f}")
    print(f"SL Distance: ${entry_price - stop_loss:.2f}")
    
    # Calculate position size
    lot_size = risk_manager.calculate_position_size(
        symbol=symbol,
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_percent=0.02  # 2% risk
    )
    
    print(f"\nPosition Size: {lot_size} lots")
    print(f"Risk Amount: ${stats['balance'] * 0.02:.2f}")
    
    # Calculate take profit
    take_profit = risk_manager.calculate_take_profit(
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_reward_ratio=2.0
    )
    
    print(f"\nTake Profit: ${take_profit:.2f}")
    print(f"TP Distance: ${take_profit - entry_price:.2f}")
    print(f"Risk/Reward: 1:2.0")
    
    # Calculate potential profit/loss
    risk_amount = stats['balance'] * 0.02
    reward_amount = risk_amount * 2.0
    
    print(f"\nPotential Loss: -${risk_amount:.2f}")
    print(f"Potential Profit: +${reward_amount:.2f}")
    
    print("\n" + "=" * 60)
    print("POSITION VALIDATION")
    print("=" * 60)
    
    # Validate if can open position
    validation = risk_manager.can_open_position(
        symbol=symbol,
        order_type='BUY',
        lot_size=lot_size
    )
    
    if validation['allowed']:
        print(f"✅ ALLOWED: {validation['reason']}")
    else:
        print(f"❌ DENIED: {validation['reason']}")
    
    print("\n" + "=" * 60)
    print("RISK MANAGEMENT SUMMARY")
    print("=" * 60)
    
    print(f"""
📊 TRADE SETUP:
   Symbol: {symbol}
   Type: BUY
   Entry: ${entry_price:.2f}
   Stop Loss: ${stop_loss:.2f} ({entry_price - stop_loss:.2f} points)
   Take Profit: ${take_profit:.2f} ({take_profit - entry_price:.2f} points)
   Lot Size: {lot_size} lots
   
💰 RISK/REWARD:
   Risk Amount: ${risk_amount:.2f} ({2.0}%)
   Reward Amount: ${reward_amount:.2f} ({4.0}%)
   Risk/Reward Ratio: 1:2.0
   
🛡️ ACCOUNT PROTECTION:
   Max Risk per Trade: {stats['risk_per_trade_percent']:.1f}%
   Max Daily Loss: {stats['max_daily_loss'] / stats['balance'] * 100:.1f}%
   Max Drawdown: {stats['max_drawdown_percent']:.1f}%
   Max Simultaneous Positions: {stats['max_open_positions']}
   Current Open Positions: {stats['open_positions']}
   
✅ VALIDATION: {'APPROVED' if validation['allowed'] else 'REJECTED'}
   Reason: {validation['reason']}
    """)
    
    # Disconnect
    mt5.disconnect()
    print("\n✅ Disconnected from MT5")


if __name__ == "__main__":
    main()
