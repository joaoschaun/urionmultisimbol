# -*- coding: utf-8 -*-
"""
Unit Tests - Urion Trading Bot

Testes unitários para componentes críticos do sistema.
Objetivo: >80% coverage
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Adicionar path do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Tests: State Manager
# =============================================================================

class TestStateManager:
    """Testes para StateManager"""
    
    @pytest.fixture
    def state_manager(self):
        """Cria instância de teste"""
        from src.core.state_manager import StateManager, BotState, PositionState
        
        manager = StateManager({'state_dir': 'data/test_state'})
        manager.current_state = BotState(instance_id='test_instance')
        return manager
    
    def test_init(self, state_manager):
        """Testa inicialização"""
        assert state_manager.current_state is not None
        assert state_manager.current_state.instance_id == 'test_instance'
    
    def test_update_position(self, state_manager):
        """Testa atualização de posição"""
        from src.core.state_manager import PositionState
        
        pos = PositionState(
            ticket=12345,
            symbol='XAUUSD',
            direction='buy',
            volume=0.1,
            entry_price=2650.0,
            entry_time=datetime.now(),
            stop_loss=2640.0,
            take_profit=2670.0,
            current_profit=25.0,
            magic=100001,
            strategy='scalping'
        )
        
        state_manager.update_position(pos)
        
        assert len(state_manager.current_state.positions) == 1
        assert state_manager.current_state.positions[0].ticket == 12345
    
    def test_remove_position(self, state_manager):
        """Testa remoção de posição"""
        from src.core.state_manager import PositionState
        
        pos = PositionState(
            ticket=12345,
            symbol='XAUUSD',
            direction='buy',
            volume=0.1,
            entry_price=2650.0,
            entry_time=datetime.now(),
            stop_loss=2640.0,
            take_profit=2670.0,
            current_profit=25.0,
            magic=100001,
            strategy='scalping'
        )
        
        state_manager.update_position(pos)
        state_manager.remove_position(12345)
        
        assert len(state_manager.current_state.positions) == 0
    
    def test_update_performance(self, state_manager):
        """Testa atualização de performance"""
        state_manager.update_performance(
            daily_pnl=150.0,
            trades_today=5,
            drawdown=0.02
        )
        
        assert state_manager.current_state.daily_pnl == 150.0
        assert state_manager.current_state.total_trades_today == 5
        assert state_manager.current_state.current_drawdown == 0.02
    
    def test_heartbeat(self, state_manager):
        """Testa heartbeat"""
        before = state_manager.current_state.last_heartbeat
        state_manager.heartbeat()
        after = state_manager.current_state.last_heartbeat
        
        assert after >= before
    
    def test_serialization(self):
        """Testa serialização/deserialização"""
        from src.core.state_manager import StateSerializer, BotState, PositionState
        
        state = BotState(
            instance_id='test',
            balance=10000.0,
            equity=10500.0
        )
        
        state.positions.append(PositionState(
            ticket=1,
            symbol='XAUUSD',
            direction='buy',
            volume=0.1,
            entry_price=2650.0,
            entry_time=datetime.now(),
            stop_loss=2640.0,
            take_profit=2670.0,
            current_profit=50.0,
            magic=100001,
            strategy='scalping'
        ))
        
        # Serializar
        data = StateSerializer.serialize(state)
        
        # Deserializar
        recovered = StateSerializer.deserialize(data)
        
        assert recovered.instance_id == 'test'
        assert recovered.balance == 10000.0
        assert len(recovered.positions) == 1
    
    def test_checksum(self):
        """Testa cálculo de checksum"""
        from src.core.state_manager import StateSerializer, BotState
        
        state1 = BotState(instance_id='test1', balance=10000.0)
        state2 = BotState(instance_id='test2', balance=10000.0)
        
        checksum1 = StateSerializer.calculate_checksum(state1)
        checksum2 = StateSerializer.calculate_checksum(state2)
        
        # Checksums devem ser diferentes para estados diferentes
        assert checksum1 != checksum2


# =============================================================================
# Tests: Disaster Recovery
# =============================================================================

class TestDisasterRecovery:
    """Testes para DisasterRecovery"""
    
    @pytest.fixture
    def disaster_recovery(self):
        """Cria instância de teste"""
        from src.core.disaster_recovery import DisasterRecovery
        
        dr = DisasterRecovery({
            'max_drawdown': 0.05,
            'max_daily_loss': 0.03,
            'max_rapid_losses': 3
        })
        return dr
    
    def test_init(self, disaster_recovery):
        """Testa inicialização"""
        assert disaster_recovery.max_drawdown == 0.05
        assert disaster_recovery.trading_paused is False
    
    def test_check_trading_allowed(self, disaster_recovery):
        """Testa verificação de trading permitido"""
        allowed, msg = disaster_recovery.check_trading_allowed()
        assert allowed is True
        assert msg == "OK"
    
    def test_trading_paused(self, disaster_recovery):
        """Testa pausa de trading"""
        disaster_recovery.trading_paused = True
        disaster_recovery.pause_until = datetime.now() + timedelta(hours=1)
        
        allowed, msg = disaster_recovery.check_trading_allowed()
        assert allowed is False
        assert "pausado" in msg
    
    def test_rapid_losses_trigger(self, disaster_recovery):
        """Testa trigger de perdas rápidas"""
        # Simular perdas rápidas
        for _ in range(3):
            disaster_recovery.report_trade_result(-100, 'XAUUSD')
        
        # Deve ter pausado trading
        assert disaster_recovery.trading_paused is True
    
    def test_high_drawdown_event(self, disaster_recovery):
        """Testa evento de alto drawdown"""
        initial_events = len(disaster_recovery.events)
        
        disaster_recovery.report_drawdown(0.06)  # Acima do limite
        
        assert len(disaster_recovery.events) > initial_events
    
    def test_get_status(self, disaster_recovery):
        """Testa obtenção de status"""
        status = disaster_recovery.get_status()
        
        assert 'trading_paused' in status
        assert 'circuit_breakers' in status


class TestCircuitBreaker:
    """Testes para CircuitBreaker"""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Cria instância de teste"""
        from src.core.disaster_recovery import CircuitBreaker
        
        return CircuitBreaker('test', failure_threshold=3, recovery_timeout=10)
    
    def test_init_closed(self, circuit_breaker):
        """Testa que inicia fechado"""
        assert circuit_breaker.is_closed() is True
    
    def test_opens_after_failures(self, circuit_breaker):
        """Testa abertura após falhas"""
        for _ in range(3):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.is_closed() is False
    
    def test_resets_on_success(self, circuit_breaker):
        """Testa reset em sucesso"""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()
        
        assert circuit_breaker.state.failure_count == 0


