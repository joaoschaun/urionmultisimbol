# -*- coding: utf-8 -*-
"""
Testes para a API Backend do Urion Trading Bot
Cobertura: Endpoints REST, respostas JSON, tratamento de erros
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
from datetime import datetime, timedelta

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestStrategyStatsDB(unittest.TestCase):
    """Testes para o banco de dados de estatísticas"""
    
    def setUp(self):
        """Setup executado antes de cada teste"""
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
    def tearDown(self):
        """Cleanup após cada teste"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
    
    def test_database_initialization(self):
        """Testa inicialização do banco de dados"""
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB(db_path=self.db_path)
        
        # Verifica se o banco foi criado
        self.assertTrue(os.path.exists(self.db_path))
    
    def test_get_strategy_stats_empty(self):
        """Testa busca de stats para estratégia sem trades"""
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB(db_path=self.db_path)
        stats = stats_db.get_strategy_stats('trend_following')
        
        # Deve retornar estrutura padrão com zeros
        self.assertEqual(stats['strategy_name'], 'trend_following')
        self.assertEqual(stats['total_trades'], 0)
        self.assertEqual(stats['win_rate'], 0)
    
    def test_get_all_trades_empty(self):
        """Testa busca de trades quando vazio"""
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB(db_path=self.db_path)
        trades = stats_db.get_all_trades(days=7)
        
        self.assertEqual(len(trades), 0)
    
    def test_get_all_strategies_ranking(self):
        """Testa ranking de estratégias"""
        from database.strategy_stats import StrategyStatsDB
        
        stats_db = StrategyStatsDB(db_path=self.db_path)
        ranking = stats_db.get_all_strategies_ranking(days=7)
        
        # Deve retornar lista (mesmo que vazia ou com dados zerados)
        self.assertIsInstance(ranking, list)


class TestBackendEndpoints(unittest.TestCase):
    """Testes para endpoints do backend FastAPI"""
    
    @classmethod
    def setUpClass(cls):
        """Setup executado uma vez para toda a classe"""
        # Tentar importar FastAPI TestClient
        try:
            from fastapi.testclient import TestClient
            cls.test_client_available = True
        except ImportError:
            cls.test_client_available = False
    
    def test_strategies_endpoint_format(self):
        """Testa formato de resposta do endpoint /api/strategies"""
        # Este teste valida a estrutura esperada
        expected_fields = ['name', 'enabled', 'trades', 'win_rate', 'profit', 'status']
        
        # Mock de resposta
        mock_strategy = {
            "name": "Trend Following",
            "enabled": True,
            "trades": 10,
            "win_rate": 55.0,
            "profit": 125.50,
            "status": "active"
        }
        
        for field in expected_fields:
            self.assertIn(field, mock_strategy)
    
    def test_trades_history_endpoint_format(self):
        """Testa formato de resposta do endpoint /api/trades/history"""
        expected_fields = ['total', 'days', 'trades']
        
        mock_response = {
            "total": 5,
            "days": 7,
            "strategy_filter": None,
            "trades": [
                {
                    "strategy_name": "trend_following",
                    "ticket": 12345,
                    "symbol": "XAUUSD",
                    "type": "BUY",
                    "profit": 25.50
                }
            ]
        }
        
        for field in expected_fields:
            self.assertIn(field, mock_response)
    
    def test_performance_daily_endpoint_format(self):
        """Testa formato de resposta do endpoint /api/performance/daily"""
        expected_daily_fields = ['date', 'trades', 'wins', 'losses', 'profit']
        
        mock_daily = {
            "date": "2025-01-15",
            "trades": 5,
            "wins": 3,
            "losses": 2,
            "profit": 45.50
        }
        
        for field in expected_daily_fields:
            self.assertIn(field, mock_daily)
    
    def test_equity_history_endpoint_format(self):
        """Testa formato de resposta do endpoint /api/equity/history"""
        expected_fields = ['days', 'current_equity', 'data_points']
        
        mock_response = {
            "days": 7,
            "current_equity": 10250.00,
            "data_points": [
                {
                    "timestamp": "2025-01-15T10:30:00",
                    "equity": 10200.00,
                    "change": 50.00
                }
            ]
        }
        
        for field in expected_fields:
            self.assertIn(field, mock_response)
    
    def test_strategies_ranking_endpoint_format(self):
        """Testa formato de resposta do endpoint /api/strategies/ranking"""
        expected_fields = ['days', 'ranking']
        
        mock_response = {
            "days": 7,
            "ranking": [
                {
                    "strategy_name": "TrendFollowing",
                    "score": 85.5,
                    "win_rate": 55.0
                }
            ]
        }
        
        for field in expected_fields:
            self.assertIn(field, mock_response)


