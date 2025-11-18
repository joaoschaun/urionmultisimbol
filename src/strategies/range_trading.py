"""
Estratégia: Range Trading
Opera em mercados laterais/consolidados comprando no suporte e vendendo na resistência
Ideal para quando NÃO há tendência clara (ADX baixo, mercado consolidado)
"""

from typing import Dict, Optional
from loguru import logger
from .base_strategy import BaseStrategy


class RangeTradingStrategy(BaseStrategy):
    """
    Estratégia de Range Trading (mercado lateral)
    
    Regras:
    - ADX < 25 (SEM tendência forte - mercado lateral)
    - Preço nas extremidades das Bandas de Bollinger
    - RSI em extremos mas não muito extremo (35-45 para compra, 55-65 para venda)
    - Stochastic confirma reversão
    - Preço oscilando entre suporte e resistência
    - Volume normal (não precisa ser alto)
    
    OBJETIVO: Lucrar com oscilações dentro de um range definido
    """
    
    def __init__(self, config: Dict):
        super().__init__('RangeTrading', config)
        
        # Parâmetros para mercado lateral
        self.adx_max = config.get('adx_max', 25)  # ADX BAIXO = sem tendência
        self.rsi_buy_min = config.get('rsi_buy_min', 35)
        self.rsi_buy_max = config.get('rsi_buy_max', 45)
        self.rsi_sell_min = config.get('rsi_sell_min', 55)
        self.rsi_sell_max = config.get('rsi_sell_max', 65)
        self.stoch_low = config.get('stoch_low', 30)
        self.stoch_high = config.get('stoch_high', 70)
        self.bb_touch_threshold = config.get('bb_touch_threshold', 0.003)  # 0.3% da banda
    
    def analyze(self, technical_analysis: Dict,
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Analisa mercado para identificar oportunidades em range
        
        Args:
            technical_analysis: Análise técnica multi-timeframe
            news_analysis: Análise de notícias (opcional)
            
        Returns:
            Sinal de trading
        """
        try:
            # Usar M5 como principal
            if 'M5' not in technical_analysis:
                return self.create_signal('HOLD', 0.0, 'no_data')
            
            m5_data = technical_analysis['M5']
            
            # Extrair indicadores
            current_price = m5_data.get('current_price', 0)
            rsi = m5_data.get('rsi', 50)
            bollinger = m5_data.get('bollinger', {})
            adx_data = m5_data.get('adx', {})
            stoch_data = m5_data.get('stochastic', {})
            ema = m5_data.get('ema', {})
            
            adx = adx_data.get('adx', 0)
            bb_upper = bollinger.get('upper', 0)
            bb_lower = bollinger.get('lower', 0)
            bb_middle = bollinger.get('middle', 0)
            stoch_k = stoch_data.get('k', 50)
            stoch_d = stoch_data.get('d', 50)
            ema_21 = ema.get('ema_21', 0)
            
            if not all([current_price, bb_upper, bb_lower, bb_middle, ema_21]):
                return self.create_signal('HOLD', 0.0, 'insufficient_data')
            
            # Calcular distância das bandas
            distance_from_lower = current_price - bb_lower
            distance_from_upper = bb_upper - current_price
            bb_width = bb_upper - bb_lower
            
            # === CONDIÇÃO PRINCIPAL: MERCADO LATERAL (SEM TENDÊNCIA) ===
            is_ranging = adx < self.adx_max
            
            if not is_ranging:
                return self.create_signal(
                    'HOLD', 0.0,
                    f'market_trending_adx_{adx:.1f}'
                )
            
            # === COMPRA NO SUPORTE (banda inferior) ===
            buy_range_conditions = {
                # Mercado lateral (ADX baixo)
                'no_trend': adx < self.adx_max,
                
                # Preço próximo da banda inferior (suporte)
                'near_lower_band': distance_from_lower < (bb_width * self.bb_touch_threshold),
                
                # RSI indicando possível alta mas não muito baixo
                'rsi_buy_zone': self.rsi_buy_min < rsi < self.rsi_buy_max,
                
                # Stochastic em zona baixa
                'stoch_oversold': stoch_k < self.stoch_low,
                
                # Stochastic virando para cima (K cruzando D)
                'stoch_turning_up': stoch_k > stoch_d,
                
                # Preço abaixo da média (banda do meio)
                'below_middle': current_price < bb_middle,
                
                # Preço abaixo da EMA21
                'below_ema21': current_price < ema_21,
                
                # Não está muito longe do suporte
                'close_to_support': distance_from_lower < (bb_width * 0.2)
            }
            
            # === VENDA NA RESISTÊNCIA (banda superior) ===
            sell_range_conditions = {
                # Mercado lateral (ADX baixo)
                'no_trend': adx < self.adx_max,
                
                # Preço próximo da banda superior (resistência)
                'near_upper_band': distance_from_upper < (bb_width * self.bb_touch_threshold),
                
                # RSI indicando possível baixa mas não muito alto
                'rsi_sell_zone': self.rsi_sell_min < rsi < self.rsi_sell_max,
                
                # Stochastic em zona alta
                'stoch_overbought': stoch_k > self.stoch_high,
                
                # Stochastic virando para baixo (K cruzando D)
                'stoch_turning_down': stoch_k < stoch_d,
                
                # Preço acima da média (banda do meio)
                'above_middle': current_price > bb_middle,
                
                # Preço acima da EMA21
                'above_ema21': current_price > ema_21,
                
                # Não está muito longe da resistência
                'close_to_resistance': distance_from_upper < (bb_width * 0.2)
            }
            
            # Calcular scores
            buy_score = self.calculate_score(buy_range_conditions)
            sell_score = self.calculate_score(sell_range_conditions)
            
            # Determinar ação
            if buy_score > sell_score and buy_score >= self.min_confidence:
                action = 'BUY'
                confidence = buy_score
                reason = 'range_bounce_from_support'
                details = {
                    'current_price': current_price,
                    'adx': adx,
                    'bb_lower': bb_lower,
                    'bb_middle': bb_middle,
                    'distance_from_support': distance_from_lower,
                    'rsi': rsi,
                    'stoch_k': stoch_k,
                    'conditions_met': sum(buy_range_conditions.values()),
                    'total_conditions': len(buy_range_conditions),
                    'strategy_type': 'RANGE_TRADING'
                }
                
            elif sell_score > buy_score and sell_score >= self.min_confidence:
                action = 'SELL'
                confidence = sell_score
                reason = 'range_rejection_from_resistance'
                details = {
                    'current_price': current_price,
                    'adx': adx,
                    'bb_upper': bb_upper,
                    'bb_middle': bb_middle,
                    'distance_from_resistance': distance_from_upper,
                    'rsi': rsi,
                    'stoch_k': stoch_k,
                    'conditions_met': sum(sell_range_conditions.values()),
                    'total_conditions': len(sell_range_conditions),
                    'strategy_type': 'RANGE_TRADING'
                }
                
            else:
                # Mercado lateral mas preço no meio do range
                action = 'HOLD'
                confidence = max(buy_score, sell_score)
                reason = f'price_in_middle_of_range_adx_{adx:.1f}'
                details = {
                    'current_price': current_price,
                    'adx': adx,
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'price_position': 'middle' if abs(current_price - bb_middle) < bb_width * 0.1 else 'undefined'
                }
            
            # Adicionar confirmação M15 se disponível
            if action in ['BUY', 'SELL'] and 'M15' in technical_analysis:
                m15_data = technical_analysis['M15']
                m15_adx = m15_data.get('adx', {}).get('adx', 0)
                
                # M15 também deve estar em range (ADX baixo)
                if m15_adx < self.adx_max:
                    confidence += 0.05
                    details['m15_confirms_range'] = True
                else:
                    # M15 com tendência pode invalidar o range
                    confidence -= 0.10
                    details['m15_trending'] = True
                    details['m15_adx'] = m15_adx
            
            # Limitar confiança
            confidence = min(max(confidence, 0.0), 1.0)
            
            if action in ['BUY', 'SELL']:
                logger.info(
                    f"RangeTrading: {action} @ {current_price:.2f} "
                    f"(confiança: {confidence:.2%}, ADX: {adx:.1f})"
                )
            
            return self.create_signal(action, confidence, reason, details)
            
        except Exception as e:
            logger.error(f"Erro em RangeTradingStrategy.analyze: {e}")
            return self.create_signal('HOLD', 0.0, f'error: {e}')