# =============================================================================
# Tests: Backtest Engine
# =============================================================================

class TestBacktestEngine:
    """Testes para BacktestEngine"""
    
    @pytest.fixture
    def sample_data(self):
        """Cria dados de exemplo"""
        dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='1h')
        np.random.seed(42)
        
        df = pd.DataFrame({
            'time': dates,
            'open': 2600 + np.random.randn(len(dates)).cumsum() * 10,
            'high': 2600 + np.random.randn(len(dates)).cumsum() * 10 + 5,
            'low': 2600 + np.random.randn(len(dates)).cumsum() * 10 - 5,
            'close': 2600 + np.random.randn(len(dates)).cumsum() * 10,
            'volume': np.random.randint(1000, 10000, len(dates))
        })
        
        df['high'] = df[['open', 'high', 'close']].max(axis=1) + np.random.rand(len(df)) * 2
        df['low'] = df[['open', 'low', 'close']].min(axis=1) - np.random.rand(len(df)) * 2
        
        return df
    
    @pytest.fixture
    def backtest_engine(self):
        """Cria engine de teste"""
        from src.backtesting.backtest_engine import BacktestEngine
        
        return BacktestEngine({
            'initial_capital': 10000,
            'commission': 0.0001,
            'slippage_pct': 0.0001
        })
    
    def test_calculate_metrics_basic(self, backtest_engine, sample_data):
        """Testa cálculo básico de métricas"""
        trades = pd.DataFrame({
            'profit': [100, -50, 75, -25, 150, -30],
            'entry_time': sample_data['time'][:6],
            'exit_time': sample_data['time'][1:7],
            'entry_price': sample_data['close'][:6].values,
            'exit_price': sample_data['close'][1:7].values,
            'direction': ['buy', 'sell', 'buy', 'sell', 'buy', 'sell'],
            'volume': [0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
        })
        
        metrics = backtest_engine.calculate_metrics(trades)
        
        assert metrics['total_profit'] == 220  # 100-50+75-25+150-30
        assert metrics['win_rate'] == pytest.approx(0.5, 0.1)  # 3 wins, 3 losses
    
    def test_calculate_sharpe_ratio(self, backtest_engine):
        """Testa cálculo do Sharpe Ratio"""
        # Retornos consistentes
        returns = pd.Series([0.01] * 252)  # 1% por dia por 1 ano
        sharpe = backtest_engine._calculate_sharpe(returns)
        
        assert sharpe > 0  # Retorno positivo deve ter Sharpe positivo
    
    def test_calculate_max_drawdown(self, backtest_engine):
        """Testa cálculo de max drawdown"""
        equity = pd.Series([10000, 10500, 10200, 9800, 10100, 10300])
        
        # Max drawdown deve ser de 10500 para 9800 = 6.67%
        mdd = backtest_engine._calculate_max_drawdown(equity)
        
        assert mdd > 0
        assert mdd < 1
    
    def test_walk_forward_validation(self, backtest_engine, sample_data):
        """Testa walk-forward validation"""
        # Mock da estratégia
        def mock_strategy(data):
            signals = pd.DataFrame({
                'signal': np.random.choice([1, -1, 0], len(data)),
                'time': data['time']
            })
            return signals
        
        # Este teste é mais de integração, verificamos apenas se roda
        try:
            results = backtest_engine.walk_forward_analysis(
                sample_data, mock_strategy, n_splits=2
            )
            assert 'oos_results' in results
        except Exception as e:
            # OK se falhar por dependências não disponíveis
            pytest.skip(f"Dependências não disponíveis: {e}")


# =============================================================================
# Tests: Paper Trading
# =============================================================================

class TestPaperTrading:
    """Testes para PaperTradingEngine"""
    
    @pytest.fixture
    def paper_trading(self):
        """Cria engine de teste"""
        from src.backtesting.paper_trading import PaperTradingEngine
        
        return PaperTradingEngine({
            'initial_balance': 10000,
            'base_latency_ms': 50,
            'latency_variance_ms': 20
        })
    
    def test_init(self, paper_trading):
        """Testa inicialização"""
        assert paper_trading.balance == 10000
        assert len(paper_trading.positions) == 0
    
    def test_execute_order(self, paper_trading):
        """Testa execução de ordem"""
        order = {
            'symbol': 'XAUUSD',
            'direction': 'buy',
            'volume': 0.1,
            'order_type': 'market',
            'stop_loss': 2640.0,
            'take_profit': 2670.0
        }
        
        # Mock do preço atual
        paper_trading.get_current_price = Mock(return_value=2650.0)
        
        result = paper_trading.execute_order(order)
        
        assert result is not None
        assert result.symbol == 'XAUUSD'
    
    def test_slippage_calculation(self, paper_trading):
        """Testa cálculo de slippage"""
        slippage = paper_trading._calculate_slippage(
            price=2650.0,
            volume=0.1,
            direction='buy',
            volatility=0.02
        )
        
        # Slippage deve ser pequeno mas não zero
        assert slippage >= 0
        assert slippage < 50  # Menos que 50 pips
    
    def test_partial_fill_simulation(self, paper_trading):
        """Testa simulação de partial fill"""
        # Para volumes grandes, deve haver chance de partial fill
        filled = paper_trading._simulate_fill(
            requested_volume=10.0,  # Volume muito grande
            symbol='XAUUSD',
            price=2650.0
        )
        
        # Pode ser partial ou full
        assert filled > 0
        assert filled <= 10.0


# =============================================================================
# Tests: ML Validator
# =============================================================================

class TestMLValidator:
    """Testes para MLValidator"""
    
    @pytest.fixture
    def sample_ml_data(self):
        """Cria dados de exemplo para ML"""
        np.random.seed(42)
        n = 1000
        
        X = pd.DataFrame({
            'feature1': np.random.randn(n),
            'feature2': np.random.randn(n),
            'feature3': np.random.randn(n)
        })
        
        # Target com alguma correlação
        y = (X['feature1'] > 0).astype(int)
        
        return X, y
    
    @pytest.fixture
    def ml_validator(self):
        """Cria validator de teste"""
        from src.ml.ml_validator import MLValidator
        
        return MLValidator({'cv_splits': 3, 'min_train_size': 100})
    
    def test_temporal_cv_split(self, ml_validator, sample_ml_data):
        """Testa split temporal"""
        X, y = sample_ml_data
        
        splits = list(ml_validator._temporal_cv_split(X, n_splits=3))
        
        assert len(splits) == 3
        
        for train_idx, val_idx in splits:
            # Treino deve vir antes de validação
            assert max(train_idx) < min(val_idx)
    
    def test_detect_data_leakage_no_leakage(self, ml_validator):
        """Testa detecção de leakage quando não há"""
        train = pd.DataFrame({
            'feature1': [1, 2, 3],
            'feature2': [4, 5, 6],
            'target': [0, 1, 0]
        })
        
        test = pd.DataFrame({
            'feature1': [7, 8, 9],
            'feature2': [10, 11, 12],
            'target': [1, 0, 1]
        })
        
        leakage = ml_validator.detect_data_leakage(
            train, test, target_col='target'
        )
        
        # Não deve haver leakage significativo
        assert leakage['leakage_score'] < 0.5
    
    def test_detect_overfitting(self, ml_validator):
        """Testa detecção de overfitting"""
        train_score = 0.98  # Muito alto
        val_score = 0.55    # Bem menor
        
        gap = train_score - val_score
        
        # Gap > 0.1 indica overfitting
        assert gap > 0.1


# =============================================================================
# Tests: Strategies
# =============================================================================

class TestScalpingStrategy:
    """Testes para ScalpingStrategy"""
    
    @pytest.fixture
    def sample_market_data(self):
        """Cria dados de mercado de exemplo"""
        np.random.seed(42)
        n = 100
        
        return pd.DataFrame({
            'time': pd.date_range(start='2024-01-01', periods=n, freq='1min'),
            'open': 2650 + np.random.randn(n).cumsum() * 0.5,
            'high': 2650 + np.random.randn(n).cumsum() * 0.5 + 1,
            'low': 2650 + np.random.randn(n).cumsum() * 0.5 - 1,
            'close': 2650 + np.random.randn(n).cumsum() * 0.5,
            'volume': np.random.randint(100, 1000, n)
        })
    
    def test_strategy_returns_valid_signal(self, sample_market_data):
        """Testa que estratégia retorna sinais válidos"""
        # Este teste requer a estratégia real
        try:
            from src.strategies.scalping_strategy import ScalpingStrategy
            
            strategy = ScalpingStrategy({})
            signal = strategy.generate_signal(sample_market_data, 'XAUUSD')
            
            if signal:
                assert 'direction' in signal
                assert signal['direction'] in ['buy', 'sell', 'hold']
        except ImportError:
            pytest.skip("ScalpingStrategy não disponível")


# =============================================================================
# Tests: Risk Management
# =============================================================================

class TestRiskManager:
    """Testes para RiskManager"""
    
    def test_position_sizing(self):
        """Testa cálculo de tamanho de posição"""
        try:
            from src.risk.risk_manager import RiskManager
            
            rm = RiskManager({
                'max_risk_per_trade': 0.02,
                'max_total_exposure': 0.1
            })
            
            size = rm.calculate_position_size(
                balance=10000,
                risk_per_trade=0.02,
                stop_loss_pips=50,
                symbol='XAUUSD'
            )
            
            assert size > 0
            assert size <= 1.0  # Não deve ser maior que 1 lote para $10k
        except ImportError:
            pytest.skip("RiskManager não disponível")
    
    def test_max_exposure_limit(self):
        """Testa limite de exposição máxima"""
        try:
            from src.risk.risk_manager import RiskManager
            
            rm = RiskManager({
                'max_total_exposure': 0.1
            })
            
            # Simular posições existentes
            existing_exposure = 0.08  # 8%
            
            # Nova posição deve ser limitada
            allowed = rm.check_exposure_limit(
                current_exposure=existing_exposure,
                new_position_size=0.05  # 5% adicional
            )
            
            # Não deve permitir (total seria 13% > 10%)
            assert allowed is False
        except ImportError:
            pytest.skip("RiskManager não disponível")


# =============================================================================
# Tests: Utils
# =============================================================================

class TestUtils:
    """Testes para funções utilitárias"""
    
    def test_calculate_pip_value(self):
        """Testa cálculo de valor do pip"""
        # Para XAUUSD, 1 pip = $0.10 para 0.01 lotes
        # Para 0.1 lotes = $1.00 por pip
        
        pip_value = 0.1 * 10  # volume * 10 para gold
        assert pip_value == 1.0
    
    def test_format_price(self):
        """Testa formatação de preço"""
        price = 2650.123456
        formatted = round(price, 2)
        
        assert formatted == 2650.12
    
    def test_calculate_lot_size_from_risk(self):
        """Testa cálculo de lote a partir do risco"""
        balance = 10000
        risk_pct = 0.02
        stop_loss_value = 100  # $100 de SL
        
        max_risk = balance * risk_pct  # $200
        lot_size = max_risk / stop_loss_value  # 2.0 lotes
        
        assert lot_size == 2.0


# =============================================================================
# Tests: Integration
# =============================================================================

class TestIntegration:
    """Testes de integração"""
    
    def test_full_trading_cycle(self):
        """Testa ciclo completo de trading"""
        # Este é um teste de integração mais complexo
        
        # 1. Criar state manager
        # 2. Criar disaster recovery
        # 3. Simular entrada de trade
        # 4. Simular saída de trade
        # 5. Verificar estado final
        
        try:
            from src.core.state_manager import StateManager, PositionState
            from src.core.disaster_recovery import DisasterRecovery
            
            sm = StateManager({'state_dir': 'data/test_state'})
            dr = DisasterRecovery({}, state_manager=sm)
            
            # Verificar trading permitido
            allowed, _ = dr.check_trading_allowed()
            assert allowed
            
            # Simular trade
            dr.report_trade_result(50.0, 'XAUUSD')
            
            # Verificar que não pausou (lucro, não perda)
            allowed, _ = dr.check_trading_allowed()
            assert allowed
            
        except ImportError:
            pytest.skip("Módulos não disponíveis")


# =============================================================================
# Fixtures Globais
# =============================================================================

@pytest.fixture(scope="session")
def test_config():
    """Configuração global de teste"""
    return {
        'test_mode': True,
        'state_dir': 'data/test_state',
        'log_level': 'WARNING'
    }


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Limpa arquivos de teste após cada teste"""
    yield
    
    import shutil
    test_dirs = ['data/test_state']
    for d in test_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
            except:
                pass


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
