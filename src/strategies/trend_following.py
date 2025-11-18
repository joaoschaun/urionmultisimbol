"""
Estratégia: Trend Following
Opera seguindo tendências fortes identificadas por múltiplos indicadores
"""

from typing import Dict, Optional
from loguru import logger
from .base_strategy import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    """
    Estratégia de seguimento de tendência
    
    Regras:
    - ADX > 25 (tendência forte)
    - EMA 9 > EMA 21 > EMA 50 (alta) ou inverso (baixa)
    - MACD confirma direção
    - Preço acima/abaixo das médias móveis
    - RSI não em extremos (evita sobrecompra/sobrevenda)
    """
    
    def __init__(self, config: Dict):
        super().__init__('TrendFollowing', config)
        
        # Parâmetros configuráveis
        self.adx_threshold = config.get('adx_threshold', 25)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.min_ema_separation = config.get('min_ema_separation', 0.0001)
    
    def analyze(self, technical_analysis: Dict,
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Analisa mercado para identificar tendências
        
        Args:
            technical_analysis: Análise técnica multi-timeframe
            news_analysis: Análise de notícias (opcional)
            
        Returns:
            Sinal de trading ou None
        """
        try:
            # Usar timeframe principal (M5)
            if 'M5' not in technical_analysis:
                logger.warning("M5 não disponível para TrendFollowing")
                return self.create_signal('HOLD', 0.0, 'no_data')
            
            m5_data = technical_analysis['M5']
            
            # Extrair indicadores
            current_price = m5_data.get('current_price', 0)
            rsi = m5_data.get('rsi', 50)
            macd_data = m5_data.get('macd', {})
            adx_data = m5_data.get('adx', {})
            ema = m5_data.get('ema', {})
            
            # Valores necessários
            adx = adx_data.get('adx', 0)
            di_plus = adx_data.get('di_plus', 0)
            di_minus = adx_data.get('di_minus', 0)
            
            macd_line = macd_data.get('macd', 0)
            macd_signal = macd_data.get('signal', 0)
            
            ema_9 = ema.get('ema_9', 0)
            ema_21 = ema.get('ema_21', 0)
            ema_50 = ema.get('ema_50', 0)
            
            # Verificar se há dados suficientes
            if not all([adx, ema_9, ema_21, ema_50, current_price]):
                return self.create_signal('HOLD', 0.0, 'insufficient_data')
            
            # === ANÁLISE DE TENDÊNCIA DE ALTA ===
            bullish_conditions = {
                # ADX indica tendência forte
                'strong_trend': adx > self.adx_threshold,
                
                # DI+ > DI- (direcional positivo)
                'directional_positive': di_plus > di_minus,
                
                # EMAs alinhadas (9 > 21 > 50)
                'ema_alignment': ema_9 > ema_21 and ema_21 > ema_50,
                
                # Separação adequada entre EMAs
                'ema_separation': (ema_9 - ema_50) / ema_50 > self.min_ema_separation,
                
                # Preço acima das médias
                'price_above_ema': current_price > ema_9,
                
                # MACD positivo
                'macd_positive': macd_line > macd_signal,
                
                # RSI não em sobrecompra
                'rsi_not_overbought': rsi < self.rsi_overbought,
                
                # RSI em zona de tendência (40-70)
                'rsi_trending': 40 < rsi < 70
            }
            
            # === ANÁLISE DE TENDÊNCIA DE BAIXA ===
            bearish_conditions = {
                # ADX indica tendência forte
                'strong_trend': adx > self.adx_threshold,
                
                # DI- > DI+ (direcional negativo)
                'directional_negative': di_minus > di_plus,
                
                # EMAs alinhadas (9 < 21 < 50)
                'ema_alignment': ema_9 < ema_21 and ema_21 < ema_50,
                
                # Separação adequada entre EMAs
                'ema_separation': (ema_50 - ema_9) / ema_50 > self.min_ema_separation,
                
                # Preço abaixo das médias
                'price_below_ema': current_price < ema_9,
                
                # MACD negativo
                'macd_negative': macd_line < macd_signal,
                
                # RSI não em sobrevenda
                'rsi_not_oversold': rsi > self.rsi_oversold,
                
                # RSI em zona de tendência (30-60)
                'rsi_trending': 30 < rsi < 60
            }
            
            # Calcular scores
            bullish_score = self.calculate_score(bullish_conditions)
            bearish_score = self.calculate_score(bearish_conditions)
            
            # Determinar ação
            if bullish_score > bearish_score and bullish_score >= self.min_confidence:
                action = 'BUY'
                confidence = bullish_score
                reason = 'strong_uptrend_detected'
                details = {
                    'current_price': current_price,
                    'adx': adx,
                    'ema_9': ema_9,
                    'ema_21': ema_21,
                    'ema_50': ema_50,
                    'rsi': rsi,
                    'macd_histogram': macd_line - macd_signal,
                    'conditions_met': sum(bullish_conditions.values()),
                    'total_conditions': len(bullish_conditions)
                }
                
            elif bearish_score > bullish_score and bearish_score >= self.min_confidence:
                action = 'SELL'
                confidence = bearish_score
                reason = 'strong_downtrend_detected'
                details = {
                    'current_price': current_price,
                    'adx': adx,
                    'ema_9': ema_9,
                    'ema_21': ema_21,
                    'ema_50': ema_50,
                    'rsi': rsi,
                    'macd_histogram': macd_line - macd_signal,
                    'conditions_met': sum(bearish_conditions.values()),
                    'total_conditions': len(bearish_conditions)
                }
                
            else:
                action = 'HOLD'
                confidence = max(bullish_score, bearish_score)
                reason = 'no_clear_trend'
                details = {
                    'current_price': current_price,
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'adx': adx
                }
            
            # Ajustar confiança com confirmação de timeframes maiores
            if 'M15' in technical_analysis:
                m15_trend = technical_analysis['M15'].get('trend', {})
                m15_direction = m15_trend.get('direction', 'neutral')
                
                # Confirma se M15 está alinhado
                if (action == 'BUY' and m15_direction == 'bullish') or \
                   (action == 'SELL' and m15_direction == 'bearish'):
                    confidence = min(confidence * 1.1, 1.0)
                    details['m15_confirmation'] = True
                elif m15_direction != 'neutral':
                    confidence *= 0.9
                    details['m15_confirmation'] = False
            
            # Ajustar confiança com análise de notícias
            if news_analysis:
                news_sentiment = news_analysis.get('sentiment', {})
                news_overall = news_sentiment.get('overall_sentiment', 'neutral')
                
                # Confirma se notícias estão alinhadas
                if (action == 'BUY' and news_overall == 'bullish') or \
                   (action == 'SELL' and news_overall == 'bearish'):
                    confidence = min(confidence * 1.05, 1.0)
                    details['news_confirmation'] = True
                elif news_overall != 'neutral':
                    confidence *= 0.95
                    details['news_confirmation'] = False
            
            signal = self.create_signal(action, confidence, reason, details)
            
            if self.validate_signal(signal):
                logger.info(
                    f"TrendFollowing: {action} @ {current_price:.2f} "
                    f"(confiança: {confidence:.2%})"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Erro na estratégia TrendFollowing: {e}")
            return self.create_signal('HOLD', 0.0, 'error')
