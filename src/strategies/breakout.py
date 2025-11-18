"""
Estratégia: Breakout
Opera rompimentos de níveis importantes com volume
"""

from typing import Dict, Optional
from loguru import logger
from .base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Estratégia de rompimento (breakout)
    
    Regras:
    - Preço rompe banda de Bollinger
    - Volume aumentado (confirma força)
    - ADX crescente (tendência se fortalecendo)
    - MACD confirma direção
    - Preço consolida antes do rompimento
    """
    
    def __init__(self, config: Dict):
        super().__init__('Breakout', config)
        
        # Parâmetros
        self.adx_min = config.get('adx_min', 20)
        self.volume_multiplier = config.get('volume_multiplier', 1.5)
        self.consolidation_bars = config.get('consolidation_bars', 10)
    
    def analyze(self, technical_analysis: Dict,
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Analisa mercado para identificar breakouts
        
        Args:
            technical_analysis: Análise técnica multi-timeframe
            news_analysis: Análise de notícias (opcional)
            
        Returns:
            Sinal de trading
        """
        try:
            # Usar M5
            if 'M5' not in technical_analysis:
                return self.create_signal('HOLD', 0.0, 'no_data')
            
            m5_data = technical_analysis['M5']
            
            # Extrair indicadores
            current_price = m5_data.get('current_price', 0)
            bollinger = m5_data.get('bollinger', {})
            macd_data = m5_data.get('macd', {})
            adx_data = m5_data.get('adx', {})
            atr = m5_data.get('atr', 0)
            
            bb_upper = bollinger.get('upper', 0)
            bb_lower = bollinger.get('lower', 0)
            bb_middle = bollinger.get('middle', 0)
            
            macd_line = macd_data.get('macd', 0)
            macd_signal = macd_data.get('signal', 0)
            macd_histogram = macd_data.get('histogram', 0)
            
            adx = adx_data.get('adx', 0)
            di_plus = adx_data.get('di_plus', 0)
            di_minus = adx_data.get('di_minus', 0)
            
            if not all([current_price, bb_upper, bb_lower, bb_middle, atr]):
                return self.create_signal('HOLD', 0.0, 'insufficient_data')
            
            # Calcular distância das bandas
            distance_from_upper = current_price - bb_upper
            distance_from_lower = bb_lower - current_price
            
            # Amplitude das bandas (volatilidade)
            bb_width = bb_upper - bb_lower
            
            # === BREAKOUT DE ALTA ===
            bullish_breakout = {
                # Preço rompeu banda superior
                'breakout_upper': distance_from_upper > 0,
                
                # Ou está muito próximo (iminente)
                'near_upper': 0 <= distance_from_upper <= (atr * 0.2) if distance_from_upper >= 0 else False,
                
                # ADX indica força crescente
                'adx_strong': adx > self.adx_min,
                
                # DI+ dominante
                'directional_positive': di_plus > di_minus,
                
                # MACD positivo e crescente
                'macd_positive': macd_line > macd_signal,
                'macd_momentum': macd_histogram > 0,
                
                # Bandas não muito largas (não em alta volatilidade)
                'bb_not_too_wide': bb_width < (bb_middle * 0.05),
                
                # Preço acima da média
                'above_middle': current_price > bb_middle
            }
            
            # === BREAKOUT DE BAIXA ===
            bearish_breakout = {
                # Preço rompeu banda inferior
                'breakout_lower': distance_from_lower > 0,
                
                # Ou está muito próximo
                'near_lower': 0 <= distance_from_lower <= (atr * 0.2) if distance_from_lower >= 0 else False,
                
                # ADX indica força crescente
                'adx_strong': adx > self.adx_min,
                
                # DI- dominante
                'directional_negative': di_minus > di_plus,
                
                # MACD negativo e caindo
                'macd_negative': macd_line < macd_signal,
                'macd_momentum': macd_histogram < 0,
                
                # Bandas não muito largas
                'bb_not_too_wide': bb_width < (bb_middle * 0.05),
                
                # Preço abaixo da média
                'below_middle': current_price < bb_middle
            }
            
            # Pesos (breakout efetivo mais importante)
            weights_bull = {
                'breakout_upper': 2.0,
                'near_upper': 1.5,
                'adx_strong': 1.2,
                'directional_positive': 1.0,
                'macd_positive': 1.0,
                'macd_momentum': 1.0,
                'bb_not_too_wide': 0.8,
                'above_middle': 0.8
            }
            
            weights_bear = {
                'breakout_lower': 2.0,
                'near_lower': 1.5,
                'adx_strong': 1.2,
                'directional_negative': 1.0,
                'macd_negative': 1.0,
                'macd_momentum': 1.0,
                'bb_not_too_wide': 0.8,
                'below_middle': 0.8
            }
            
            bullish_score = self.calculate_score(bullish_breakout, weights_bull)
            bearish_score = self.calculate_score(bearish_breakout, weights_bear)
            
            # Determinar ação
            if bullish_score > bearish_score and bullish_score >= self.min_confidence:
                action = 'BUY'
                confidence = bullish_score
                reason = 'bullish_breakout_detected'
                details = {
                    'price': current_price,
                    'bb_upper': bb_upper,
                    'distance_from_upper': distance_from_upper,
                    'bb_width': bb_width,
                    'adx': adx,
                    'macd_histogram': macd_histogram,
                    'breakout_type': 'confirmed' if distance_from_upper > 0 else 'imminent',
                    'conditions_met': sum(bullish_breakout.values()),
                    'total_conditions': len(bullish_breakout)
                }
                
            elif bearish_score > bullish_score and bearish_score >= self.min_confidence:
                action = 'SELL'
                confidence = bearish_score
                reason = 'bearish_breakout_detected'
                details = {
                    'price': current_price,
                    'bb_lower': bb_lower,
                    'distance_from_lower': distance_from_lower,
                    'bb_width': bb_width,
                    'adx': adx,
                    'macd_histogram': macd_histogram,
                    'breakout_type': 'confirmed' if distance_from_lower > 0 else 'imminent',
                    'conditions_met': sum(bearish_breakout.values()),
                    'total_conditions': len(bearish_breakout)
                }
                
            else:
                action = 'HOLD'
                confidence = max(bullish_score, bearish_score)
                reason = 'no_breakout_detected'
                details = {
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'bb_width': bb_width
                }
            
            # Confirmação com H1 (timeframe maior)
            if 'H1' in technical_analysis and action != 'HOLD':
                h1_data = technical_analysis['H1']
                h1_trend = h1_data.get('trend', {})
                h1_direction = h1_trend.get('direction', 'neutral')
                
                # H1 deve estar na mesma direção
                if (action == 'BUY' and h1_direction == 'bullish') or \
                   (action == 'SELL' and h1_direction == 'bearish'):
                    confidence = min(confidence * 1.2, 1.0)
                    details['h1_confirmation'] = True
                else:
                    confidence *= 0.85
                    details['h1_confirmation'] = False
            
            # Evitar breakouts durante notícias de alto impacto
            if news_analysis:
                is_blocking, _ = news_analysis.get('is_blocking', (False, None))
                if is_blocking and action != 'HOLD':
                    confidence *= 0.5
                    details['news_caution'] = True
                    logger.warning("Breakout detectado durante evento de notícias")
            
            signal = self.create_signal(action, confidence, reason, details)
            
            if self.validate_signal(signal):
                breakout_type = details.get('breakout_type', 'unknown')
                logger.info(
                    f"Breakout: {action} @ {current_price:.2f} "
                    f"({breakout_type}, confiança: {confidence:.2%})"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Erro na estratégia Breakout: {e}")
            return self.create_signal('HOLD', 0.0, 'error')
