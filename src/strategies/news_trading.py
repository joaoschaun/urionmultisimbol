"""
Estratégia: News Trading
Opera baseada em análise de sentimento de notícias
"""

from typing import Dict, Optional
from loguru import logger
from .base_strategy import BaseStrategy


class NewsTradingStrategy(BaseStrategy):
    """
    Estratégia baseada em notícias e sentimento
    
    Regras:
    - Sentimento forte de notícias (>60%)
    - Múltiplas notícias alinhadas
    - Não em janela de bloqueio
    - Confirmação técnica opcional
    """
    
    def __init__(self, config: Dict):
        super().__init__('NewsTrading', config)
        
        # Parâmetros
        self.sentiment_threshold = config.get('sentiment_threshold', 0.3)
        self.min_news_count = config.get('min_news_count', 3)
        self.min_agreement = config.get('min_agreement', 0.6)
    
    def analyze(self, technical_analysis: Dict,
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Analisa sentimento de notícias para gerar sinais
        
        Args:
            technical_analysis: Análise técnica
            news_analysis: Análise de notícias (OBRIGATÓRIO)
            
        Returns:
            Sinal de trading
        """
        try:
            # Notícias são obrigatórias para esta estratégia
            if not news_analysis:
                return self.create_signal('HOLD', 0.0, 'no_news_data')
            
            # Verificar bloqueio
            is_blocking = news_analysis.get('action') == 'BLOCK'
            if is_blocking:
                return self.create_signal(
                    'HOLD', 0.0, 'news_blocking_window',
                    {'event': news_analysis.get('event')}
                )
            
            # Extrair sentimento
            sentiment = news_analysis.get('sentiment', {})
            overall = sentiment.get('overall_sentiment', 'neutral')
            polarity = sentiment.get('polarity_avg', 0.0)
            total_news = sentiment.get('total_analyzed', 0)
            bullish_count = sentiment.get('bullish_count', 0)
            bearish_count = sentiment.get('bearish_count', 0)
            
            # Verificar mínimo de notícias
            if total_news < self.min_news_count:
                return self.create_signal(
                    'HOLD', 0.0, 'insufficient_news',
                    {'news_count': total_news}
                )
            
            # Calcular nível de acordo (concordância)
            if total_news > 0:
                if overall == 'bullish':
                    agreement = bullish_count / total_news
                elif overall == 'bearish':
                    agreement = bearish_count / total_news
                else:
                    agreement = 0.0
            else:
                agreement = 0.0
            
            # === CONDIÇÕES PARA SINAL DE ALTA ===
            bullish_news = {
                # Sentimento geral é bullish
                'sentiment_bullish': overall == 'bullish',
                
                # Polaridade positiva forte
                'strong_positive_polarity': polarity > self.sentiment_threshold,
                
                # Alta concordância entre notícias
                'high_agreement': agreement > self.min_agreement,
                
                # Número adequado de notícias bullish
                'enough_bullish_news': bullish_count >= self.min_news_count,
                
                # Notícias recentes (implícito na análise)
                'recent_news': total_news > 0
            }
            
            # === CONDIÇÕES PARA SINAL DE BAIXA ===
            bearish_news = {
                # Sentimento geral é bearish
                'sentiment_bearish': overall == 'bearish',
                
                # Polaridade negativa forte
                'strong_negative_polarity': polarity < -self.sentiment_threshold,
                
                # Alta concordância entre notícias
                'high_agreement': agreement > self.min_agreement,
                
                # Número adequado de notícias bearish
                'enough_bearish_news': bearish_count >= self.min_news_count,
                
                # Notícias recentes
                'recent_news': total_news > 0
            }
            
            # Pesos (concordância é muito importante)
            weights = {
                'sentiment_bullish': 1.5,
                'sentiment_bearish': 1.5,
                'strong_positive_polarity': 1.2,
                'strong_negative_polarity': 1.2,
                'high_agreement': 2.0,
                'enough_bullish_news': 1.0,
                'enough_bearish_news': 1.0,
                'recent_news': 0.8
            }
            
            bullish_score = self.calculate_score(bullish_news, weights)
            bearish_score = self.calculate_score(bearish_news, weights)
            
            # Determinar ação
            if bullish_score > bearish_score and bullish_score >= self.min_confidence:
                action = 'BUY'
                confidence = bullish_score
                reason = 'positive_news_sentiment'
                details = {
                    'polarity': polarity,
                    'agreement': agreement,
                    'total_news': total_news,
                    'bullish_count': bullish_count,
                    'bearish_count': bearish_count,
                    'conditions_met': sum(bullish_news.values()),
                    'total_conditions': len(bullish_news)
                }
                
            elif bearish_score > bullish_score and bearish_score >= self.min_confidence:
                action = 'SELL'
                confidence = bearish_score
                reason = 'negative_news_sentiment'
                details = {
                    'polarity': polarity,
                    'agreement': agreement,
                    'total_news': total_news,
                    'bullish_count': bullish_count,
                    'bearish_count': bearish_count,
                    'conditions_met': sum(bearish_news.values()),
                    'total_conditions': len(bearish_news)
                }
                
            else:
                action = 'HOLD'
                confidence = max(bullish_score, bearish_score)
                reason = 'neutral_news_sentiment'
                details = {
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'polarity': polarity,
                    'total_news': total_news
                }
            
            # Confirmação técnica (opcional mas aumenta confiança)
            if technical_analysis and 'M5' in technical_analysis and action != 'HOLD':
                m5_data = technical_analysis['M5']
                trend = m5_data.get('trend', {})
                tech_direction = trend.get('direction', 'neutral')
                
                # Técnica alinhada com notícias
                if (action == 'BUY' and tech_direction == 'bullish') or \
                   (action == 'SELL' and tech_direction == 'bearish'):
                    confidence = min(confidence * 1.25, 1.0)
                    details['technical_confirmation'] = True
                    logger.info("NewsTrading: Confirmação técnica alinhada")
                elif tech_direction == 'neutral':
                    # Neutro não ajuda nem atrapalha
                    details['technical_confirmation'] = 'neutral'
                else:
                    # Técnica contradiz notícias - reduz confiança
                    confidence *= 0.7
                    details['technical_confirmation'] = False
                    logger.warning("NewsTrading: Técnica contradiz notícias")
            
            signal = self.create_signal(action, confidence, reason, details)
            
            if self.validate_signal(signal):
                logger.info(
                    f"NewsTrading: {action} baseado em {total_news} notícias "
                    f"(polaridade: {polarity:+.2f}, confiança: {confidence:.2%})"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Erro na estratégia NewsTrading: {e}")
            return self.create_signal('HOLD', 0.0, 'error')
