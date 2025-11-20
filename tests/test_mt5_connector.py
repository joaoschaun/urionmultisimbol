"""
Testes unitários para MT5Connector
Cobertura: Conexão, ordens, posições, retry logic
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.mt5_connector import MT5Connector


class TestMT5Connector(unittest.TestCase):
    """Testes para MT5Connector"""

    def setUp(self):
        """Setup executado antes de cada teste"""
        self.config = {
            'mt5': {
                'login': 12345,
                'password': 'test_password',
                'server': 'TestServer-Demo',
                'path': 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'
            },
            'trading': {
                'symbol': 'XAUUSD',
                'magic_number': 123456
            }
        }

    @patch('core.mt5_connector.mt5')
    def test_initialization(self, mock_mt5):
        """Testa inicialização do MT5Connector"""
        connector = MT5Connector(self.config)
        
        self.assertEqual(connector.login, 12345)
        self.assertEqual(connector.server, 'TestServer-Demo')
        self.assertFalse(connector.connected)

    @patch('core.mt5_connector.mt5')
    def test_connect_success(self, mock_mt5):
        """Testa conexão bem-sucedida"""
        mock_mt5.initialize.return_value = True
        mock_mt5.login.return_value = True
        mock_mt5.last_error.return_value = (0, 'Success')
        
        connector = MT5Connector(self.config)
        result = connector.connect()
        
        self.assertTrue(result)
        self.assertTrue(connector.connected)
        mock_mt5.initialize.assert_called_once()
        mock_mt5.login.assert_called_once()

    @patch('core.mt5_connector.mt5')
    def test_connect_initialize_fails(self, mock_mt5):
        """Testa falha na inicialização"""
        mock_mt5.initialize.return_value = False
        mock_mt5.last_error.return_value = (1, 'Initialize failed')
        
        connector = MT5Connector(self.config)
        
        # Deve lançar exceção devido ao retry handler
        with self.assertRaises(Exception):
            connector.connect()

    @patch('core.mt5_connector.mt5')
    def test_connect_login_fails(self, mock_mt5):
        """Testa falha no login"""
        mock_mt5.initialize.return_value = True
        mock_mt5.login.return_value = False
        mock_mt5.last_error.return_value = (2, 'Invalid credentials')
        
        connector = MT5Connector(self.config)
        
        with self.assertRaises(Exception):
            connector.connect()

    @patch('core.mt5_connector.mt5')
    def test_disconnect(self, mock_mt5):
        """Testa desconexão"""
        mock_mt5.initialize.return_value = True
        mock_mt5.login.return_value = True
        mock_mt5.shutdown.return_value = None
        
        connector = MT5Connector(self.config)
        connector.connect()
        connector.disconnect()
        
        self.assertFalse(connector.connected)
        mock_mt5.shutdown.assert_called_once()

    @patch('core.mt5_connector.mt5')
    def test_get_account_info(self, mock_mt5):
        """Testa obtenção de informações da conta"""
        mock_account = Mock()
        mock_account.balance = 10000.0
        mock_account.equity = 10500.0
        mock_account.margin = 500.0
        mock_account.margin_free = 9500.0
        mock_account.profit = 500.0
        
        mock_mt5.account_info.return_value = mock_account
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        info = connector.get_account_info()
        
        self.assertEqual(info['balance'], 10000.0)
        self.assertEqual(info['equity'], 10500.0)
        self.assertEqual(info['profit'], 500.0)

    @patch('core.mt5_connector.mt5')
    def test_get_account_info_not_connected(self, mock_mt5):
        """Testa get_account_info quando não conectado"""
        connector = MT5Connector(self.config)
        connector.connected = False
        
        info = connector.get_account_info()
        
        self.assertIsNone(info)

    @patch('core.mt5_connector.mt5')
    def test_place_order_buy(self, mock_mt5):
        """Testa colocação de ordem de COMPRA"""
        mock_mt5.symbol_info_tick.return_value = Mock(ask=2005.0, bid=2004.9)
        mock_mt5.order_send.return_value = Mock(
            retcode=10009,  # TRADE_RETCODE_DONE
            order=12345,
            volume=0.01
        )
        mock_mt5.ORDER_TYPE_BUY = 0
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        result = connector.place_order(
            symbol='XAUUSD',
            order_type='BUY',
            volume=0.01,
            sl=2000.0,
            tp=2010.0
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['ticket'], 12345)

    @patch('core.mt5_connector.mt5')
    def test_place_order_sell(self, mock_mt5):
        """Testa colocação de ordem de VENDA"""
        mock_mt5.symbol_info_tick.return_value = Mock(ask=2005.0, bid=2004.9)
        mock_mt5.order_send.return_value = Mock(
            retcode=10009,
            order=54321,
            volume=0.01
        )
        mock_mt5.ORDER_TYPE_SELL = 1
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        result = connector.place_order(
            symbol='XAUUSD',
            order_type='SELL',
            volume=0.01,
            sl=2010.0,
            tp=2000.0
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['ticket'], 54321)

    @patch('core.mt5_connector.mt5')
    def test_place_order_fails(self, mock_mt5):
        """Testa falha ao colocar ordem"""
        mock_mt5.symbol_info_tick.return_value = Mock(ask=2005.0, bid=2004.9)
        mock_mt5.order_send.return_value = Mock(
            retcode=10013,  # TRADE_RETCODE_ERROR
            comment='Invalid volume'
        )
        mock_mt5.ORDER_TYPE_BUY = 0
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        result = connector.place_order(
            symbol='XAUUSD',
            order_type='BUY',
            volume=0.01,
            sl=2000.0,
            tp=2010.0
        )
        
        self.assertFalse(result['success'])

    @patch('core.mt5_connector.mt5')
    def test_get_open_positions(self, mock_mt5):
        """Testa obtenção de posições abertas"""
        mock_position1 = Mock()
        mock_position1.ticket = 12345
        mock_position1.symbol = 'XAUUSD'
        mock_position1.type = 0  # BUY
        mock_position1.volume = 0.01
        mock_position1.price_open = 2005.0
        mock_position1.sl = 2000.0
        mock_position1.tp = 2010.0
        mock_position1.profit = 50.0
        
        mock_mt5.positions_get.return_value = [mock_position1]
        mock_mt5.ORDER_TYPE_BUY = 0
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        positions = connector.get_open_positions()
        
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]['ticket'], 12345)
        self.assertEqual(positions[0]['symbol'], 'XAUUSD')

    @patch('core.mt5_connector.mt5')
    def test_close_position(self, mock_mt5):
        """Testa fechamento de posição"""
        mock_mt5.symbol_info_tick.return_value = Mock(ask=2010.0, bid=2009.9)
        mock_mt5.order_send.return_value = Mock(retcode=10009)
        mock_mt5.POSITION_TYPE_BUY = 0
        mock_mt5.ORDER_TYPE_SELL = 1
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        result = connector.close_position(
            ticket=12345,
            symbol='XAUUSD',
            volume=0.01,
            position_type='BUY'
        )
        
        self.assertTrue(result)

    @patch('core.mt5_connector.mt5')
    def test_modify_position(self, mock_mt5):
        """Testa modificação de SL/TP"""
        mock_mt5.order_send.return_value = Mock(retcode=10009)
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        result = connector.modify_position(
            ticket=12345,
            symbol='XAUUSD',
            sl=2001.0,
            tp=2012.0
        )
        
        self.assertTrue(result)

    @patch('core.mt5_connector.mt5')
    def test_get_symbol_info(self, mock_mt5):
        """Testa obtenção de informações do símbolo"""
        mock_symbol = Mock()
        mock_symbol.point = 0.01
        mock_symbol.digits = 2
        mock_symbol.trade_contract_size = 100
        
        mock_mt5.symbol_info.return_value = mock_symbol
        
        connector = MT5Connector(self.config)
        connector.connected = True
        
        info = connector.get_symbol_info('XAUUSD')
        
        self.assertEqual(info['point'], 0.01)
        self.assertEqual(info['digits'], 2)


if __name__ == '__main__':
    unittest.main()
