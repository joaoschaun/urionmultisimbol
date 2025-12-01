# -*- coding: utf-8 -*-
"""
Test Configuration - pytest

Configurações globais para testes.
"""

import pytest
import sys
import os

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def project_root():
    """Retorna raiz do projeto"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def test_data_dir(project_root):
    """Retorna diretório de dados de teste"""
    test_dir = os.path.join(project_root, 'data', 'test')
    os.makedirs(test_dir, exist_ok=True)
    return test_dir


@pytest.fixture
def mock_mt5():
    """Mock do MetaTrader5"""
    from unittest.mock import MagicMock
    
    mt5 = MagicMock()
    mt5.initialize.return_value = True
    mt5.login.return_value = True
    mt5.terminal_info.return_value = MagicMock(connected=True)
    mt5.account_info.return_value = MagicMock(
        balance=10000,
        equity=10500,
        margin=100,
        margin_free=10400
    )
    mt5.positions_get.return_value = []
    
    return mt5


@pytest.fixture
def mock_redis():
    """Mock do Redis"""
    from unittest.mock import MagicMock
    
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.ping.return_value = True
    
    return redis_mock
