"""
Estratégia: Scalping
Opera em movimentos rápidos de preço com entrada/saída rápida
"""

from typing import Dict, Optional
from loguru import logger
from .base_strategy import BaseStrategy


class ScalpingStrategy(BaseStrategy):
    """
    Estratégia de Scalping (operações rápidas)
    
    Regras:
    - Timeframe: M1 e M5 (curto prazo)
    - Movimentos rápidos com volume
    - Spread baixo (< 3 pips)
    - RSI entre 40-60 (evita extremos)
    - Confirmação de momentum (MACD e Stochastic)
    - Target pequeno: 5-10 pips
    - Stop apertado: 3-5 pips
    """
    
    def __init__(self, config: Dict):
        super().__init__('Scalping', config)
        
        # Parâmetros configuráveis
        self.max_spread_pips = config.get('max_spread_pips', 3)
        self.min_momentum = config.get('min_momentum', 0.0002)
        self.rsi_min = config.get('rsi_min', 40)
        self.rsi_max = config.get('rsi_max', 60)
        self.target_pips = config.get('target_pips', 8)
        self.stop_pips = config.get('stop_pips', 4)
        self.min_volume_ratio = config.get('min_volume_ratio', 1.2)
    
    def analyze(self, technical_analysis: Dict,
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Analisa mercado para identificar oportunidades de scalping
        
        Args:
            technical_analysis: Análise técnica multi-timeframe
            news_analysis: Análise de notícias (opcional)
            
        Returns:
            Sinal de trading
        """
        try:
            # Usar M5 como principal (mais estável que M1)
            if 'M5' not in technical_analysis:
                logger.debug("M5 não disponível para Scalping")
                return self.create_signal('HOLD', 0.0, 'no_data')
            
            m5 = technical_analysis['M5']
            
            # Extrair indicadores
            indicators = m5.get('indicators', {})
            price = m5.get('current_price', 0)
            
            if not indicators or price == 0:
                return self.create_signal('HOLD', 0.0, 'no_indicators')
            
            # 1. Verificar spread (simular - 0.2 = 2 pips para XAUUSD)
            estimated_spread = price * 0.0002  # 0.02% = ~2 pips
            spread_pips = estimated_spread / 0.1  # Converter para pips
            
            if spread_pips > self.max_spread_pips:
                return self.create_signal(
                    'HOLD', 0.0, 
                    f'high_spread_{spread_pips:.1f}pips'
                )
            
            # 2. Verificar RSI (deve estar neutro)
            rsi = indicators.get('RSI', 50)
            if rsi < self.rsi_min or rsi > self.rsi_max:
                return self.create_signal(
                    'HOLD', 0.0,
                    f'rsi_extreme_{rsi:.1f}'
                )
            
            # 3. Verificar momentum (MACD e Stochastic)
            macd = indicators.get('MACD', {})
            macd_line = macd.get('macd', 0)
            macd_signal = macd.get('signal', 0)
            macd_hist = macd.get('histogram', 0)
            
            stochastic = indicators.get('Stochastic', {})
            stoch_k = stochastic.get('k', 50)
            stoch_d = stochastic.get('d', 50)
            
            # 4. Calcular momentum score
            momentum_score = 0
            action = 'HOLD'
            reasons = []
            
            # MACD positivo = compra
            if macd_hist > 0 and macd_line > macd_signal:
                momentum_score += 2
                action = 'BUY'
                reasons.append('macd_bullish')
            elif macd_hist < 0 and macd_line < macd_signal:
                momentum_score += 2
                action = 'SELL'
                reasons.append('macd_bearish')
            
            # Stochastic confirma
            if action == 'BUY' and stoch_k > stoch_d and stoch_k < 80:
                momentum_score += 1
                reasons.append('stoch_bullish')
            elif action == 'SELL' and stoch_k < stoch_d and stoch_k > 20:
                momentum_score += 1
                reasons.append('stoch_bearish')
            
            # 5. Verificar volume (se disponível)
            volume_ratio = indicators.get('volume_ratio', 1.0)
            if volume_ratio >= self.min_volume_ratio:
                momentum_score += 1
                reasons.append(f'volume_{volume_ratio:.1f}x')
            
            # 6. Verificar EMAs curtas (9, 21)
            ema_9 = indicators.get('EMA_9', price)
            ema_21 = indicators.get('EMA_21', price)
            
            if action == 'BUY' and price > ema_9 > ema_21:
                momentum_score += 1
                reasons.append('price_above_emas')
            elif action == 'SELL' and price < ema_9 < ema_21:
                momentum_score += 1
                reasons.append('price_below_emas')
            
            # 7. Calcular confiança (máximo 5 pontos)
            max_score = 5
            confidence = min(momentum_score / max_score, 1.0)
            
            # Precisamos de pelo menos 60% de confiança (3/5 pontos)
            if confidence < 0.6:
                return self.create_signal(
                    'HOLD', confidence,
                    f'low_momentum_{momentum_score}/{max_score}'
                )
            
            # 8. Confirmar com timeframe M15 (se disponível)
            if 'M15' in technical_analysis:
                m15 = technical_analysis['M15']
                m15_indicators = m15.get('indicators', {})
                m15_rsi = m15_indicators.get('RSI', 50)
                
                # M15 deve estar na mesma direção
                if action == 'BUY' and m15_rsi > 55:
                    confidence += 0.05
                    reasons.append('m15_confirms')
                elif action == 'SELL' and m15_rsi < 45:
                    confidence += 0.05
                    reasons.append('m15_confirms')
            
            # Limitar confiança a 85% (scalping é arriscado)
            confidence = min(confidence, 0.85)
            
            if action in ['BUY', 'SELL']:
                logger.info(
                    f"Scalping: {action} @ {price} "
                    f"(confiança: {confidence:.2%})"
                )
                
                return self.create_signal(
                    action, confidence,
                    ', '.join(reasons),
                    {
                        'entry_price': price,
                        'target_pips': self.target_pips,
                        'stop_pips': self.stop_pips,
                        'rsi': rsi,
                        'macd_hist': macd_hist,
                        'momentum_score': f"{momentum_score}/{max_score}",
                        'spread_pips': round(spread_pips, 1)
                    }
                )
            
            return self.create_signal('HOLD', confidence, 'no_clear_signal')
            
        except Exception as e:
            logger.error(f"Erro em ScalpingStrategy.analyze: {e}")
            return self.create_signal('HOLD', 0.0, f'error: {e}')
