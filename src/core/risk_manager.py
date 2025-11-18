"""
Risk Manager
Manages all risk-related calculations and validations
"""
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from loguru import logger
import MetaTrader5 as mt5


class RiskManager:
    """
    Risk Management System
    
    Handles:
    - Position sizing
    - Stop loss / Take profit calculation
    - Drawdown monitoring
    - Daily loss limits
    - Trade limits
    - Exposure validation
    """
    
    def __init__(self, config: Dict[str, Any], mt5_connector):
        """
        Initialize Risk Manager
        
        Args:
            config: Configuration dictionary
            mt5_connector: MT5Connector instance
        """
        self.config = config
        self.mt5 = mt5_connector
        
        # Risk configuration
        self.risk_config = config.get('risk', {})
        self.max_risk_per_trade = self.risk_config.get('max_risk_per_trade', 0.02)
        self.max_drawdown = self.risk_config.get('max_drawdown', 0.15)
        self.max_daily_loss = self.risk_config.get('max_daily_loss', 0.05)
        
        # Trading configuration
        self.trading_config = config.get('trading', {})
        self.max_open_positions = self.trading_config.get('max_open_positions', 3)
        self.symbol = self.trading_config.get('symbol', 'XAUUSD')
        
        # Tracking
        self.daily_profit = 0.0
        self.last_reset_date = datetime.now().date()
        self.peak_balance = 0.0
        
        logger.info("Risk Manager initialized")
        logger.info(f"Max risk per trade: {self.max_risk_per_trade * 100}%")
        logger.info(f"Max drawdown: {self.max_drawdown * 100}%")
        logger.info(f"Max daily loss: {self.max_daily_loss * 100}%")
        logger.info(f"Max simultaneous positions: {self.max_open_positions}")
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            logger.info("Resetting daily statistics")
            self.daily_profit = 0.0
            self.last_reset_date = today
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        risk_percent: Optional[float] = None
    ) -> float:
        """
        Calculate position size based on risk percentage
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_percent: Risk percentage (uses default if None)
            
        Returns:
            Position size in lots
        """
        try:
            # Get account info
            account_info = self.mt5.get_account_info()
            if not account_info:
                logger.error("Failed to get account info for position sizing")
                return 0.0
            
            balance = account_info['balance']
            
            # Use provided risk or default
            risk = risk_percent if risk_percent is not None else self.max_risk_per_trade
            
            # Calculate risk amount in currency
            risk_amount = balance * risk
            
            # Get symbol info
            symbol_info = self.mt5.get_symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Failed to get symbol info for {symbol}")
                return 0.0
            
            contract_size = symbol_info['trade_contract_size']
            point = symbol_info['point']
            
            # Calculate pip value
            sl_distance = abs(entry_price - stop_loss)
            sl_distance_points = sl_distance / point
            
            # Calculate lot size
            tick_value = contract_size * point
            lot_size = risk_amount / (sl_distance_points * tick_value)
            
            # Round to valid lot size
            volume_step = symbol_info['volume_step']
            lot_size = round(lot_size / volume_step) * volume_step
            
            # Enforce min/max limits
            lot_size = max(symbol_info['volume_min'], lot_size)
            lot_size = min(symbol_info['volume_max'], lot_size)
            
            # Use default lot size from config if available
            default_lot = self.trading_config.get('default_lot_size', 0.01)
            if lot_size < default_lot:
                lot_size = default_lot
            
            # Additional safety limit from config
            max_lot = self.trading_config.get('max_lot_size', 1.0)
            lot_size = min(lot_size, max_lot)
            
            logger.info(
                f"Position size calculated: {lot_size} lots "
                f"(Risk: ${risk_amount:.2f}, SL distance: {sl_distance:.5f})"
            )
            
            return lot_size
            
        except Exception as e:
            logger.exception(f"Error calculating position size: {e}")
            return 0.0
    
    def calculate_stop_loss(
        self,
        symbol: str,
        order_type: str,
        entry_price: float,
        atr_value: Optional[float] = None,
        atr_multiplier: Optional[float] = None
    ) -> float:
        """
        Calculate stop loss price
        
        Args:
            symbol: Trading symbol
            order_type: 'BUY' or 'SELL'
            entry_price: Entry price
            atr_value: ATR value (if available)
            atr_multiplier: ATR multiplier
            
        Returns:
            Stop loss price
        """
        try:
            symbol_info = self.mt5.get_symbol_info(symbol)
            if not symbol_info:
                return 0.0
            
            point = symbol_info['point']
            
            # Get stop loss distance from config or ATR
            if atr_value and atr_multiplier:
                sl_distance = atr_value * atr_multiplier
                logger.debug(f"Using ATR-based SL: {sl_distance:.5f}")
            else:
                # Use fixed pips from config
                sl_pips = self.risk_config.get('stop_loss_pips', 20)
                sl_distance = sl_pips * point * 10  # Convert pips to price
                logger.debug(f"Using fixed SL: {sl_pips} pips")
            
            # Calculate stop loss
            if order_type == 'BUY':
                stop_loss = entry_price - sl_distance
            else:  # SELL
                stop_loss = entry_price + sl_distance
            
            # Round to valid price
            digits = symbol_info['digits']
            stop_loss = round(stop_loss, digits)
            
            logger.info(
                f"Stop loss calculated: {stop_loss:.5f} "
                f"(Distance: {sl_distance:.5f})"
            )
            
            return stop_loss
            
        except Exception as e:
            logger.exception(f"Error calculating stop loss: {e}")
            return 0.0
    
    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        risk_reward_ratio: Optional[float] = None
    ) -> float:
        """
        Calculate take profit price based on risk/reward ratio
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_reward_ratio: Risk/reward ratio (uses default if None)
            
        Returns:
            Take profit price
        """
        try:
            # Use provided ratio or default
            rr_ratio = risk_reward_ratio if risk_reward_ratio is not None else \
                self.risk_config.get('take_profit_multiplier', 2.0)
            
            # Calculate distance
            sl_distance = abs(entry_price - stop_loss)
            tp_distance = sl_distance * rr_ratio
            
            # Determine direction
            if entry_price > stop_loss:  # BUY
                take_profit = entry_price + tp_distance
            else:  # SELL
                take_profit = entry_price - tp_distance
            
            logger.info(
                f"Take profit calculated: {take_profit:.5f} "
                f"(R:R = 1:{rr_ratio})"
            )
            
            return take_profit
            
        except Exception as e:
            logger.exception(f"Error calculating take profit: {e}")
            return 0.0
    
    def can_open_position(
        self,
        symbol: str,
        order_type: str,
        lot_size: float
    ) -> Dict[str, Any]:
        """
        Validate if a new position can be opened
        
        Args:
            symbol: Trading symbol
            order_type: 'BUY' or 'SELL'
            lot_size: Proposed lot size
            
        Returns:
            Dictionary with 'allowed' (bool) and 'reason' (str)
        """
        self.reset_daily_stats()
        
        # Check max open positions (CRITICAL - Always enforced)
        open_positions = self.mt5.get_open_positions(symbol)
        if len(open_positions) >= self.max_open_positions:
            return {
                'allowed': False,
                'reason': f'Max open positions reached ({self.max_open_positions})'
            }
        
        # Check daily loss limit
        account_info = self.mt5.get_account_info()
        if not account_info:
            return {
                'allowed': False,
                'reason': 'Failed to get account info'
            }
        
        balance = account_info['balance']
        daily_loss_limit = balance * self.max_daily_loss
        
        if self.daily_profit < -daily_loss_limit:
            return {
                'allowed': False,
                'reason': f'Daily loss limit reached (${abs(self.daily_profit):.2f})'
            }
        
        # Check drawdown
        if self.peak_balance == 0:
            self.peak_balance = balance
        else:
            self.peak_balance = max(self.peak_balance, balance)
        
        current_drawdown = (self.peak_balance - balance) / self.peak_balance
        
        if current_drawdown > self.max_drawdown:
            return {
                'allowed': False,
                'reason': f'Max drawdown exceeded ({current_drawdown * 100:.1f}%)'
            }
        
        # Check margin
        equity = account_info['equity']
        margin = account_info['margin']
        free_margin = account_info['free_margin']
        
        # Estimate required margin for new position
        symbol_info = self.mt5.get_symbol_info(symbol)
        if not symbol_info:
            return {
                'allowed': False,
                'reason': 'Failed to get symbol info'
            }
        
        # Simple margin estimation (actual calculation is more complex)
        leverage = account_info['leverage']
        contract_size = symbol_info['trade_contract_size']
        current_price = symbol_info['ask'] if order_type == 'BUY' else symbol_info['bid']
        
        estimated_margin = (lot_size * contract_size * current_price) / leverage
        
        if estimated_margin > free_margin * 0.8:  # Use only 80% of free margin
            return {
                'allowed': False,
                'reason': f'Insufficient margin (Need: ${estimated_margin:.2f}, Available: ${free_margin:.2f})'
            }
        
        # Check symbol-specific limits
        spread = symbol_info['spread']
        spread_threshold = self.trading_config.get('spread_threshold', 30)
        
        if spread > spread_threshold:
            return {
                'allowed': False,
                'reason': f'Spread too high ({spread} > {spread_threshold})'
            }
        
        # All checks passed
        logger.info("Position validation passed - Can open trade")
        return {
            'allowed': True,
            'reason': 'All risk checks passed'
        }
    
    def register_trade(self, profit: float):
        """
        Register a completed trade
        
        Args:
            profit: Trade profit/loss
        """
        self.reset_daily_stats()
        self.daily_profit += profit
        
        logger.info(
            f"Trade registered: Profit=${profit:.2f}, "
            f"Daily P/L=${self.daily_profit:.2f}"
        )
    
    def get_risk_stats(self) -> Dict[str, Any]:
        """
        Get current risk statistics
        
        Returns:
            Dictionary with risk statistics
        """
        self.reset_daily_stats()
        
        account_info = self.mt5.get_account_info()
        if not account_info:
            return {}
        
        balance = account_info['balance']
        equity = account_info['equity']
        
        if self.peak_balance == 0:
            self.peak_balance = balance
        
        current_drawdown = (self.peak_balance - balance) / self.peak_balance
        
        return {
            'balance': balance,
            'equity': equity,
            'peak_balance': self.peak_balance,
            'current_drawdown': current_drawdown,
            'current_drawdown_percent': current_drawdown * 100,
            'max_drawdown_percent': self.max_drawdown * 100,
            'daily_profit': self.daily_profit,
            'max_daily_loss': balance * self.max_daily_loss,
            'daily_loss_remaining': (balance * self.max_daily_loss) + self.daily_profit,
            'risk_per_trade_percent': self.max_risk_per_trade * 100,
            'open_positions': len(self.mt5.get_open_positions(self.symbol)),
            'max_open_positions': self.max_open_positions,
            'can_trade': (
                self.daily_profit > -(balance * self.max_daily_loss) and
                current_drawdown < self.max_drawdown and
                len(self.mt5.get_open_positions(self.symbol)) < self.max_open_positions
            )
        }
    
    def calculate_trailing_stop(
        self,
        position: Dict,
        current_price: float,
        trailing_distance: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate trailing stop loss
        
        Args:
            position: Position dictionary
            current_price: Current market price
            trailing_distance: Trailing distance (uses config if None)
            
        Returns:
            New stop loss price or None if no update needed
        """
        try:
            symbol_info = self.mt5.get_symbol_info(position['symbol'])
            if not symbol_info:
                return None
            
            point = symbol_info['point']
            
            # Get trailing distance
            if trailing_distance is None:
                trailing_pips = self.risk_config.get('trailing_stop_distance', 15)
                trailing_distance = trailing_pips * point * 10
            
            current_sl = position['sl']
            position_type = position['type']
            
            if position_type == 'BUY':
                # For BUY, trail stop up
                new_sl = current_price - trailing_distance
                if new_sl > current_sl:
                    logger.info(
                        f"Trailing stop updated for BUY: {current_sl:.5f} -> {new_sl:.5f}"
                    )
                    return new_sl
            else:  # SELL
                # For SELL, trail stop down
                new_sl = current_price + trailing_distance
                if new_sl < current_sl or current_sl == 0:
                    logger.info(
                        f"Trailing stop updated for SELL: {current_sl:.5f} -> {new_sl:.5f}"
                    )
                    return new_sl
            
            return None
            
        except Exception as e:
            logger.exception(f"Error calculating trailing stop: {e}")
            return None
    
    def should_move_to_breakeven(
        self,
        position: Dict,
        current_price: float
    ) -> bool:
        """
        Check if position should be moved to break-even
        
        Args:
            position: Position dictionary
            current_price: Current market price
            
        Returns:
            True if should move to break-even
        """
        try:
            if not self.risk_config.get('break_even_enabled', True):
                return False
            
            symbol_info = self.mt5.get_symbol_info(position['symbol'])
            if not symbol_info:
                return False
            
            point = symbol_info['point']
            
            entry_price = position['price_open']
            current_sl = position['sl']
            position_type = position['type']
            
            # Get break-even trigger distance
            be_trigger_pips = self.risk_config.get('break_even_trigger', 15)
            be_trigger_distance = be_trigger_pips * point * 10
            
            if position_type == 'BUY':
                profit_distance = current_price - entry_price
                # Move to break-even if in profit and SL is still below entry
                if profit_distance >= be_trigger_distance and current_sl < entry_price:
                    logger.info(
                        f"Break-even triggered for BUY (Profit: {profit_distance:.5f})"
                    )
                    return True
            else:  # SELL
                profit_distance = entry_price - current_price
                # Move to break-even if in profit and SL is still above entry
                if profit_distance >= be_trigger_distance and \
                   (current_sl > entry_price or current_sl == 0):
                    logger.info(
                        f"Break-even triggered for SELL (Profit: {profit_distance:.5f})"
                    )
                    return True
            
            return False
            
        except Exception as e:
            logger.exception(f"Error checking break-even: {e}")
            return False
