"""
Multi-Source Data Provider - Agregador de APIs para Urion Trading Bot
=====================================================================
Integra múltiplas fontes de dados para maximizar informações disponíveis:
- Alpha Vantage (indicadores técnicos)
- FRED (dados macro do Federal Reserve)
- Fear & Greed Index (sentiment)
- COT Data (posições institucionais)
- NewsAPI (notícias globais)
"""

import requests
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import json
import os
from functools import lru_cache
import threading


class DataSource(Enum):
    """Fontes de dados disponíveis"""
    ALPHA_VANTAGE = "alphavantage"
    FRED = "fred"
    FEAR_GREED = "fear_greed"
    COT = "cot"
    NEWS_API = "newsapi"
    VIX = "vix"


@dataclass
class MarketData:
    """Dados de mercado agregados"""
    timestamp: datetime
    source: str
    data_type: str
    value: Any
    metadata: Dict = field(default_factory=dict)


@dataclass
class MacroIndicator:
    """Indicador macroeconômico"""
    name: str
    value: float
    previous: float
    change_pct: float
    date: str
    source: str
    impact_on_gold: str  # 'bullish', 'bearish', 'neutral'


@dataclass
class SentimentData:
    """Dados de sentiment"""
    fear_greed_score: int
    fear_greed_rating: str
    vix: float
    put_call_ratio: float
    gold_etf_flows: float
    interpretation: str
    gold_bias: str  # 'bullish', 'bearish', 'neutral'


