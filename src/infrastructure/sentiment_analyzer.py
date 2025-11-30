# -*- coding: utf-8 -*-
"""
Sentiment Analyzer
==================
Analisador de sentimento usando NLTK.
"""

from typing import Dict, List, Optional
from loguru import logger

try:
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    SentimentIntensityAnalyzer = None


class SentimentAnalyzer:
    """
    Analisador de sentimento para notícias e textos.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._analyzer = None
        self._initialized = False
        
        self._initialize()
    
    def _initialize(self):
        """Inicializa o analisador"""
        if not NLTK_AVAILABLE:
            logger.warning("NLTK não disponível. Instale: pip install nltk")
            return
        
        try:
            # Baixar recursos necessários
            nltk.download('vader_lexicon', quiet=True)
            nltk.download('punkt', quiet=True)
            
            self._analyzer = SentimentIntensityAnalyzer()
            self._initialized = True
            
            logger.info("SentimentAnalyzer inicializado")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar NLTK: {e}")
    
    def analyze(self, text: str) -> Dict:
        """
        Analisa sentimento de um texto.
        
        Retorna:
            - compound: Score geral (-1 a 1)
            - positive: Score positivo (0 a 1)
            - negative: Score negativo (0 a 1)
            - neutral: Score neutro (0 a 1)
            - sentiment: 'bullish', 'bearish', ou 'neutral'
        """
        if not self._initialized or not self._analyzer:
            return {
                'compound': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 1,
                'sentiment': 'neutral'
            }
        
        try:
            scores = self._analyzer.polarity_scores(text)
            
            # Determinar sentimento
            compound = scores['compound']
            if compound >= 0.05:
                sentiment = 'bullish'
            elif compound <= -0.05:
                sentiment = 'bearish'
            else:
                sentiment = 'neutral'
            
            return {
                'compound': compound,
                'positive': scores['pos'],
                'negative': scores['neg'],
                'neutral': scores['neu'],
                'sentiment': sentiment
            }
            
        except Exception as e:
            logger.error(f"Erro na análise: {e}")
            return {
                'compound': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 1,
                'sentiment': 'neutral'
            }
    
    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """Analisa múltiplos textos"""
        return [self.analyze(text) for text in texts]
    
    def get_market_sentiment(self, headlines: List[str]) -> Dict:
        """
        Calcula sentimento agregado do mercado.
        """
        if not headlines:
            return {
                'overall': 'neutral',
                'score': 0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0
            }
        
        results = self.analyze_batch(headlines)
        
        bullish = sum(1 for r in results if r['sentiment'] == 'bullish')
        bearish = sum(1 for r in results if r['sentiment'] == 'bearish')
        neutral = len(results) - bullish - bearish
        
        avg_compound = sum(r['compound'] for r in results) / len(results)
        
        if avg_compound >= 0.1:
            overall = 'bullish'
        elif avg_compound <= -0.1:
            overall = 'bearish'
        else:
            overall = 'neutral'
        
        return {
            'overall': overall,
            'score': avg_compound,
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral
        }


# Singleton
_sentiment_analyzer = None

def get_sentiment_analyzer(config: Dict = None) -> SentimentAnalyzer:
    """Retorna instância singleton"""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer(config)
    return _sentiment_analyzer
