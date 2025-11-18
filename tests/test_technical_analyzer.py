"""
Testes para o módulo de Análise Técnica
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Adicionar diretório src ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis.technical import TechnicalAnalyzer


@pytest.fixture
def mock_mt5_connector():
    """Mock do MT5Connector"""
    connector = Mock()
    connector.symbol = 'XAUUSD'
    return connector


@pytest.fixture
def mock_config():
    """Configuração mock para testes"""
    return {
        'mt5': {
            'symbol': 'XAUUSD'
        },
        'technical_analysis': {
            'indicators': {
                'ema_periods': [9, 21, 50],
                'sma_periods': [20, 50],
                'rsi_period': 14,
                'macd': {'fast': 12, 'slow': 26, 'signal': 9},
                'bollinger': {'period': 20, 'std': 2.0},
                'atr_period': 14,
                'adx_period': 14
            }
        }
    }


@pytest.fixture
def sample_dataframe():
    """Gera DataFrame de exemplo com dados OHLCV"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
    
    # Gerar dados sintéticos com tendência
    np.random.seed(42)
    base_price = 2000.0
    trend = np.linspace(0, 50, 100)  # Tendência de alta
    noise = np.random.randn(100) * 5
    
    close_prices = base_price + trend + noise
    
    df = pd.DataFrame({
        'Open': close_prices - np.random.rand(100) * 2,
        'High': close_prices + np.random.rand(100) * 3,
        'Low': close_prices - np.random.rand(100) * 3,
        'Close': close_prices,
        'Volume': np.random.randint(100, 1000, 100)
    }, index=dates)
    
    # Garantir High >= max(Open, Close) e Low <= min(Open, Close)
    df['High'] = df[['Open', 'High', 'Close']].max(axis=1)
    df['Low'] = df[['Open', 'Low', 'Close']].min(axis=1)
    
    return df


