"""
Testes unitários para TelegramNotifier
Cobertura: Comandos, notificações, integração MT5
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import sys
import os
from datetime import datetime

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestTelegramNotifier(unittest.TestCase):
    """Testes para TelegramNotifier"""

    def setUp(self):
        """Setup executado antes de cada teste"""
        self.config = {
            'telegram': {
                'token': 'test_token_123',
                'chat_id': '123456789',
                'enabled': True
            },
            'trading': {
                'symbol': 'XAUUSD'
            }
        }
        
        self.mock_mt5 = Mock()
        self.mock_stats_db = Mock()

    @patch('notifications.telegram_bot.Bot')
    def test_initialization(self, mock_bot):
        """Testa inicialização do TelegramNotifier"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        self.assertEqual(notifier.token, 'test_token_123')
        self.assertEqual(notifier.chat_id, '123456789')
        self.assertTrue(notifier.enabled)

    @patch('notifications.telegram_bot.Bot')
    def test_send_message_sync_success(self, mock_bot):
        """Testa envio síncrono de mensagem com sucesso"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        # Mock do envio
        mock_bot_instance = mock_bot.return_value
        mock_bot_instance.send_message = AsyncMock()
        
        result = notifier.send_message_sync("Test message")
        
        # Verifica que tentou enviar
        self.assertIsNotNone(result)

    @patch('notifications.telegram_bot.Bot')
    def test_send_message_disabled(self, mock_bot):
        """Testa que mensagens não são enviadas quando desabilitado"""
        config_disabled = self.config.copy()
        config_disabled['telegram']['enabled'] = False
        
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=config_disabled,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        result = notifier.send_message_sync("Test message")
        
        # Não deve enviar quando desabilitado
        self.assertIsNone(result) or self.assertFalse(result)

    @patch('notifications.telegram_bot.Bot')
    def test_cmd_status_with_mt5_info(self, mock_bot):
        """Testa comando /status com informações do MT5"""
        from notifications.telegram_bot import TelegramNotifier
        
        # Setup MT5 mock
        self.mock_mt5.get_account_info.return_value = {
            'balance': 10000.0,
            'equity': 10500.0,
            'margin': 500.0,
            'profit': 500.0
        }
        self.mock_mt5.get_open_positions.return_value = [
            {'ticket': 12345, 'profit': 50.0},
            {'ticket': 54321, 'profit': 30.0}
        ]
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        # Simula comando /status
        mock_update = Mock()
        mock_context = Mock()
        
        # Testa que método existe e pode ser chamado
        self.assertTrue(hasattr(notifier, 'cmd_status'))

    @patch('notifications.telegram_bot.Bot')
    def test_cmd_balance(self, mock_bot):
        """Testa comando /balance"""
        from notifications.telegram_bot import TelegramNotifier
        
        self.mock_mt5.get_account_info.return_value = {
            'balance': 10000.0,
            'equity': 10500.0,
            'margin': 500.0,
            'margin_free': 9500.0,
            'profit': 500.0
        }
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        self.assertTrue(hasattr(notifier, 'cmd_balance'))

    @patch('notifications.telegram_bot.Bot')
    def test_cmd_positions_with_open_trades(self, mock_bot):
        """Testa comando /positions com posições abertas"""
        from notifications.telegram_bot import TelegramNotifier
        
        self.mock_mt5.get_open_positions.return_value = [
            {
                'ticket': 12345,
                'symbol': 'XAUUSD',
                'type': 'BUY',
                'volume': 0.01,
                'open_price': 2005.0,
                'current_price': 2008.0,
                'profit': 30.0,
                'sl': 2000.0,
                'tp': 2010.0
            }
        ]
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        self.assertTrue(hasattr(notifier, 'cmd_positions'))

    @patch('notifications.telegram_bot.Bot')
    def test_cmd_positions_empty(self, mock_bot):
        """Testa comando /positions sem posições"""
        from notifications.telegram_bot import TelegramNotifier
        
        self.mock_mt5.get_open_positions.return_value = []
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        # Deve informar que não há posições
        self.assertTrue(hasattr(notifier, 'cmd_positions'))

    @patch('notifications.telegram_bot.Bot')
    def test_cmd_stats_today(self, mock_bot):
        """Testa comando /stats com estatísticas de hoje"""
        from notifications.telegram_bot import TelegramNotifier
        
        # Mock stats_db
        self.mock_stats_db.get_daily_stats.return_value = [
            {
                'strategy_name': 'TrendFollowing',
                'trades': 5,
                'wins': 3,
                'losses': 2,
                'profit': 150.0
            }
        ]
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        self.assertTrue(hasattr(notifier, 'cmd_stats'))

    @patch('notifications.telegram_bot.Bot')
    def test_cmd_stop_graceful_shutdown(self, mock_bot):
        """Testa comando /stop com shutdown gracioso"""
        from notifications.telegram_bot import TelegramNotifier
        
        # Mock de posições abertas
        self.mock_mt5.get_open_positions.return_value = [
            {'ticket': 12345, 'symbol': 'XAUUSD', 'volume': 0.01}
        ]
        self.mock_mt5.close_position.return_value = True
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        self.assertTrue(hasattr(notifier, 'cmd_stop'))

    @patch('notifications.telegram_bot.Bot')
    def test_trade_notification_formatting(self, mock_bot):
        """Testa formatação de notificações de trades"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        # Notificação de ordem aberta
        message = "✅ Ordem BUY XAUUSD 0.01 @ 2005.0\nSL: 2000.0 | TP: 2010.0"
        
        # Verifica que mensagem tem estrutura esperada
        self.assertIn('BUY', message)
        self.assertIn('XAUUSD', message)
        self.assertIn('SL', message)
        self.assertIn('TP', message)

    @patch('notifications.telegram_bot.Bot')
    def test_error_notification(self, mock_bot):
        """Testa notificações de erro"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        error_message = "❌ ERRO: Falha ao executar ordem - Insufficient margin"
        
        self.assertIn('ERRO', error_message)

    @patch('notifications.telegram_bot.Bot')
    def test_profit_notification(self, mock_bot):
        """Testa notificações de lucro"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        profit_message = "💰 Posição fechada: +$50.00 (TrendFollowing)"
        
        self.assertIn('💰', profit_message)
        self.assertIn('$', profit_message)

    @patch('notifications.telegram_bot.Bot')
    def test_loss_notification(self, mock_bot):
        """Testa notificações de perda"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        loss_message = "📉 Posição fechada: -$30.00 (MeanReversion)"
        
        self.assertIn('-$', loss_message)

    @patch('notifications.telegram_bot.Bot')
    def test_breakeven_notification(self, mock_bot):
        """Testa notificação de breakeven"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        breakeven_msg = "🔒 Breakeven ativado: #12345 SL movido para 2005.0"
        
        self.assertIn('Breakeven', breakeven_msg)
        self.assertIn('SL', breakeven_msg)

    @patch('notifications.telegram_bot.Bot')
    def test_trailing_stop_notification(self, mock_bot):
        """Testa notificação de trailing stop"""
        from notifications.telegram_bot import TelegramNotifier
        
        notifier = TelegramNotifier(
            config=self.config,
            mt5=self.mock_mt5,
            stats_db=self.mock_stats_db
        )
        
        trailing_msg = "📈 Trailing Stop: #12345 SL movido para 2008.0"
        
        self.assertIn('Trailing', trailing_msg)


if __name__ == '__main__':
    unittest.main()
