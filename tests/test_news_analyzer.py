"""
Testes para o módulo de Análise de Notícias
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Adicionar diretório src ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis.news_analyzer import NewsAnalyzer


@pytest.fixture
def mock_config():
    """Configuração mock para testes"""
    return {
        'news': {
            'forexnews_api_key': 'test_forex_key',
            'finazon_api_key': 'test_finazon_key',
            'fmp_api_key': 'test_fmp_key'
        }
    }


@pytest.fixture
def sample_forex_news():
    """Notícias de exemplo do ForexNewsAPI"""
    return {
        'data': [
            {
                'title': 'Gold prices surge on inflation concerns',
                'description': 'Rising inflation pushes investors to safe haven',
                'url': 'https://example.com/news1',
                'date': '2024-01-15 10:00:00'
            },
            {
                'title': 'Fed announces interest rate decision',
                'description': 'Federal Reserve keeps rates unchanged',
                'url': 'https://example.com/news2',
                'date': '2024-01-15 09:00:00'
            }
        ]
    }


@pytest.fixture
def sample_economic_events():
    """Eventos econômicos de exemplo"""
    return [
        {
            'event': 'Non-Farm Payrolls',
            'country': 'United States',
            'date': (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
            'impact': 'high',
            'currency': 'USD',
            'estimate': '200K',
            'previous': '195K'
        },
        {
            'event': 'CPI m/m',
            'country': 'United States',
            'date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'impact': 'high',
            'currency': 'USD',
            'estimate': '0.3%',
            'previous': '0.2%'
        }
    ]


class TestNewsAnalyzer:
    """Testes para NewsAnalyzer"""
    
    def test_initialization(self, mock_config):
        """Testa inicialização do analisador"""
        analyzer = NewsAnalyzer(mock_config)
        
        assert analyzer.config == mock_config
        assert analyzer.forexnews_key == 'test_forex_key'
        assert analyzer.finazon_key == 'test_finazon_key'
        assert analyzer.fmp_key == 'test_fmp_key'
        assert analyzer._news_cache == []
        assert analyzer._events_cache == []
    
    def test_is_gold_relevant(self, mock_config):
        """Testa detecção de relevância para GOLD"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Textos relevantes
        assert analyzer._is_gold_relevant("Gold prices rise on inflation")
        assert analyzer._is_gold_relevant("Fed raises interest rates")
        assert analyzer._is_gold_relevant("XAU/USD analysis")
        assert analyzer._is_gold_relevant("Dollar weakens against precious metals")
        
        # Textos não relevantes
        assert not analyzer._is_gold_relevant("Tesla stock surges")
        assert not analyzer._is_gold_relevant("Bitcoin reaches new high")
    
    def test_calculate_relevance(self, mock_config):
        """Testa cálculo de relevância"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Texto com múltiplas palavras-chave
        high_relevance = analyzer._calculate_relevance(
            "Gold prices surge as Fed raises interest rates amid inflation concerns"
        )
        assert high_relevance > 0.5
        
        # Texto com poucas palavras-chave
        low_relevance = analyzer._calculate_relevance(
            "Market analysis shows mixed signals"
        )
        assert low_relevance < 0.5
    
    @patch('src.analysis.news_analyzer.TextBlob')
    def test_analyze_sentiment_positive(self, mock_textblob, mock_config):
        """Testa análise de sentimento positivo"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock do TextBlob
        mock_blob = MagicMock()
        mock_blob.sentiment.polarity = 0.8
        mock_blob.sentiment.subjectivity = 0.6
        mock_textblob.return_value = mock_blob
        
        sentiment = analyzer.analyze_sentiment("Great news! Gold prices soar!")
        
        assert sentiment['polarity'] == 0.8
        assert sentiment['subjectivity'] == 0.6
        assert sentiment['method'] == 'textblob'
    
    @patch('src.analysis.news_analyzer.TextBlob')
    def test_analyze_sentiment_negative(self, mock_textblob, mock_config):
        """Testa análise de sentimento negativo"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock do TextBlob
        mock_blob = MagicMock()
        mock_blob.sentiment.polarity = -0.7
        mock_blob.sentiment.subjectivity = 0.5
        mock_textblob.return_value = mock_blob
        
        sentiment = analyzer.analyze_sentiment("Terrible news for gold market")
        
        assert sentiment['polarity'] == -0.7
        assert sentiment['method'] == 'textblob'
    
    @patch('requests.get')
    def test_fetch_forex_news(self, mock_get, mock_config, sample_forex_news):
        """Testa busca de notícias do ForexNewsAPI"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock da resposta
        mock_response = Mock()
        mock_response.json.return_value = sample_forex_news
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        news = analyzer.fetch_forex_news(limit=10)
        
        assert len(news) == 2
        assert news[0]['source'] == 'ForexNewsAPI'
        assert 'gold' in news[0]['title'].lower() or 'gold' in news[0]['description'].lower()
        assert 'relevance' in news[0]
    
    @patch('requests.get')
    def test_fetch_forex_news_error(self, mock_get, mock_config):
        """Testa tratamento de erro ao buscar ForexNewsAPI"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock de erro
        mock_get.side_effect = Exception("API Error")
        
        news = analyzer.fetch_forex_news()
        
        assert news == []
    
    @patch('requests.get')
    def test_fetch_economic_calendar(self, mock_get, mock_config, sample_economic_events):
        """Testa busca de calendário econômico"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock da resposta
        mock_response = Mock()
        mock_response.json.return_value = sample_economic_events
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        events = analyzer.fetch_economic_calendar(days=1)
        
        assert len(events) > 0
        assert events[0]['source'] == 'FMP'
        assert 'impact' in events[0]
    
    @patch('requests.get')
    def test_fetch_economic_calendar_caching(self, mock_get, mock_config, sample_economic_events):
        """Testa cache do calendário econômico"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock da resposta
        mock_response = Mock()
        mock_response.json.return_value = sample_economic_events
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Primeira chamada - busca da API
        events1 = analyzer.fetch_economic_calendar(days=1)
        
        # Segunda chamada - deve usar cache
        events2 = analyzer.fetch_economic_calendar(days=1)
        
        # Deve ter chamado a API apenas uma vez
        assert mock_get.call_count == 1
        assert events1 == events2
    
    @patch('requests.get')
    def test_get_aggregated_news(self, mock_get, mock_config, sample_forex_news):
        """Testa agregação de notícias"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock das respostas
        mock_response = Mock()
        mock_response.json.return_value = sample_forex_news
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        news = analyzer.get_aggregated_news(max_age_hours=24)
        
        assert len(news) > 0
        assert all('source' in n for n in news)
        assert all('relevance' in n for n in news)
    
    @patch('requests.get')
    @patch('src.analysis.news_analyzer.TextBlob')
    def test_get_sentiment_summary(self, mock_textblob, mock_get, 
                                   mock_config, sample_forex_news):
        """Testa resumo de sentimento"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock das notícias
        mock_response = Mock()
        mock_response.json.return_value = sample_forex_news
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock do sentimento
        mock_blob = MagicMock()
        mock_blob.sentiment.polarity = 0.5
        mock_blob.sentiment.subjectivity = 0.6
        mock_textblob.return_value = mock_blob
        
        summary = analyzer.get_sentiment_summary(max_news=10)
        
        assert 'overall_sentiment' in summary
        assert summary['overall_sentiment'] in ['bullish', 'bearish', 'neutral']
        assert 'polarity_avg' in summary
        assert 'bullish_count' in summary
        assert 'bearish_count' in summary
        assert 'neutral_count' in summary
        assert 'total_analyzed' in summary
    
    @patch('requests.get')
    def test_is_news_blocking_window_active(self, mock_get, mock_config):
        """Testa detecção de janela de bloqueio ativa"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Evento acontecendo AGORA
        events = [
            {
                'event': 'NFP',
                'country': 'United States',
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'impact': 'high',
                'currency': 'USD'
            }
        ]
        
        mock_response = Mock()
        mock_response.json.return_value = events
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        is_blocking, event = analyzer.is_news_blocking_window(buffer_minutes=15)
        
        assert is_blocking is True
        assert event is not None
    
    @patch('requests.get')
    def test_is_news_blocking_window_inactive(self, mock_get, mock_config):
        """Testa janela de bloqueio inativa"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Evento daqui a 2 horas
        events = [
            {
                'event': 'NFP',
                'country': 'United States',
                'date': (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'impact': 'high',
                'currency': 'USD'
            }
        ]
        
        mock_response = Mock()
        mock_response.json.return_value = events
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        is_blocking, event = analyzer.is_news_blocking_window(buffer_minutes=15)
        
        assert is_blocking is False
        assert event is None
    
    @patch('requests.get')
    @patch('src.analysis.news_analyzer.TextBlob')
    def test_get_news_signal_bullish(self, mock_textblob, mock_get, 
                                     mock_config, sample_forex_news):
        """Testa geração de sinal bullish"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock das notícias
        mock_response = Mock()
        mock_response.json.return_value = sample_forex_news
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock de sentimento positivo
        mock_blob = MagicMock()
        mock_blob.sentiment.polarity = 0.7
        mock_blob.sentiment.subjectivity = 0.6
        mock_textblob.return_value = mock_blob
        
        signal = analyzer.get_news_signal()
        
        assert 'action' in signal
        assert signal['action'] in ['BULLISH', 'BEARISH', 'HOLD', 'BLOCK']
        assert 'confidence' in signal
        assert 0 <= signal['confidence'] <= 1
    
    @patch('requests.get')
    def test_get_news_signal_blocking(self, mock_get, mock_config):
        """Testa sinal de bloqueio durante evento"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Evento acontecendo agora
        events = [
            {
                'event': 'NFP',
                'country': 'United States',
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'impact': 'high',
                'currency': 'USD'
            }
        ]
        
        mock_response = Mock()
        mock_response.json.return_value = events
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        signal = analyzer.get_news_signal()
        
        assert signal['action'] == 'BLOCK'
        assert signal['reason'] == 'high_impact_event'
        assert signal['confidence'] == 1.0
    
    @patch('requests.get')
    def test_get_top_news(self, mock_get, mock_config, sample_forex_news):
        """Testa busca de top notícias"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Mock das notícias
        mock_response = Mock()
        mock_response.json.return_value = sample_forex_news
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        top_news = analyzer.get_top_news(limit=5)
        
        assert len(top_news) <= 5
        assert all('sentiment' in n for n in top_news)
    
    def test_clear_cache(self, mock_config):
        """Testa limpeza de cache"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Adicionar dados ao cache
        analyzer._news_cache = [{'test': 'data'}]
        analyzer._cache_timestamp = datetime.now()
        analyzer._events_cache = [{'test': 'event'}]
        analyzer._events_cache_timestamp = datetime.now()
        
        # Limpar cache
        analyzer.clear_cache()
        
        assert analyzer._news_cache == []
        assert analyzer._cache_timestamp is None
        assert analyzer._events_cache == []
        assert analyzer._events_cache_timestamp is None
    
    def test_is_cache_valid(self, mock_config):
        """Testa validação de cache"""
        analyzer = NewsAnalyzer(mock_config)
        
        # Cache recente - válido
        recent = datetime.now() - timedelta(seconds=30)
        assert analyzer._is_cache_valid(recent, timedelta(minutes=1)) is True
        
        # Cache antigo - inválido
        old = datetime.now() - timedelta(minutes=10)
        assert analyzer._is_cache_valid(old, timedelta(minutes=1)) is False
        
        # Cache None - inválido
        assert analyzer._is_cache_valid(None, timedelta(minutes=1)) is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
