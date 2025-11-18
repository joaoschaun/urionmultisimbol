"""
MetaTrader 5 Connector
Handles connection, authentication and communication with MT5 terminal
"""
import MetaTrader5 as mt5
import time
from datetime import datetime
from typing import Optional, Dict, List, Any
import pandas as pd
from loguru import logger


class MT5Connector:
    """MetaTrader 5 Connection Manager"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize MT5 Connector
        
        Args:
            config: Configuration dictionary with MT5 credentials
        """
        self.config = config
        self.mt5_config = config.get('mt5', {})
        self.login = int(self.mt5_config.get('login'))
        self.password = self.mt5_config.get('password')
        self.server = self.mt5_config.get('server')
        self.path = self.mt5_config.get('path', '')
        self.timeout = self.mt5_config.get('timeout', 60000)
        self.max_reconnect_attempts = self.mt5_config.get('max_reconnect_attempts', 5)
        self.connected = False
        self.reconnect_attempts = 0
        
    def connect(self) -> bool:
        """
        Connect to MetaTrader 5 terminal
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("Connecting to MetaTrader 5...")
            
            # Initialize MT5
            if self.path:
                if not mt5.initialize(path=self.path, timeout=self.timeout):
                    logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
                    return False
            else:
                if not mt5.initialize(timeout=self.timeout):
                    logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
                    return False
            
            logger.info("MT5 initialized successfully")
            
            # Login to account
            if not mt5.login(self.login, password=self.password, server=self.server):
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            logger.info(f"Logged in to account {self.login} on server {self.server}")
            
            # Verify connection
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("Failed to get account info")
                return False
            
            self.connected = True
            self.reconnect_attempts = 0
            
            logger.info(f"Account Balance: {account_info.balance} {account_info.currency}")
            logger.info(f"Account Leverage: 1:{account_info.leverage}")
            logger.info(f"Account Company: {account_info.company}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error connecting to MT5: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MetaTrader 5"""
        try:
            if self.connected:
                mt5.shutdown()
                self.connected = False
                logger.info("Disconnected from MetaTrader 5")
        except Exception as e:
            logger.exception(f"Error disconnecting from MT5: {e}")
    
    def is_connected(self) -> bool:
        """
        Check if connected to MT5
        
        Returns:
            bool: True if connected
        """
        return self.connected and mt5.terminal_info() is not None
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect to MetaTrader 5
        
        Returns:
            bool: True if reconnection successful
        """
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return False
        
        self.reconnect_attempts += 1
        logger.warning(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        
        self.disconnect()
        time.sleep(5)  # Wait before reconnecting
        
        return self.connect()
    
    def ensure_connection(self) -> bool:
        """
        Ensure connection to MT5 is active
        
        Returns:
            bool: True if connected
        """
        if not self.connected:
            return self.reconnect()
        
        # Verify connection is still active
        try:
            account_info = mt5.account_info()
            if account_info is None:
                logger.warning("Connection lost, attempting reconnection...")
                return self.reconnect()
            return True
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            return self.reconnect()
    
    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information
        
        Returns:
            Dictionary with account info or None
        """
        if not self.ensure_connection():
            return None
        
        try:
            account_info = mt5.account_info()
            if account_info is None:
                logger.error(f"Failed to get account info: {mt5.last_error()}")
                return None
            
            return {
                'login': account_info.login,
                'balance': account_info.balance,
                'equity': account_info.equity,
                'margin': account_info.margin,
                'free_margin': account_info.margin_free,
                'margin_level': account_info.margin_level,
                'profit': account_info.profit,
                'currency': account_info.currency,
                'leverage': account_info.leverage,
                'server': account_info.server,
                'company': account_info.company
            }
        except Exception as e:
            logger.exception(f"Error getting account info: {e}")
            return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get symbol information
        
        Args:
            symbol: Symbol name (e.g., 'XAUUSD')
            
        Returns:
            Dictionary with symbol info or None
        """
        if not self.ensure_connection():
            return None
        
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Failed to get symbol info for {symbol}: {mt5.last_error()}")
                return None
            
            return {
                'name': symbol_info.name,
                'bid': symbol_info.bid,
                'ask': symbol_info.ask,
                'spread': symbol_info.spread,
                'digits': symbol_info.digits,
                'point': symbol_info.point,
                'trade_contract_size': symbol_info.trade_contract_size,
                'volume_min': symbol_info.volume_min,
                'volume_max': symbol_info.volume_max,
                'volume_step': symbol_info.volume_step,
                'trade_mode': symbol_info.trade_mode,
                'description': symbol_info.description
            }
        except Exception as e:
            logger.exception(f"Error getting symbol info: {e}")
            return None
    
    def get_rates(self, symbol: str, timeframe: int, count: int = 1000) -> Optional[pd.DataFrame]:
        """
        Get historical price data
        
        Args:
            symbol: Symbol name
            timeframe: MT5 timeframe constant
            count: Number of bars to retrieve
            
        Returns:
            DataFrame with OHLCV data or None
        """
        if not self.ensure_connection():
            return None
        
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is None or len(rates) == 0:
                logger.error(f"Failed to get rates for {symbol}: {mt5.last_error()}")
                return None
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            return df
            
        except Exception as e:
            logger.exception(f"Error getting rates: {e}")
            return None
    
    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open positions
        
        Args:
            symbol: Filter by symbol (optional)
            
        Returns:
            List of position dictionaries
        """
        if not self.ensure_connection():
            return []
        
        try:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()
            
            if positions is None:
                return []
            
            return [
                {
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'price_open': pos.price_open,
                    'price_current': pos.price_current,
                    'sl': pos.sl,
                    'tp': pos.tp,
                    'profit': pos.profit,
                    'time': datetime.fromtimestamp(pos.time),
                    'comment': pos.comment
                }
                for pos in positions
            ]
            
        except Exception as e:
            logger.exception(f"Error getting positions: {e}")
            return []
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Alias for get_open_positions()
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of position dictionaries
        """
        return self.get_open_positions(symbol)
    
    def place_order(self, symbol: str, order_type: str, volume: float, 
                   sl: float = 0, tp: float = 0, comment: str = "", 
                   magic: int = 123456) -> Optional[Dict]:
        """
        Place a market order
        
        Args:
            symbol: Symbol name
            order_type: 'BUY' or 'SELL'
            volume: Lot size
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment
            magic: Magic number for identifying orders
            
        Returns:
            Dictionary with order result or None
        """
        if not self.ensure_connection():
            return None
        
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Symbol {symbol} not found")
                return None
            
            if not symbol_info.visible:
                if not mt5.symbol_select(symbol, True):
                    logger.error(f"Failed to select symbol {symbol}")
                    return None
            
            # Prepare request
            order_type_mt5 = mt5.ORDER_TYPE_BUY if order_type == 'BUY' else mt5.ORDER_TYPE_SELL
            price = symbol_info.ask if order_type == 'BUY' else symbol_info.bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type_mt5,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": self.config.get('trading', {}).get('slippage', 10),
                "magic": magic,  # Magic number from parameter
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result is None:
                logger.error(f"Order send failed: {mt5.last_error()}")
                return None
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result.retcode}, {result.comment}")
                return None
            
            logger.info(f"Order placed successfully: {order_type} {volume} {symbol} at {price}")
            
            return {
                'ticket': result.order,
                'symbol': symbol,
                'type': order_type,
                'volume': volume,
                'price': result.price,
                'sl': sl,
                'tp': tp,
                'comment': comment,
                'retcode': result.retcode
            }
            
        except Exception as e:
            logger.exception(f"Error placing order: {e}")
            return None
    
    def close_position(self, ticket: int) -> bool:
        """
        Close an open position
        
        Args:
            ticket: Position ticket number
            
        Returns:
            bool: True if position closed successfully
        """
        if not self.ensure_connection():
            return False
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            # Opposite order type
            order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(position.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": self.config.get('trading', {}).get('slippage', 10),
                "magic": 123456,
                "comment": "Close by bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to close position {ticket}: {result.comment if result else mt5.last_error()}")
                return False
            
            logger.info(f"Position {ticket} closed successfully")
            return True
            
        except Exception as e:
            logger.exception(f"Error closing position: {e}")
            return False
    
    def modify_position(self, ticket: int, sl: float = None, tp: float = None) -> bool:
        """
        Modify position's stop loss and/or take profit
        
        Args:
            ticket: Position ticket number
            sl: New stop loss (optional)
            tp: New take profit (optional)
            
        Returns:
            bool: True if modification successful
        """
        if not self.ensure_connection():
            return False
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": position.symbol,
                "position": ticket,
                "sl": sl if sl is not None else position.sl,
                "tp": tp if tp is not None else position.tp,
            }
            
            result = mt5.order_send(request)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to modify position {ticket}: {result.comment if result else mt5.last_error()}")
                return False
            
            logger.info(f"Position {ticket} modified successfully")
            return True
            
        except Exception as e:
            logger.exception(f"Error modifying position: {e}")
            return False