class TestTechnicalAnalyzer:
    """Testes para TechnicalAnalyzer"""
    
    def test_initialization(self, mock_mt5_connector, mock_config):
        """Testa inicialização do analisador"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        assert analyzer.mt5 == mock_mt5_connector
        assert analyzer.symbol == 'XAUUSD'
        assert analyzer.config == mock_config
        assert isinstance(analyzer._cache, dict)
    
    def test_calculate_ema(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de EMA"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        ema = analyzer.calculate_ema(sample_dataframe, 20)
        
        assert isinstance(ema, pd.Series)
        assert len(ema) == len(sample_dataframe)
        assert not ema.iloc[-1] == 0  # Não deve ser zero
    
    def test_calculate_sma(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de SMA"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        sma = analyzer.calculate_sma(sample_dataframe, 20)
        
        assert isinstance(sma, pd.Series)
        assert len(sma) == len(sample_dataframe)
    
    def test_calculate_rsi(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de RSI"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        rsi = analyzer.calculate_rsi(sample_dataframe, 14)
        
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(sample_dataframe)
        # RSI deve estar entre 0 e 100
        assert 0 <= rsi.iloc[-1] <= 100
    
    def test_calculate_macd(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de MACD"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        macd = analyzer.calculate_macd(sample_dataframe)
        
        assert 'macd' in macd
        assert 'signal' in macd
        assert 'histogram' in macd
        assert isinstance(macd['macd'], pd.Series)
        assert len(macd['macd']) == len(sample_dataframe)
    
    def test_calculate_bollinger_bands(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de Bandas de Bollinger"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        bb = analyzer.calculate_bollinger_bands(sample_dataframe)
        
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        
        # Upper deve ser maior que middle, middle maior que lower
        assert bb['upper'].iloc[-1] > bb['middle'].iloc[-1]
        assert bb['middle'].iloc[-1] > bb['lower'].iloc[-1]
    
    def test_calculate_atr(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de ATR"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        atr = analyzer.calculate_atr(sample_dataframe, 14)
        
        assert isinstance(atr, pd.Series)
        assert len(atr) == len(sample_dataframe)
        assert atr.iloc[-1] > 0  # ATR deve ser positivo
    
    def test_calculate_adx(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de ADX"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        adx = analyzer.calculate_adx(sample_dataframe)
        
        assert 'adx' in adx
        assert 'di_plus' in adx
        assert 'di_minus' in adx
        assert isinstance(adx['adx'], pd.Series)
    
    def test_calculate_stochastic(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa cálculo de Estocástico"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        stoch = analyzer.calculate_stochastic(sample_dataframe)
        
        assert 'k' in stoch
        assert 'd' in stoch
        
        # K e D devem estar entre 0 e 100
        assert 0 <= stoch['k'].iloc[-1] <= 100
        assert 0 <= stoch['d'].iloc[-1] <= 100
    
    def test_detect_candlestick_patterns_doji(self, mock_mt5_connector, mock_config):
        """Testa detecção de padrão Doji"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Criar DataFrame com Doji
        df = pd.DataFrame({
            'Open': [100.0, 100.5, 101.0],
            'High': [101.0, 101.5, 102.0],
            'Low': [99.0, 99.5, 100.0],
            'Close': [100.5, 100.4, 101.05],  # Última é Doji
            'Volume': [1000, 1000, 1000]
        })
        
        patterns = analyzer.detect_candlestick_patterns(df)
        
        assert 'doji' in patterns
        assert isinstance(patterns['doji'], bool)
    
    def test_detect_candlestick_patterns_engulfing(self, mock_mt5_connector, mock_config):
        """Testa detecção de padrões Engulfing"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Criar DataFrame com Engulfing Bullish
        df = pd.DataFrame({
            'Open': [102.0, 100.0, 99.0],
            'High': [102.5, 100.5, 103.0],
            'Low': [99.5, 99.0, 98.5],
            'Close': [100.0, 99.5, 102.5],  # Última engole anterior
            'Volume': [1000, 1000, 1000]
        })
        
        patterns = analyzer.detect_candlestick_patterns(df)
        
        assert 'engulfing_bullish' in patterns
        assert 'engulfing_bearish' in patterns
    
    def test_analyze_trend_bullish(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa análise de tendência de alta"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Criar indicadores que apontam alta
        indicators = {
            'current_price': 2050.0,
            'ema': {'ema_9': 2045.0, 'ema_21': 2040.0, 'ema_50': 2030.0},
            'rsi': 65.0,
            'macd': {'macd': 5.0, 'signal': 3.0, 'histogram': 2.0},
            'adx': {'adx': 30.0, 'di_plus': 30.0, 'di_minus': 20.0},
            'bollinger': {'upper': 2060.0, 'middle': 2045.0, 'lower': 2030.0}
        }
        
        trend = analyzer._analyze_trend(sample_dataframe, indicators)
        
        assert 'direction' in trend
        assert 'strength' in trend
        assert 'signals' in trend
        assert trend['direction'] in ['bullish', 'bearish', 'neutral']
    
    def test_get_market_data_caching(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa sistema de cache de dados"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Configurar mock para retornar dados
        mock_mt5_connector.get_rates = Mock(return_value=sample_dataframe.reset_index().to_dict('records'))
        
        # Primeira chamada - deve buscar dados
        df1 = analyzer.get_market_data('M5', 100)
        assert df1 is not None
        
        # Segunda chamada - deve usar cache
        df2 = analyzer.get_market_data('M5', 100)
        assert df2 is not None
        
        # Deve ter chamado get_rates apenas uma vez devido ao cache
        assert mock_mt5_connector.get_rates.call_count == 1
    
    def test_clear_cache(self, mock_mt5_connector, mock_config):
        """Testa limpeza do cache"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        analyzer._cache['test'] = {'data': 'test'}
        assert len(analyzer._cache) > 0
        
        analyzer.clear_cache()
        assert len(analyzer._cache) == 0
    
    def test_analyze_timeframe(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa análise completa de timeframe"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Mock get_market_data
        analyzer.get_market_data = Mock(return_value=sample_dataframe)
        
        result = analyzer.analyze_timeframe('M5')
        
        assert result is not None
        assert 'timeframe' in result
        assert result['timeframe'] == 'M5'
        assert 'current_price' in result
        assert 'ema' in result
        assert 'rsi' in result
        assert 'macd' in result
        assert 'bollinger' in result
        assert 'atr' in result
        assert 'trend' in result
    
    def test_analyze_multi_timeframe(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa análise multi-timeframe"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Mock get_market_data
        analyzer.get_market_data = Mock(return_value=sample_dataframe)
        
        result = analyzer.analyze_multi_timeframe(['M5', 'M15'])
        
        assert 'M5' in result
        assert 'M15' in result
        assert 'consensus' in result
        
        consensus = result['consensus']
        assert 'direction' in consensus
        assert 'strength' in consensus
        assert 'agreement' in consensus
    
    def test_calculate_consensus(self, mock_mt5_connector, mock_config):
        """Testa cálculo de consenso"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Análises mock
        analyses = {
            'M5': {'trend': {'direction': 'bullish', 'strength': 0.8}},
            'M15': {'trend': {'direction': 'bullish', 'strength': 0.7}},
            'H1': {'trend': {'direction': 'neutral', 'strength': 0.5}}
        }
        
        consensus = analyzer._calculate_consensus(analyses)
        
        assert consensus['direction'] == 'bullish'
        assert consensus['strength'] > 0
        assert consensus['agreement'] > 0
        assert consensus['bullish_count'] == 2
    
    def test_get_signal_buy(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa geração de sinal de compra"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Mock análise que retorna sinal de compra
        mock_analysis = {
            'M5': {'trend': {'direction': 'bullish', 'strength': 0.8}},
            'M15': {'trend': {'direction': 'bullish', 'strength': 0.75}},
            'H1': {'trend': {'direction': 'bullish', 'strength': 0.7}},
            'consensus': {
                'direction': 'bullish',
                'strength': 0.75,
                'agreement': 1.0
            }
        }
        
        analyzer.analyze_multi_timeframe = Mock(return_value=mock_analysis)
        
        signal = analyzer.get_signal('M5')
        
        assert signal is not None
        assert signal['action'] == 'BUY'
        assert signal['confidence'] > 0.6
    
    def test_get_signal_sell(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa geração de sinal de venda"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Mock análise que retorna sinal de venda
        mock_analysis = {
            'M5': {'trend': {'direction': 'bearish', 'strength': 0.8}},
            'M15': {'trend': {'direction': 'bearish', 'strength': 0.75}},
            'H1': {'trend': {'direction': 'bearish', 'strength': 0.7}},
            'consensus': {
                'direction': 'bearish',
                'strength': 0.75,
                'agreement': 1.0
            }
        }
        
        analyzer.analyze_multi_timeframe = Mock(return_value=mock_analysis)
        
        signal = analyzer.get_signal('M5')
        
        assert signal is not None
        assert signal['action'] == 'SELL'
        assert signal['confidence'] > 0.6
    
    def test_get_signal_hold(self, mock_mt5_connector, mock_config, sample_dataframe):
        """Testa geração de sinal HOLD"""
        analyzer = TechnicalAnalyzer(mock_mt5_connector, mock_config)
        
        # Mock análise que retorna sinal neutro
        mock_analysis = {
            'M5': {'trend': {'direction': 'neutral', 'strength': 0.5}},
            'M15': {'trend': {'direction': 'bullish', 'strength': 0.4}},
            'H1': {'trend': {'direction': 'bearish', 'strength': 0.4}},
            'consensus': {
                'direction': 'neutral',
                'strength': 0.43,
                'agreement': 0.33
            }
        }
        
        analyzer.analyze_multi_timeframe = Mock(return_value=mock_analysis)
        
        signal = analyzer.get_signal('M5')
        
        assert signal is not None
        assert signal['action'] == 'HOLD'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