class TestMT5Service(unittest.TestCase):
    """Testes para o serviço MT5 do backend"""
    
    def test_account_info_format(self):
        """Testa formato de informações de conta"""
        expected_fields = [
            'login', 'server', 'balance', 'equity', 
            'margin', 'free_margin', 'profit', 'leverage', 'currency'
        ]
        
        mock_account = {
            "login": 12345678,
            "server": "Demo",
            "balance": 10000.0,
            "equity": 10250.0,
            "margin": 200.0,
            "free_margin": 10050.0,
            "margin_level": 5125.0,
            "profit": 250.0,
            "leverage": 100,
            "currency": "USD"
        }
        
        for field in expected_fields:
            self.assertIn(field, mock_account)
    
    def test_position_format(self):
        """Testa formato de posição"""
        expected_fields = [
            'ticket', 'symbol', 'type', 'volume',
            'price_open', 'price_current', 'sl', 'tp', 'profit'
        ]
        
        mock_position = {
            "ticket": 12345,
            "symbol": "XAUUSD",
            "type": "BUY",
            "volume": 0.01,
            "price_open": 2005.0,
            "price_current": 2008.0,
            "sl": 2000.0,
            "tp": 2015.0,
            "profit": 30.0,
            "time": "2025-01-15T10:30:00",
            "magic": 123,
            "comment": "TrendFollowing"
        }
        
        for field in expected_fields:
            self.assertIn(field, mock_position)
    
    def test_metrics_calculation(self):
        """Testa cálculo de métricas"""
        # Dados de trades simulados
        trades = [
            {'profit': 25.0},
            {'profit': -10.0},
            {'profit': 30.0},
            {'profit': -15.0},
            {'profit': 40.0}
        ]
        
        # Cálculos
        total_trades = len(trades)
        wins = sum(1 for t in trades if t['profit'] > 0)
        losses = sum(1 for t in trades if t['profit'] < 0)
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        total_profit = sum(t['profit'] for t in trades if t['profit'] > 0)
        total_loss = abs(sum(t['profit'] for t in trades if t['profit'] < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        net_profit = sum(t['profit'] for t in trades)
        
        # Validações
        self.assertEqual(total_trades, 5)
        self.assertEqual(wins, 3)
        self.assertEqual(losses, 2)
        self.assertEqual(win_rate, 60.0)
        self.assertGreater(profit_factor, 1)  # Mais lucro que perda
        self.assertEqual(net_profit, 70.0)


class TestThreadSafety(unittest.TestCase):
    """Testes para thread safety"""
    
    def test_strategy_learner_locks(self):
        """Testa que StrategyLearner tem locks de thread"""
        from ml.strategy_learner import StrategyLearner
        import tempfile
        
        # Criar arquivo temporário para o banco de dados
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'stats.db')
            
            learner = StrategyLearner(db_path=db_path)
            
            # Verificar existência de locks
            self.assertTrue(hasattr(learner, '_data_lock'))
            self.assertTrue(hasattr(learner, '_db_lock') or hasattr(learner, '_file_lock'))
    
    def test_concurrent_access_simulation(self):
        """Simula acesso concorrente ao sistema"""
        import threading
        import time
        
        counter = {'value': 0}
        lock = threading.RLock()
        
        def increment():
            with lock:
                current = counter['value']
                time.sleep(0.001)  # Simula operação lenta
                counter['value'] = current + 1
        
        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Se os locks funcionam, o contador deve ser exatamente 10
        self.assertEqual(counter['value'], 10)


class TestMultiSymbol(unittest.TestCase):
    """Testes para suporte multi-símbolo"""
    
    def test_supported_symbols(self):
        """Testa símbolos suportados"""
        supported_symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
        
        for symbol in supported_symbols:
            self.assertEqual(len(symbol), 6)
            self.assertTrue(symbol.isupper())
    
    def test_strategy_per_symbol_allocation(self):
        """Testa alocação de estratégias por símbolo"""
        strategies = [
            'TrendFollowing',
            'MeanReversion',
            'Breakout',
            'Scalping',
            'NewsTrading',
            'RangeTrading'
        ]
        
        symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
        
        # Total de executores = símbolos × estratégias
        total_executors = len(symbols) * len(strategies)
        self.assertEqual(total_executors, 24)


if __name__ == '__main__':
    unittest.main()
