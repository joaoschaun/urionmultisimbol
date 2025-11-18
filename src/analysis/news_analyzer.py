"""
Módulo de Análise de Notícias
Integra múltiplas fontes de notícias e calendário econômico
Analisa sentimento e impacto no mercado
"""

import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pytz
from loguru import logger

# NLP para análise de sentimento
try:
    from textblob import TextBlob
except ImportError:
    logger.warning("TextBlob não instalado. Análise de sentimento limitada.")
    TextBlob = None


class NewsAnalyzer:
    """
    Analisador de notícias e eventos econômicos
    Integra com ForexNewsAPI, Finazon e Financial Modeling Prep
    """
    
    # Palavras-chave para GOLD/XAUUSD
    GOLD_KEYWORDS = [
        'gold', 'xau', 'precious metals', 'safe haven',
        'inflation', 'fed', 'interest rate', 'treasury',
        'dollar', 'usd', 'dxy', 'geopolitical', 'war',
        'central bank', 'monetary policy', 'recession'
    ]
    
    # Níveis de impacto
    IMPACT_HIGH = 'high'
    IMPACT_MEDIUM = 'medium'
    IMPACT_LOW = 'low'
    
    def __init__(self, config: Dict):
        """
        Inicializa o analisador de notícias
        
        Args:
            config: Configurações do sistema
        """
        self.config = config
        self.news_config = config.get('news', {})
        
        # API Keys
        self.forexnews_key = self.news_config.get('forexnews_api_key', '')
        self.finazon_key = self.news_config.get('finazon_api_key', '')
        self.fmp_key = self.news_config.get('fmp_api_key', '')
        
        # Cache de notícias
        self._news_cache: List[Dict] = []
        self._cache_timestamp: Optional[datetime] = None
        self._cache_timeout = timedelta(minutes=5)
        
        # Cache de eventos econômicos
        self._events_cache: List[Dict] = []
        self._events_cache_timestamp: Optional[datetime] = None
        self._events_cache_timeout = timedelta(hours=1)
        
        logger.info("NewsAnalyzer inicializado")
    
    def _is_cache_valid(self, timestamp: Optional[datetime], 
                       timeout: timedelta) -> bool:
        """Verifica se cache ainda é válido"""
        if timestamp is None:
            return False
        return datetime.now() - timestamp < timeout
    
    def fetch_forex_news(self, limit: int = 50) -> List[Dict]:
        """
        Busca notícias do ForexNewsAPI
        
        Args:
            limit: Número máximo de notícias
            
        Returns:
            Lista de notícias
        """
        try:
            if not self.forexnews_key:
                logger.warning("ForexNewsAPI key não configurada")
                return []
            
            url = "https://forexnewsapi.com/api/v1"
            params = {
                'token': self.forexnews_key,
                'section': 'forex,commodities,economy',
                'limit': limit,
                'page': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            news_list = data.get('data', [])
            
            # Filtrar notícias relevantes para GOLD
            filtered_news = []
            for news in news_list:
                if self._is_gold_relevant(news.get('title', '') + ' ' + 
                                         news.get('description', '')):
                    filtered_news.append({
                        'source': 'ForexNewsAPI',
                        'title': news.get('title', ''),
                        'description': news.get('description', ''),
                        'url': news.get('url', ''),
                        'published_at': news.get('date', ''),
                        'relevance': self._calculate_relevance(
                            news.get('title', '') + ' ' + 
                            news.get('description', '')
                        )
                    })
            
            logger.info(f"ForexNewsAPI: {len(filtered_news)} notícias relevantes")
            return filtered_news
            
        except Exception as e:
            logger.error(f"Erro ao buscar ForexNewsAPI: {e}")
            return []
    
    def fetch_finazon_news(self, limit: int = 50) -> List[Dict]:
        """
        Busca notícias do Finazon
        
        Args:
            limit: Número máximo de notícias
            
        Returns:
            Lista de notícias
        """
        try:
            if not self.finazon_key:
                logger.warning("Finazon API key não configurada")
                return []
            
            url = "https://api.finazon.io/latest/news"
            headers = {'Authorization': f'Bearer {self.finazon_key}'}
            params = {
                'ticker': 'XAUUSD',
                'page': 0,
                'page_size': limit
            }
            
            response = requests.get(url, headers=headers, 
                                  params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            news_list = data.get('data', [])
            
            filtered_news = []
            for news in news_list:
                filtered_news.append({
                    'source': 'Finazon',
                    'title': news.get('title', ''),
                    'description': news.get('description', ''),
                    'url': news.get('url', ''),
                    'published_at': news.get('published_at', ''),
                    'relevance': self._calculate_relevance(
                        news.get('title', '') + ' ' + 
                        news.get('description', '')
                    )
                })
            
            logger.info(f"Finazon: {len(filtered_news)} notícias")
            return filtered_news
            
        except Exception as e:
            logger.error(f"Erro ao buscar Finazon: {e}")
            return []
    
    def fetch_economic_calendar(self, days: int = 1) -> List[Dict]:
        """
        Busca eventos do calendário econômico (Financial Modeling Prep)
        
        Args:
            days: Número de dias para buscar
            
        Returns:
            Lista de eventos econômicos
        """
        try:
            if not self.fmp_key:
                logger.warning("FMP API key não configurada")
                return []
            
            # Verificar cache
            if self._is_cache_valid(self._events_cache_timestamp,
                                   self._events_cache_timeout):
                return self._events_cache
            
            url = "https://financialmodelingprep.com/api/v3/economic_calendar"
            params = {
                'apikey': self.fmp_key,
                'from': datetime.now().strftime('%Y-%m-%d'),
                'to': (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            events = response.json()
            
            # Filtrar eventos de alto impacto
            high_impact_events = []
            for event in events:
                impact = event.get('impact', '').lower()
                
                # Apenas eventos de médio/alto impacto
                if impact in ['high', 'medium']:
                    event_text = (event.get('event', '') + ' ' + 
                                event.get('country', ''))
                    
                    # Verificar relevância para GOLD
                    if self._is_gold_relevant(event_text) or \
                       event.get('country', '') in ['US', 'United States']:
                        high_impact_events.append({
                            'source': 'FMP',
                            'event': event.get('event', ''),
                            'country': event.get('country', ''),
                            'date': event.get('date', ''),
                            'impact': impact,
                            'currency': event.get('currency', ''),
                            'estimate': event.get('estimate', ''),
                            'previous': event.get('previous', ''),
                            'actual': event.get('actual', '')
                        })
            
            # Atualizar cache
            self._events_cache = high_impact_events
            self._events_cache_timestamp = datetime.now()
            
            logger.info(f"Calendário Econômico: {len(high_impact_events)} eventos")
            return high_impact_events
            
        except Exception as e:
            logger.error(f"Erro ao buscar calendário econômico: {e}")
            return []
    
    def _is_gold_relevant(self, text: str) -> bool:
        """
        Verifica se texto é relevante para GOLD/XAUUSD
        
        Args:
            text: Texto a analisar
            
        Returns:
            True se relevante
        """
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.GOLD_KEYWORDS)
    
    def _calculate_relevance(self, text: str) -> float:
        """
        Calcula relevância do texto para GOLD (0.0 a 1.0)
        
        Args:
            text: Texto a analisar
            
        Returns:
            Score de relevância
        """
        text_lower = text.lower()
        matches = sum(1 for keyword in self.GOLD_KEYWORDS 
                     if keyword in text_lower)
        
        # Normalizar: max 5 palavras-chave = relevância 1.0
        relevance = min(matches / 5.0, 1.0)
        return relevance
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analisa sentimento do texto usando TextBlob
        
        Args:
            text: Texto a analisar
            
        Returns:
            Dict com polarity (-1 a 1) e subjectivity (0 a 1)
        """
        if TextBlob is None:
            return {'polarity': 0.0, 'subjectivity': 0.5, 'method': 'none'}
        
        try:
            blob = TextBlob(text)
            return {
                'polarity': blob.sentiment.polarity,
                'subjectivity': blob.sentiment.subjectivity,
                'method': 'textblob'
            }
        except Exception as e:
            logger.error(f"Erro na análise de sentimento: {e}")
            return {'polarity': 0.0, 'subjectivity': 0.5, 'method': 'error'}
    
    def get_aggregated_news(self, max_age_hours: int = 24) -> List[Dict]:
        """
        Busca e agrega notícias de todas as fontes
        
        Args:
            max_age_hours: Idade máxima das notícias em horas
            
        Returns:
            Lista agregada de notícias
        """
        # Verificar cache
        if self._is_cache_valid(self._cache_timestamp, self._cache_timeout):
            return self._news_cache
        
        all_news = []
        
        # Buscar de todas as fontes
        all_news.extend(self.fetch_forex_news(limit=30))
        all_news.extend(self.fetch_finazon_news(limit=30))
        
        # Filtrar por idade
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        filtered_news = []
        for news in all_news:
            try:
                # Tentar parsear data
                pub_date_str = news.get('published_at', '')
                if pub_date_str:
                    # Tentar múltiplos formatos de data
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%SZ',
                               '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']:
                        try:
                            pub_date = datetime.strptime(pub_date_str, fmt)
                            if pub_date > cutoff_time:
                                filtered_news.append(news)
                            break
                        except ValueError:
                            continue
            except Exception as e:
                logger.debug(f"Erro ao parsear data: {e}")
                # Se não conseguir parsear, incluir mesmo assim
                filtered_news.append(news)
        
        # Ordenar por relevância
        filtered_news.sort(key=lambda x: x.get('relevance', 0), reverse=True)
        
        # Atualizar cache
        self._news_cache = filtered_news
        self._cache_timestamp = datetime.now()
        
        logger.info(f"Notícias agregadas: {len(filtered_news)} itens")
        return filtered_news
    
    def get_sentiment_summary(self, max_news: int = 20) -> Dict:
        """
        Gera resumo do sentimento geral das notícias
        
        Args:
            max_news: Número máximo de notícias a analisar
            
        Returns:
            Dict com estatísticas de sentimento
        """
        news_list = self.get_aggregated_news()[:max_news]
        
        if not news_list:
            return {
                'overall_sentiment': 'neutral',
                'polarity_avg': 0.0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'total_analyzed': 0
            }
        
        polarities = []
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        for news in news_list:
            text = news.get('title', '') + ' ' + news.get('description', '')
            sentiment = self.analyze_sentiment(text)
            polarity = sentiment['polarity']
            
            polarities.append(polarity)
            
            if polarity > 0.1:
                bullish_count += 1
            elif polarity < -0.1:
                bearish_count += 1
            else:
                neutral_count += 1
        
        # Calcular média ponderada por relevância
        weighted_polarity = 0.0
        total_weight = 0.0
        
        for news, polarity in zip(news_list, polarities):
            weight = news.get('relevance', 0.5)
            weighted_polarity += polarity * weight
            total_weight += weight
        
        avg_polarity = weighted_polarity / total_weight if total_weight > 0 else 0.0
        
        # Determinar sentimento geral
        if avg_polarity > 0.2:
            overall = 'bullish'
        elif avg_polarity < -0.2:
            overall = 'bearish'
        else:
            overall = 'neutral'
        
        return {
            'overall_sentiment': overall,
            'polarity_avg': round(avg_polarity, 3),
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count,
            'total_analyzed': len(news_list)
        }
    
    def is_news_blocking_window(self, buffer_minutes: int = 15) -> Tuple[bool, Optional[Dict]]:
        """
        Verifica se estamos dentro de janela de bloqueio de notícias
        
        Args:
            buffer_minutes: Minutos antes/depois do evento para bloquear
            
        Returns:
            (is_blocking, event_info)
        """
        # Se buffer é 0, não bloquear
        if buffer_minutes == 0:
            return False, None
            
        events = self.fetch_economic_calendar(days=1)
        
        if not events:
            return False, None
        
        now = datetime.now(pytz.UTC)
        buffer = timedelta(minutes=buffer_minutes)
        
        for event in events:
            try:
                # Parsear data do evento
                event_date_str = event.get('date', '')
                
                # Tentar múltiplos formatos
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                           '%Y-%m-%dT%H:%M:%SZ']:
                    try:
                        event_date = datetime.strptime(event_date_str, fmt)
                        event_date = pytz.UTC.localize(event_date)
                        
                        # Verificar se estamos no intervalo de bloqueio
                        time_diff = abs((event_date - now).total_seconds())
                        
                        if time_diff < buffer.total_seconds():
                            logger.warning(
                                f"Janela de bloqueio ativa: {event['event']} "
                                f"em {event_date_str}"
                            )
                            return True, event
                        
                        break
                    except ValueError:
                        continue
                        
            except Exception as e:
                logger.debug(f"Erro ao processar evento: {e}")
                continue
        
        return False, None
    
    def get_news_signal(self) -> Dict:
        """
        Gera sinal baseado em notícias
        
        Returns:
            Dict com sinal e análise
        """
        # Verificar janela de bloqueio
        is_blocking, blocking_event = self.is_news_blocking_window()
        
        if is_blocking:
            return {
                'action': 'BLOCK',
                'reason': 'high_impact_event',
                'event': blocking_event,
                'confidence': 1.0
            }
        
        # Obter sentimento geral
        sentiment = self.get_sentiment_summary()
        
        # Determinar ação baseada em sentimento
        overall = sentiment['overall_sentiment']
        polarity = sentiment['polarity_avg']
        
        # Calcular confiança baseada em consenso
        total = sentiment['total_analyzed']
        if total == 0:
            confidence = 0.0
        else:
            if overall == 'bullish':
                confidence = sentiment['bullish_count'] / total
            elif overall == 'bearish':
                confidence = sentiment['bearish_count'] / total
            else:
                confidence = sentiment['neutral_count'] / total
        
        # Ajustar confiança pela polaridade
        confidence = confidence * min(abs(polarity) * 2, 1.0)
        
        return {
            'action': overall.upper() if overall != 'neutral' else 'HOLD',
            'reason': 'news_sentiment',
            'sentiment': sentiment,
            'confidence': round(confidence, 2),
            'news_count': total
        }
    
    def get_top_news(self, limit: int = 5) -> List[Dict]:
        """
        Retorna top notícias mais relevantes
        
        Args:
            limit: Número de notícias
            
        Returns:
            Lista de top notícias
        """
        news_list = self.get_aggregated_news()
        
        # Adicionar sentimento a cada notícia
        for news in news_list[:limit]:
            text = news.get('title', '') + ' ' + news.get('description', '')
            sentiment = self.analyze_sentiment(text)
            news['sentiment'] = sentiment
        
        return news_list[:limit]
    
    def clear_cache(self):
        """Limpa todos os caches"""
        self._news_cache = []
        self._cache_timestamp = None
        self._events_cache = []
        self._events_cache_timestamp = None
        logger.debug("Cache de notícias limpo")
