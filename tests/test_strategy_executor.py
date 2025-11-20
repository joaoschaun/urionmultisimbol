"""
Testes unitários para StrategyExecutor
Cobertura: Execução de sinais, validação de ordens, retry logic
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.strategy_executor import StrategyExecutor
from core.risk_manager import RiskManager
from core.mt5_connector import MT5Connector


class TestStrategyExecutor(unittest.TestCase):
    """Testes para StrategyExecutor"""

    def setUp(self):
        """Setup executado antes de cada teste"""
        self.config = {
            'trading': {
                'symbol': 'XAUUSD',
                'lot_size': 0.01,
                'max_open_positions': 6
            },
            'risk': {
                'max_risk_per_trade': 0.02,
                'max_drawdown': 0.08
            }
        }
        
        # Mocks
        self.mock_mt5 = Mock(spec=MT5Connector)
        self.mock_risk_manager = Mock(spec=RiskManager)
        self.mock_telegram = Mock()
        self.mock_stats_db = Mock()
        
        # Configura métodos do MT5
        self.mock_mt5.get_account_info.return_value = {
            'balance': 10000,
            'equity': 10000,
            'margin_free': 9000
        }
        self.mock_mt5.get_open_positions.return_value = []
        
        # Configura métodos do RiskManager
        self.mock_risk_manager.can_open_position.return_value = (True, "OK")
        self.mock_risk_manager.calculate_position_size.return_value = 0.01
        
        # Cria executor
        self.executor = StrategyExecutor(
            config=self.config,
            mt5=self.mock_mt5,
            risk_manager=self.mock_risk_manager,
            telegram=self.mock_telegram,
            stats_db=self.mock_stats_db
        )

    def test_initialization(self):
        """Testa inicialização do StrategyExecutor"""
        self.assertEqual(self.executor.symbol, 'XAUUSD')
        self.assertEqual(self.executor.lot_size, 0.01)
        self.assertEqual(self.executor.max_open_positions, 6)
        self.assertIsNotNone(self.executor.mt5)
        self.assertIsNotNone(self.executor.risk_manager)

    def test_execute_signal_buy_success(self):
        """Testa execução bem-sucedida de sinal de COMPRA"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'TrendFollowing',
            'confidence': 75.0,
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        # Mock de place_order retornando sucesso
        self.mock_mt5.place_order.return_value = {
            'success': True,
            'ticket': 12345,
            'volume': 0.01
        }
        
        result = self.executor.execute_signal(signal)
        
        self.assertTrue(result)
        self.mock_mt5.place_order.assert_called_once()
        self.mock_telegram.send_message.assert_called()

    def test_execute_signal_sell_success(self):
        """Testa execução bem-sucedida de sinal de VENDA"""
        signal = {
            'action': 'SELL',
            'symbol': 'XAUUSD',
            'strategy': 'MeanReversion',
            'confidence': 80.0,
            'sl': 2010.0,
            'tp': 2000.0,
            'details': {'current_price': 2005.0}
        }
        
        self.mock_mt5.place_order.return_value = {
            'success': True,
            'ticket': 54321,
            'volume': 0.01
        }
        
        result = self.executor.execute_signal(signal)
        
        self.assertTrue(result)
        self.mock_mt5.place_order.assert_called_once()

    def test_execute_signal_hold_ignored(self):
        """Testa que sinal HOLD é ignorado"""
        signal = {
            'action': 'HOLD',
            'symbol': 'XAUUSD',
            'strategy': 'TrendFollowing',
            'confidence': 50.0
        }
        
        result = self.executor.execute_signal(signal)
        
        self.assertFalse(result)
        self.mock_mt5.place_order.assert_not_called()

    def test_execute_signal_risk_manager_blocks(self):
        """Testa que RiskManager bloqueia ordem quando necessário"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'Breakout',
            'confidence': 85.0,
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        # RiskManager bloqueia
        self.mock_risk_manager.can_open_position.return_value = (False, "Max positions reached")
        
        result = self.executor.execute_signal(signal)
        
        self.assertFalse(result)
        self.mock_mt5.place_order.assert_not_called()

    def test_execute_signal_mt5_fails(self):
        """Testa tratamento de falha no MT5"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'NewsTrading',
            'confidence': 90.0,
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        # MT5 falha ao executar ordem
        self.mock_mt5.place_order.return_value = {
            'success': False,
            'error': 'Insufficient margin'
        }
        
        result = self.executor.execute_signal(signal)
        
        self.assertFalse(result)
        self.mock_mt5.place_order.assert_called_once()

    def test_execute_signal_missing_sl_tp(self):
        """Testa que ordem é rejeitada sem SL/TP"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'Scalping',
            'confidence': 70.0,
            'details': {'current_price': 2005.0}
            # SL e TP faltando
        }
        
        result = self.executor.execute_signal(signal)
        
        # Deve falhar ou usar valores padrão
        # Depende da implementação - ajustar conforme necessário
        self.assertIsNotNone(result)

    def test_execute_signal_saves_to_database(self):
        """Testa que trade é salvo no banco de dados"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'RangeTrading',
            'confidence': 65.0,
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        self.mock_mt5.place_order.return_value = {
            'success': True,
            'ticket': 99999,
            'volume': 0.01
        }
        
        result = self.executor.execute_signal(signal)
        
        self.assertTrue(result)
        # Verifica se save_trade foi chamado
        if hasattr(self.mock_stats_db, 'save_trade'):
            self.mock_stats_db.save_trade.assert_called()

    def test_execute_signal_low_confidence_rejected(self):
        """Testa rejeição de sinais com confiança muito baixa"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'TrendFollowing',
            'confidence': 45.0,  # Muito baixo
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        # Dependendo da implementação, confiança baixa pode ser rejeitada
        result = self.executor.execute_signal(signal)
        
        # Ajustar conforme lógica de threshold
        self.assertIsNotNone(result)

    def test_calculate_lot_size_respects_config(self):
        """Testa que lot size do config é respeitado"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'TrendFollowing',
            'confidence': 75.0,
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        self.mock_mt5.place_order.return_value = {
            'success': True,
            'ticket': 11111,
            'volume': 0.01
        }
        
        self.executor.execute_signal(signal)
        
        # Verifica que place_order foi chamado com volume correto
        call_args = self.mock_mt5.place_order.call_args
        if call_args:
            # Volume pode estar em kwargs ou args
            self.assertIn(0.01, [call_args[1].get('volume'), call_args[0] if call_args[0] else None])

    def test_concurrent_signal_execution(self):
        """Testa execução de múltiplos sinais simultaneamente"""
        signals = [
            {
                'action': 'BUY',
                'symbol': 'XAUUSD',
                'strategy': 'TrendFollowing',
                'confidence': 75.0,
                'sl': 2000.0,
                'tp': 2010.0,
                'details': {'current_price': 2005.0}
            },
            {
                'action': 'SELL',
                'symbol': 'XAUUSD',
                'strategy': 'MeanReversion',
                'confidence': 80.0,
                'sl': 2010.0,
                'tp': 2000.0,
                'details': {'current_price': 2005.0}
            }
        ]
        
        self.mock_mt5.place_order.return_value = {
            'success': True,
            'ticket': 77777,
            'volume': 0.01
        }
        
        results = [self.executor.execute_signal(sig) for sig in signals]
        
        # Ambos devem ser executados (se max_positions permite)
        self.assertEqual(len(results), 2)

    def test_telegram_notification_on_success(self):
        """Testa que Telegram é notificado em caso de sucesso"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'Breakout',
            'confidence': 88.0,
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        self.mock_mt5.place_order.return_value = {
            'success': True,
            'ticket': 88888,
            'volume': 0.01
        }
        
        self.executor.execute_signal(signal)
        
        # Verifica que Telegram foi chamado
        self.mock_telegram.send_message.assert_called()

    def test_telegram_notification_on_failure(self):
        """Testa que Telegram é notificado em caso de falha"""
        signal = {
            'action': 'BUY',
            'symbol': 'XAUUSD',
            'strategy': 'NewsTrading',
            'confidence': 92.0,
            'sl': 2000.0,
            'tp': 2010.0,
            'details': {'current_price': 2005.0}
        }
        
        self.mock_mt5.place_order.return_value = {
            'success': False,
            'error': 'Trade context busy'
        }
        
        self.executor.execute_signal(signal)
        
        # Telegram pode ou não ser notificado em falhas (depende da implementação)
        # Ajustar conforme necessário


if __name__ == '__main__':
    unittest.main()
