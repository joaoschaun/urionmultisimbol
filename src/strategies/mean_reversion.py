"""
Estratégia: Mean Reversion
Opera em reversões à média quando preço atinge extremos
"""

from typing import Dict, Optional
from loguru import logger
from .base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """
    Estratégia de reversão à média
    
    Regras:
    - RSI em extremos (>70 ou <30)
    - Preço fora das Bandas de Bollinger
    - ADX < 25 (sem tendência forte)
    - Stochastic em extremos
    - Padrões de reversão (Doji, Hammer, etc)
    """
    
    def __init__(self, config: Dict):
        super().__init__('MeanReversion', config)
        
        # Parâmetros
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.adx_max = config.get('adx_max', 25)
        self.stoch_high = config.get('stoch_high', 80)
        self.stoch_low = config.get('stoch_low', 20)
    
    def analyze(self, technical_analysis: Dict,
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Analisa mercado para identificar oportunidades de reversão
        
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
            rsi = m5_data.get('rsi', 50)
            bollinger = m5_data.get('bollinger', {})
            adx_data = m5_data.get('adx', {})
            stoch_data = m5_data.get('stochastic', {})
            patterns = m5_data.get('patterns', {})
            
            adx = adx_data.get('adx', 0)
            bb_upper = bollinger.get('upper', 0)
            bb_lower = bollinger.get('lower', 0)
            bb_middle = bollinger.get('middle', 0)
            stoch_k = stoch_data.get('k', 50)
            
            if not all([current_price, bb_upper, bb_lower, bb_middle]):
                return self.create_signal('HOLD', 0.0, 'insufficient_data')
            
            # === CONDIÇÕES PARA REVERSÃO DE ALTA (COMPRA) ===
            # Preço caiu demais, hora de comprar
            bullish_reversal = {
                # RSI em sobrevenda
                'rsi_oversold': rsi < self.rsi_oversold,
                
                # Preço abaixo da banda inferior
                'below_bb_lower': current_price < bb_lower,
                
                # Sem tendência forte (permite reversão)
                'no_strong_trend': adx < self.adx_max,
                
                # Stochastic em zona baixa
                'stoch_oversold': stoch_k < self.stoch_low,
                
                # Padrões de reversão de alta
                'bullish_pattern': any([
                    patterns.get('hammer', False),
                    patterns.get('inverted_hammer', False),
                    patterns.get('engulfing_bullish', False),
                    patterns.get('morning_star', False),
                    patterns.get('pin_bar_bullish', False)
                ]),
                
                # Preço está longe da média (oportunidade)
                'far_from_mean': current_price < bb_middle * 0.995
            }
            
            # === CONDIÇÕES PARA REVERSÃO DE BAIXA (VENDA) ===
            # Preço subiu demais, hora de vender
            bearish_reversal = {
                # RSI em sobrecompra
                'rsi_overbought': rsi > self.rsi_overbought,
                
                # Preço acima da banda superior
                'above_bb_upper': current_price > bb_upper,
                
                # Sem tendência forte
                'no_strong_trend': adx < self.adx_max,
                
                # Stochastic em zona alta
                'stoch_overbought': stoch_k > self.stoch_high,
                
                # Padrões de reversão de baixa
                'bearish_pattern': any([
                    patterns.get('shooting_star', False),
                    patterns.get('engulfing_bearish', False),
                    patterns.get('evening_star', False),
                    patterns.get('pin_bar_bearish', False)
                ]),
                
                # Preço está longe da média
                'far_from_mean': current_price > bb_middle * 1.005
            }
            
            # Pesos personalizados (RSI e BB mais importantes)
            weights = {
                'rsi_oversold': 1.5,
                'rsi_overbought': 1.5,
                'below_bb_lower': 1.5,
                'above_bb_upper': 1.5,
                'no_strong_trend': 1.0,
                'stoch_oversold': 1.0,
                'stoch_overbought': 1.0,
                'bullish_pattern': 1.2,
                'bearish_pattern': 1.2,
                'far_from_mean': 1.0
            }
            
            bullish_score = self.calculate_score(bullish_reversal, weights)
            bearish_score = self.calculate_score(bearish_reversal, weights)
            
            # Determinar ação
            if bullish_score > bearish_score and bullish_score >= self.min_confidence:
                action = 'BUY'
                confidence = bullish_score
                reason = 'oversold_reversal_expected'
                details = {
                    'rsi': rsi,
                    'price': current_price,
                    'bb_lower': bb_lower,
                    'bb_middle': bb_middle,
                    'distance_from_mean': ((current_price - bb_middle) / bb_middle) * 100,
                    'stoch_k': stoch_k,
                    'adx': adx,
                    'patterns_detected': [k for k, v in patterns.items() if v],
                    'conditions_met': sum(bullish_reversal.values()),
                    'total_conditions': len(bullish_reversal)
                }
                
            elif bearish_score > bullish_score and bearish_score >= self.min_confidence:
                action = 'SELL'
                confidence = bearish_score
                reason = 'overbought_reversal_expected'
                details = {
                    'rsi': rsi,
                    'price': current_price,
                    'bb_upper': bb_upper,
                    'bb_middle': bb_middle,
                    'distance_from_mean': ((current_price - bb_middle) / bb_middle) * 100,
                    'stoch_k': stoch_k,
                    'adx': adx,
                    'patterns_detected': [k for k, v in patterns.items() if v],
                    'conditions_met': sum(bearish_reversal.values()),
                    'total_conditions': len(bearish_reversal)
                }
                
            else:
                action = 'HOLD'
                confidence = max(bullish_score, bearish_score)
                reason = 'no_clear_reversal'
                details = {
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'rsi': rsi
                }
            
            # Confirmação com timeframe maior
            if 'M15' in technical_analysis and action != 'HOLD':
                m15_data = technical_analysis['M15']
                m15_rsi = m15_data.get('rsi', 50)
                
                # M15 deve estar em extremo também
                if action == 'BUY' and m15_rsi < 35:
                    confidence = min(confidence * 1.15, 1.0)
                    details['m15_confirmation'] = True
                elif action == 'SELL' and m15_rsi > 65:
                    confidence = min(confidence * 1.15, 1.0)
                    details['m15_confirmation'] = True
                else:
                    confidence *= 0.9
                    details['m15_confirmation'] = False
            
            signal = self.create_signal(action, confidence, reason, details)
            
            if self.validate_signal(signal):
                logger.info(
                    f"MeanReversion: {action} @ {current_price:.2f} "
                    f"(RSI: {rsi:.1f}, confiança: {confidence:.2%})"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Erro na estratégia MeanReversion: {e}")
            return self.create_signal('HOLD', 0.0, 'error')