class MultiSourceDataProvider:
    """
    Agregador de múltiplas APIs para dados de trading
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.apis_config = config.get('apis', config.get('news', {}))
        
        # API Keys
        self.alphavantage_key = self.apis_config.get('alphavantage_api_key', '')
        self.fred_key = self.apis_config.get('fred_api_key', '')
        self.newsapi_key = self.apis_config.get('newsapi_api_key', '')
        self.quandl_key = self.apis_config.get('quandl_api_key', '')
        
        # Configurações
        self.timeout = self.apis_config.get('api_timeout', 10)
        self.retry_count = self.apis_config.get('api_retry_count', 3)
        
        # Cache
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._cache_duration = timedelta(minutes=self.apis_config.get('cache_duration_minutes', 5))
        self._lock = threading.Lock()
        
        # Rate limiting
        self._last_call: Dict[str, datetime] = {}
        self._rate_limits = {
            'alphavantage': 12,  # 5 calls/min = 12s between calls
            'fred': 1,
            'newsapi': 1,
            'fear_greed': 60
        }
        
        logger.info("MultiSourceDataProvider inicializado")
        self._log_available_apis()
    
    def _log_available_apis(self):
        """Log das APIs disponíveis"""
        apis = {
            'Alpha Vantage': bool(self.alphavantage_key),
            'FRED': bool(self.fred_key),
            'NewsAPI': bool(self.newsapi_key),
            'Quandl': bool(self.quandl_key),
            'Fear & Greed': True,  # Não precisa de key
            'VIX': True
        }
        
        available = [k for k, v in apis.items() if v]
        missing = [k for k, v in apis.items() if not v]
        
        logger.info(f"APIs disponíveis: {', '.join(available)}")
        if missing:
            logger.warning(f"APIs sem key: {', '.join(missing)}")
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Retorna valor do cache se válido"""
        with self._lock:
            if key in self._cache:
                timestamp, value = self._cache[key]
                if datetime.now() - timestamp < self._cache_duration:
                    return value
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Armazena valor no cache"""
        with self._lock:
            self._cache[key] = (datetime.now(), value)
    
    def _rate_limit(self, api: str):
        """Aplica rate limiting"""
        if api in self._last_call:
            elapsed = (datetime.now() - self._last_call[api]).total_seconds()
            wait_time = self._rate_limits.get(api, 1) - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
        self._last_call[api] = datetime.now()
    
    def _request(self, url: str, params: Dict = None, api_name: str = None) -> Optional[Dict]:
        """Faz request com retry e tratamento de erros"""
        for attempt in range(self.retry_count):
            try:
                if api_name:
                    self._rate_limit(api_name)
                
                response = requests.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    logger.warning(f"{api_name}: Rate limit, aguardando...")
                    time.sleep(60)
                else:
                    logger.warning(f"{api_name}: Status {response.status_code}")
                    
            except requests.Timeout:
                logger.warning(f"{api_name}: Timeout (tentativa {attempt + 1})")
            except requests.ConnectionError:
                logger.warning(f"{api_name}: Erro de conexão")
            except Exception as e:
                logger.error(f"{api_name}: Erro - {e}")
        
        return None
    
    # ==================== ALPHA VANTAGE ====================
    
    def get_forex_quote(self, from_currency: str = "XAU", to_currency: str = "USD") -> Optional[Dict]:
        """
        Obtém cotação Forex em tempo real
        """
        cache_key = f"av_quote_{from_currency}_{to_currency}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.alphavantage_key:
            return None
        
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'CURRENCY_EXCHANGE_RATE',
            'from_currency': from_currency,
            'to_currency': to_currency,
            'apikey': self.alphavantage_key
        }
        
        data = self._request(url, params, 'alphavantage')
        if data and 'Realtime Currency Exchange Rate' in data:
            result = {
                'rate': float(data['Realtime Currency Exchange Rate'].get('5. Exchange Rate', 0)),
                'bid': float(data['Realtime Currency Exchange Rate'].get('8. Bid Price', 0)),
                'ask': float(data['Realtime Currency Exchange Rate'].get('9. Ask Price', 0)),
                'timestamp': data['Realtime Currency Exchange Rate'].get('6. Last Refreshed', '')
            }
            self._set_cache(cache_key, result)
            return result
        
        return None
    
    def get_technical_indicator(self, indicator: str, symbol: str = "XAUUSD", 
                                interval: str = "60min", period: int = 14) -> Optional[Dict]:
        """
        Obtém indicador técnico calculado pela Alpha Vantage
        Indicadores: RSI, MACD, SMA, EMA, BBANDS, ADX, ATR, etc.
        """
        cache_key = f"av_{indicator}_{symbol}_{interval}_{period}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.alphavantage_key:
            return None
        
        url = "https://www.alphavantage.co/query"
        params = {
            'function': indicator.upper(),
            'symbol': symbol,
            'interval': interval,
            'time_period': period,
            'series_type': 'close',
            'apikey': self.alphavantage_key
        }
        
        # MACD tem parâmetros diferentes
        if indicator.upper() == 'MACD':
            params.pop('time_period', None)
        
        data = self._request(url, params, 'alphavantage')
        if data:
            # Pegar o último valor
            key = f"Technical Analysis: {indicator.upper()}"
            if key in data:
                values = list(data[key].values())
                if values:
                    result = {
                        'indicator': indicator,
                        'value': values[0],
                        'symbol': symbol,
                        'interval': interval,
                        'timestamp': list(data[key].keys())[0]
                    }
                    self._set_cache(cache_key, result)
                    return result
        
        return None
    
    def get_rsi(self, symbol: str = "XAUUSD", interval: str = "60min", period: int = 14) -> Optional[float]:
        """RSI atual"""
        data = self.get_technical_indicator('RSI', symbol, interval, period)
        if data:
            return float(data['value'].get('RSI', 50))
        return None
    
    def get_macd(self, symbol: str = "XAUUSD", interval: str = "60min") -> Optional[Dict]:
        """MACD atual"""
        data = self.get_technical_indicator('MACD', symbol, interval)
        if data:
            return {
                'macd': float(data['value'].get('MACD', 0)),
                'signal': float(data['value'].get('MACD_Signal', 0)),
                'histogram': float(data['value'].get('MACD_Hist', 0))
            }
        return None
    
    # ==================== FRED ====================
    
    def get_fred_series(self, series_id: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Obtém série de dados do FRED
        Séries úteis:
        - FEDFUNDS: Taxa de juros do Fed
        - CPIAUCSL: CPI (inflação)
        - DGS10: Treasury 10 anos
        - DGS2: Treasury 2 anos
        - DTWEXBGS: Índice do Dólar
        - UNRATE: Taxa de desemprego
        """
        cache_key = f"fred_{series_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.fred_key:
            return None
        
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': self.fred_key,
            'file_type': 'json',
            'limit': limit,
            'sort_order': 'desc'
        }
        
        data = self._request(url, params, 'fred')
        if data and 'observations' in data:
            result = data['observations']
            self._set_cache(cache_key, result)
            return result
        
        return None
    
    def get_fed_funds_rate(self) -> Optional[MacroIndicator]:
        """Taxa de juros do Federal Reserve"""
        data = self.get_fred_series('FEDFUNDS', 2)
        if data and len(data) >= 2:
            current = float(data[0]['value'])
            previous = float(data[1]['value'])
            change = ((current - previous) / previous * 100) if previous else 0
            
            # Juros subindo = bearish para ouro (dólar fortalece)
            # Juros caindo = bullish para ouro
            impact = 'bearish' if current > previous else 'bullish' if current < previous else 'neutral'
            
            return MacroIndicator(
                name='Fed Funds Rate',
                value=current,
                previous=previous,
                change_pct=change,
                date=data[0]['date'],
                source='FRED',
                impact_on_gold=impact
            )
        return None
    
    def get_inflation_cpi(self) -> Optional[MacroIndicator]:
        """CPI - Índice de Preços ao Consumidor"""
        data = self.get_fred_series('CPIAUCSL', 2)
        if data and len(data) >= 2:
            current = float(data[0]['value'])
            previous = float(data[1]['value'])
            change = ((current - previous) / previous * 100) if previous else 0
            
            # Inflação alta = bullish para ouro (hedge)
            impact = 'bullish' if current > previous else 'bearish'
            
            return MacroIndicator(
                name='CPI (Inflation)',
                value=current,
                previous=previous,
                change_pct=change,
                date=data[0]['date'],
                source='FRED',
                impact_on_gold=impact
            )
        return None
    
    def get_treasury_10y(self) -> Optional[MacroIndicator]:
        """Treasury 10 anos - yield"""
        data = self.get_fred_series('DGS10', 2)
        if data and len(data) >= 2:
            current = float(data[0]['value']) if data[0]['value'] != '.' else 0
            previous = float(data[1]['value']) if data[1]['value'] != '.' else 0
            change = ((current - previous) / previous * 100) if previous else 0
            
            # Yields subindo = bearish para ouro (oportunidade de custo maior)
            impact = 'bearish' if current > previous else 'bullish'
            
            return MacroIndicator(
                name='Treasury 10Y Yield',
                value=current,
                previous=previous,
                change_pct=change,
                date=data[0]['date'],
                source='FRED',
                impact_on_gold=impact
            )
        return None
    
    def get_dollar_index(self) -> Optional[MacroIndicator]:
        """Índice do Dólar (DXY aproximado)"""
        data = self.get_fred_series('DTWEXBGS', 2)
        if data and len(data) >= 2:
            current = float(data[0]['value']) if data[0]['value'] != '.' else 0
            previous = float(data[1]['value']) if data[1]['value'] != '.' else 0
            change = ((current - previous) / previous * 100) if previous else 0
            
            # Dólar forte = bearish para ouro (correlação inversa)
            impact = 'bearish' if current > previous else 'bullish'
            
            return MacroIndicator(
                name='Dollar Index',
                value=current,
                previous=previous,
                change_pct=change,
                date=data[0]['date'],
                source='FRED',
                impact_on_gold=impact
            )
        return None
    
    # ==================== FEAR & GREED ====================
    
    def get_fear_greed_index(self) -> Optional[Dict]:
        """
        CNN Fear & Greed Index
        0-25: Extreme Fear (bullish para ouro - safe haven)
        25-45: Fear
        45-55: Neutral
        55-75: Greed
        75-100: Extreme Greed (bearish para ouro - risk on)
        """
        cache_key = "fear_greed"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.cnn.com/'
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                score = data.get('fear_and_greed', {}).get('score', 50)
                rating = data.get('fear_and_greed', {}).get('rating', 'Neutral')
                
                # Determinar viés para ouro
                if score <= 25:
                    gold_bias = 'bullish'
                    interpretation = 'Extreme Fear - Safe haven demand HIGH'
                elif score <= 45:
                    gold_bias = 'slightly_bullish'
                    interpretation = 'Fear - Some safe haven demand'
                elif score <= 55:
                    gold_bias = 'neutral'
                    interpretation = 'Neutral - No clear bias'
                elif score <= 75:
                    gold_bias = 'slightly_bearish'
                    interpretation = 'Greed - Risk-on sentiment'
                else:
                    gold_bias = 'bearish'
                    interpretation = 'Extreme Greed - Risk-on, gold may fall'
                
                result = {
                    'score': score,
                    'rating': rating,
                    'gold_bias': gold_bias,
                    'interpretation': interpretation,
                    'timestamp': datetime.now().isoformat()
                }
                
                self._set_cache(cache_key, result)
                return result
                
        except Exception as e:
            logger.error(f"Fear & Greed API error: {e}")
        
        return None
    
    # ==================== VIX ====================
    
    def get_vix(self) -> Optional[Dict]:
        """
        VIX - Índice de Volatilidade
        VIX alto (>30) = bullish para ouro (medo no mercado)
        VIX baixo (<15) = bearish para ouro (complacência)
        """
        cache_key = "vix"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Usar Alpha Vantage para VIX
        if not self.alphavantage_key:
            return None
        
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': 'VIX',
            'apikey': self.alphavantage_key
        }
        
        data = self._request(url, params, 'alphavantage')
        if data and 'Time Series (Daily)' in data:
            dates = list(data['Time Series (Daily)'].keys())
            if dates:
                latest = data['Time Series (Daily)'][dates[0]]
                vix_value = float(latest['4. close'])
                
                if vix_value > 30:
                    gold_bias = 'bullish'
                    interpretation = 'High VIX - Fear in markets, gold safe haven'
                elif vix_value > 20:
                    gold_bias = 'slightly_bullish'
                    interpretation = 'Elevated VIX - Some uncertainty'
                elif vix_value > 15:
                    gold_bias = 'neutral'
                    interpretation = 'Normal VIX - Neutral sentiment'
                else:
                    gold_bias = 'bearish'
                    interpretation = 'Low VIX - Complacency, risk-on'
                
                result = {
                    'value': vix_value,
                    'date': dates[0],
                    'gold_bias': gold_bias,
                    'interpretation': interpretation
                }
                
                self._set_cache(cache_key, result)
                return result
        
        return None
    
    # ==================== NEWS API ====================
    
    def get_gold_news(self, limit: int = 20) -> List[Dict]:
        """
        Busca notícias sobre ouro de múltiplas fontes
        """
        cache_key = f"newsapi_gold_{limit}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.newsapi_key:
            return []
        
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': 'gold price OR XAUUSD OR gold trading OR federal reserve gold',
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': limit,
            'apiKey': self.newsapi_key
        }
        
        data = self._request(url, params, 'newsapi')
        if data and 'articles' in data:
            articles = []
            for article in data['articles']:
                articles.append({
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'title': article.get('title', ''),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'published_at': article.get('publishedAt', ''),
                    'sentiment': self._analyze_sentiment(
                        article.get('title', '') + ' ' + article.get('description', '')
                    )
                })
            
            self._set_cache(cache_key, articles)
            return articles
        
        return []
    
    def _analyze_sentiment(self, text: str) -> str:
        """Análise de sentimento simples"""
        text_lower = text.lower()
        
        bullish_words = ['surge', 'rally', 'rise', 'gain', 'bullish', 'buy', 
                        'support', 'breakout', 'inflation', 'fear', 'crisis']
        bearish_words = ['fall', 'drop', 'decline', 'bearish', 'sell', 
                        'resistance', 'rate hike', 'strong dollar']
        
        bullish_count = sum(1 for word in bullish_words if word in text_lower)
        bearish_count = sum(1 for word in bearish_words if word in text_lower)
        
        if bullish_count > bearish_count:
            return 'bullish'
        elif bearish_count > bullish_count:
            return 'bearish'
        return 'neutral'
    
    # ==================== AGREGAÇÃO ====================
    
    def get_complete_market_context(self) -> Dict:
        """
        Retorna contexto completo do mercado agregando todas as fontes
        """
        context = {
            'timestamp': datetime.now().isoformat(),
            'macro': {},
            'sentiment': {},
            'technical': {},
            'news': [],
            'overall_bias': 'neutral',
            'confidence': 0.0
        }
        
        # Macro indicadores
        try:
            fed_rate = self.get_fed_funds_rate()
            if fed_rate:
                context['macro']['fed_rate'] = {
                    'value': fed_rate.value,
                    'impact': fed_rate.impact_on_gold
                }
        except Exception as e:
            logger.error(f"Erro ao buscar Fed Rate: {e}")
        
        try:
            treasury = self.get_treasury_10y()
            if treasury:
                context['macro']['treasury_10y'] = {
                    'value': treasury.value,
                    'impact': treasury.impact_on_gold
                }
        except Exception as e:
            logger.error(f"Erro ao buscar Treasury: {e}")
        
        try:
            dollar = self.get_dollar_index()
            if dollar:
                context['macro']['dollar_index'] = {
                    'value': dollar.value,
                    'impact': dollar.impact_on_gold
                }
        except Exception as e:
            logger.error(f"Erro ao buscar Dollar Index: {e}")
        
        # Sentiment
        try:
            fear_greed = self.get_fear_greed_index()
            if fear_greed:
                context['sentiment']['fear_greed'] = fear_greed
        except Exception as e:
            logger.error(f"Erro ao buscar Fear & Greed: {e}")
        
        try:
            vix = self.get_vix()
            if vix:
                context['sentiment']['vix'] = vix
        except Exception as e:
            logger.error(f"Erro ao buscar VIX: {e}")
        
        # Technical (se disponível)
        try:
            rsi = self.get_rsi()
            if rsi:
                context['technical']['rsi'] = rsi
        except Exception as e:
            logger.error(f"Erro ao buscar RSI: {e}")
        
        try:
            macd = self.get_macd()
            if macd:
                context['technical']['macd'] = macd
        except Exception as e:
            logger.error(f"Erro ao buscar MACD: {e}")
        
        # News
        try:
            news = self.get_gold_news(10)
            context['news'] = news
        except Exception as e:
            logger.error(f"Erro ao buscar News: {e}")
        
        # Calcular viés geral
        context['overall_bias'], context['confidence'] = self._calculate_overall_bias(context)
        
        return context
    
    def _calculate_overall_bias(self, context: Dict) -> Tuple[str, float]:
        """Calcula viés geral baseado em todos os dados"""
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0
        
        # Macro
        for indicator in context.get('macro', {}).values():
            if isinstance(indicator, dict):
                impact = indicator.get('impact', 'neutral')
                if impact == 'bullish':
                    bullish_signals += 1
                elif impact == 'bearish':
                    bearish_signals += 1
                total_signals += 1
        
        # Sentiment
        for sentiment in context.get('sentiment', {}).values():
            if isinstance(sentiment, dict):
                bias = sentiment.get('gold_bias', 'neutral')
                if 'bullish' in bias:
                    bullish_signals += 1
                elif 'bearish' in bias:
                    bearish_signals += 1
                total_signals += 1
        
        # News sentiment
        for news in context.get('news', [])[:5]:
            if news.get('sentiment') == 'bullish':
                bullish_signals += 0.5
            elif news.get('sentiment') == 'bearish':
                bearish_signals += 0.5
            total_signals += 0.5
        
        if total_signals == 0:
            return 'neutral', 0.0
        
        bullish_pct = bullish_signals / total_signals
        bearish_pct = bearish_signals / total_signals
        
        if bullish_pct > 0.6:
            bias = 'bullish'
            confidence = bullish_pct
        elif bearish_pct > 0.6:
            bias = 'bearish'
            confidence = bearish_pct
        else:
            bias = 'neutral'
            confidence = 1 - abs(bullish_pct - bearish_pct)
        
        return bias, round(confidence, 2)


# Factory function
_provider_instance = None

def get_data_provider(config: Dict = None) -> MultiSourceDataProvider:
    """Retorna instância singleton do provider"""
    global _provider_instance
    if _provider_instance is None and config:
        _provider_instance = MultiSourceDataProvider(config)
    return _provider_instance
