"""
Testes Unitários - OrderManager
Testa trailing stop, break-even, parcial close, thread safety
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from order_manager import OrderManager


class TestOrderManager(unittest.TestCase):
    """Testes para OrderManager"""
    
    def setUp(self):
        """Setup executado antes de cada teste"""
        self.config = {
            'order_manager': {
                'enabled': True,
                'cycle_interval_seconds': 60,
                'partial_close': {
                    'enabled': True,
                    'target_pips': 50,
                    'close_percentage': 0.5
                }
            },
            'strategies': {
                'trend_following': {
                    'trailing_stop_distance': 20,
                    'break_even_trigger': 30,
                    'partial_close_trigger': 40
                }
            },
            'risk': {
                'max_drawdown': 0.08,
                'trailing_stop_enabled': True
            },
            'trading': {
                'symbol': 'XAUUSD',
                'max_open_positions': 6
            }
        }
        
        # Mock dependencies
        self.mock_mt5 = Mock()
        self.mock_mt5.get_open_positions.return_value = []
        self.mock_mt5.get_symbol_tick.return_value = {
            'ask': 2000.10,
            'bid': 2000.00
        }
        
        self.mock_telegram = Mock()
        
        # Patch dependencies na criação do OrderManager
        with patch('order_manager.MT5Connector', return_value=self.mock_mt5), \
             patch('order_manager.TelegramNotifier', return_value=self.mock_telegram):
            self.order_manager = OrderManager(config=self.config, telegram=self.mock_telegram)
            self.order_manager.mt5 = self.mock_mt5
    
    def test_initialization(self):
        """Testa inicialização do OrderManager"""
        self.assertTrue(self.order_manager.enabled)
        self.assertEqual(self.order_manager.cycle_interval, 60)
        self.assertIsInstance(self.order_manager.monitored_positions, dict)
        self.assertIsNotNone(self.order_manager.positions_lock)
    
    def test_should_move_to_breakeven_buy_position(self):
        """Testa break-even para posição BUY"""
        position = {
            'ticket': 12345,
            'type': 'BUY',
            'price_open': 2000.0,
            'price_current': 2003.0,  # +30 pips
            'sl': 1995.0,
            'magic': 100477  # trend_following
        }
        
        # Adicionar à lista monitorada
        with self.order_manager.positions_lock:
            self.order_manager.monitored_positions[12345] = {
                'breakeven_applied': False
            }
        
        should_move, new_sl = self.order_manager.should_move_to_breakeven(12345, position)
        
        self.assertTrue(should_move)
        self.assertEqual(new_sl, 2000.0)  # Break-even = entrada
    
    def test_should_move_to_breakeven_sell_position(self):
        """Testa break-even para posição SELL"""
        position = {
            'ticket': 12346,
            'type': 'SELL',
            'price_open': 2000.0,
            'price_current': 1997.0,  # +30 pips
            'sl': 2005.0,
            'magic': 100477
        }
        
        with self.order_manager.positions_lock:
            self.order_manager.monitored_positions[12346] = {
                'breakeven_applied': False
            }
        
        should_move, new_sl = self.order_manager.should_move_to_breakeven(12346, position)
        
        self.assertTrue(should_move)
        self.assertEqual(new_sl, 2000.0)
    
    def test_should_not_move_breakeven_already_applied(self):
        """Testa que não aplica break-even duas vezes"""
        position = {
            'ticket': 12347,
            'type': 'BUY',
            'price_open': 2000.0,
            'price_current': 2003.0,
            'sl': 2000.0,  # Já em break-even
            'magic': 100477
        }
        
        with self.order_manager.positions_lock:
            self.order_manager.monitored_positions[12347] = {
                'breakeven_applied': True  # Já aplicado
            }
        
        should_move, _ = self.order_manager.should_move_to_breakeven(12347, position)
        
        self.assertFalse(should_move)
    
    def test_calculate_trailing_stop_buy(self):
        """Testa trailing stop para BUY"""
        position = {
            'ticket': 12348,
            'type': 'BUY',
            'price_open': 2000.0,
            'price_current': 2005.0,
            'sl': 2000.0,
            'magic': 100477  # 20 pips trailing
        }
        
        with self.order_manager.positions_lock:
            self.order_manager.monitored_positions[12348] = {}
        
        # Mock calculate_trailing_stop do RiskManager
        self.order_manager.risk_manager.calculate_trailing_stop = Mock(return_value=2003.0)
        
        new_sl = self.order_manager.calculate_trailing_stop(12348, position)
        
        self.assertEqual(new_sl, 2003.0)
        self.assertGreater(new_sl, position['sl'])
    
    def test_should_partial_close_enabled(self):
        """Testa fechamento parcial quando atingido"""
        position = {
            'ticket': 12349,
            'type': 'BUY',
            'price_open': 2000.0,
            'price_current': 2005.0,  # +50 pips
            'volume': 0.10,
            'magic': 100477
        }
        
        with self.order_manager.positions_lock:
            self.order_manager.monitored_positions[12349] = {}
        
        should_close, volume = self.order_manager.should_partial_close(12349, position)
        
        self.assertTrue(should_close)
        self.assertEqual(volume, 0.05)  # 50% de 0.10
    
    def test_should_not_partial_close_below_target(self):
        """Testa que não fecha parcial antes do target"""
        position = {
            'ticket': 12350,
            'type': 'BUY',
            'price_open': 2000.0,
            'price_current': 2002.0,  # Apenas +20 pips
            'volume': 0.10,
            'magic': 100477
        }
        
        with self.order_manager.positions_lock:
            self.order_manager.monitored_positions[12350] = {}
        
        should_close, _ = self.order_manager.should_partial_close(12350, position)
        
        self.assertFalse(should_close)
    
    def test_thread_safety_concurrent_access(self):
        """Testa thread safety com acessos concorrentes"""
        # Adicionar 10 posições
        for i in range(10):
            with self.order_manager.positions_lock:
                self.order_manager.monitored_positions[i] = {
                    'ticket': i,
                    'profit': 0.0
                }
        
        results = []
        errors = []
        
        def update_position(ticket):
            """Thread worker que atualiza posição"""
            try:
                for _ in range(100):
                    with self.order_manager.positions_lock:
                        if ticket in self.order_manager.monitored_positions:
                            self.order_manager.monitored_positions[ticket]['profit'] += 1.0
                results.append(True)
            except Exception as e:
                errors.append(e)
        
        # Criar 10 threads atualizando concorrentemente
        threads = []
        for i in range(10):
            t = threading.Thread(target=update_position, args=(i,))
            threads.append(t)
            t.start()
        
        # Aguardar todas as threads
        for t in threads:
            t.join()
        
        # Verificar que não houve erros
        self.assertEqual(len(errors), 0, f"Erros de concorrência: {errors}")
        
        # Verificar que todas as atualizações foram aplicadas
        with self.order_manager.positions_lock:
            for i in range(10):
                self.assertEqual(
                    self.order_manager.monitored_positions[i]['profit'],
                    100.0,
                    f"Posição {i} não foi atualizada corretamente"
                )
    
    def test_update_monitored_positions_new_position(self):
        """Testa adição de nova posição monitorada"""
        self.mock_mt5.get_open_positions.return_value = [{
            'ticket': 99999,
            'type': 'BUY',
            'volume': 0.01,
            'price_open': 2000.0,
            'sl': 1995.0,
            'tp': 2010.0,
            'profit': 50.0
        }]
        
        self.order_manager.update_monitored_positions()
        
        with self.order_manager.positions_lock:
            self.assertIn(99999, self.order_manager.monitored_positions)
            pos = self.order_manager.monitored_positions[99999]
            self.assertEqual(pos['ticket'], 99999)
            self.assertEqual(pos['type'], 'BUY')
            self.assertFalse(pos['breakeven_applied'])
    
    def test_update_monitored_positions_closed_position(self):
        """Testa remoção de posição fechada"""
        # Adicionar posição monitorada
        with self.order_manager.positions_lock:
            self.order_manager.monitored_positions[88888] = {
                'ticket': 88888,
                'type': 'BUY'
            }
        
        # MT5 retorna vazio (posição fechada)
        self.mock_mt5.get_open_positions.return_value = []
        
        self.order_manager.update_monitored_positions()
        
        # Posição deve ter sido removida
        with self.order_manager.positions_lock:
            self.assertNotIn(88888, self.order_manager.monitored_positions)
    
    def test_validate_spread_before_modify(self):
        """Testa validação de spread antes de modificar"""
        # Spread normal
        self.mock_mt5.get_symbol_tick.return_value = {
            'ask': 2000.05,
            'bid': 2000.00  # Spread = 5 pips
        }
        
        result = self.order_manager._validate_spread_before_modify('XAUUSD')
        self.assertTrue(result)
        
        # Spread alto
        self.mock_mt5.get_symbol_tick.return_value = {
            'ask': 2000.10,
            'bid': 2000.00  # Spread = 10 pips (alto)
        }
        
        result = self.order_manager._validate_spread_before_modify('XAUUSD')
        self.assertFalse(result)
    
    def test_get_strategy_config(self):
        """Testa obtenção de configuração da estratégia"""
        magic = 100477  # trend_following
        
        config = self.order_manager.get_strategy_config(magic)
        
        self.assertEqual(config['trailing_stop_distance'], 20)
        self.assertEqual(config['break_even_trigger'], 30)


if __name__ == '__main__':
    unittest.main(verbosity=2)
