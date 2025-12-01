"""
Estratégia: Breakout v2.0
Opera rompimentos de níveis importantes com volume e confirmação

Melhorias v2.0:
- Volume profile confirmation
- Filtro de sessão (breakouts funcionam melhor London/NY)
- SL/TP dinâmico baseado em ATR
- Detecção de false breakout (rejection)
- Keltner Channel como confirmação
- Multi-timeframe validation
"""

from typing import Dict, Optional
from datetime import datetime
from loguru import logger
from .base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """
    Estratégia de rompimento (breakout) v2.0
    
    Regras:
    - Preço rompe banda de Bollinger ou Keltner
    - Volume aumentado (confirma força)
    - ADX crescente (tendência se fortalecendo)
    - MACD confirma direção
    - Preço consolida antes do rompimento
    - Sem divergência RSI (evita false breakout)
    - Confirmação de timeframe maior
    """
    
    def __init__(self, config: Dict):
        super().__init__('Breakout', config)
        
        # Parâmetros
        self.adx_min = config.get('adx_min', 20)
        self.volume_multiplier = config.get('volume_multiplier', 1.5)
        self.consolidation_bars = config.get('consolidation_bars', 10)
        
        # Novos parâmetros v2.0
        self.min_atr_pips = config.get('min_atr_pips', 5.0)
        self.max_atr_pips = config.get('max_atr_pips', 40.0)
        self.use_session_filter = config.get('use_session_filter', True)
        self.use_keltner_confirmation = config.get('use_keltner_confirmation', True)
        self.rejection_threshold = config.get('rejection_threshold', 0.5)  # 50% retracement = false breakout
        
        # Inicializar módulos avançados
        self._init_advanced_modules()
    
    def _init_advanced_modules(self):
        """Inicializa módulos avançados v2.0"""
        try:
            from ..core.trading_session_manager import get_session_manager
            self.session_manager = get_session_manager()
        except ImportError:
            self.session_manager = None
            
        try:
            from ..core.dynamic_risk_calculator import get_dynamic_calculator
            self.risk_calculator = get_dynamic_calculator()
        except ImportError:
            self.risk_calculator = None
    
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
            # Usar M30 para breakout (mais confiável que M5)
            primary_tf = 'M30' if 'M30' in technical_analysis else 'M15'
            if primary_tf not in technical_analysis:
                return self.create_signal('HOLD', 0.0, 'no_data')
            
            tf_data = technical_analysis[primary_tf]
            symbol = tf_data.get('symbol', 'XAUUSD')
            
            # === FILTRO DE SESSÃO ===
            if self.use_session_filter and self.session_manager:
                session_info = self.session_manager.get_current_session()
                session_quality = self.session_manager.get_session_quality()
                
                # Breakout precisa de volume - melhor em London/NY
                min_quality = 2  # moderate
                if session_quality.value < min_quality:
                    return self.create_signal('HOLD', 0.0, 'session_quality_low', {
                        'session': session_info['current_session'],
                        'quality': session_quality.name
                    })
            
            # Extrair indicadores
            current_price = tf_data.get('current_price', 0)
            previous_close = tf_data.get('previous_close', current_price)
            bollinger = tf_data.get('bollinger', {})
            keltner = tf_data.get('keltner', {})
            macd_data = tf_data.get('macd', {})
            adx_data = tf_data.get('adx', {})
            atr_raw = tf_data.get('atr', 0)  # Pode ser float ou dict
            volume_data = tf_data.get('volume', {})
            rsi = tf_data.get('rsi', 50)
            
            # Tratar bollinger (pode ser float ou dict)
            bb_upper = bollinger.get('upper', 0) if isinstance(bollinger, dict) else 0
            bb_lower = bollinger.get('lower', 0) if isinstance(bollinger, dict) else 0
            bb_middle = bollinger.get('middle', 0) if isinstance(bollinger, dict) else 0
            
            # Keltner Channel (se disponível) - tratar como dict ou usar fallback
            kc_upper = keltner.get('upper', bb_upper) if isinstance(keltner, dict) else bb_upper
            kc_lower = keltner.get('lower', bb_lower) if isinstance(keltner, dict) else bb_lower
            kc_middle = keltner.get('middle', bb_middle) if isinstance(keltner, dict) else bb_middle
            
            # Tratar MACD (pode ser float ou dict)
            macd_line = macd_data.get('macd', 0) if isinstance(macd_data, dict) else 0
            macd_signal = macd_data.get('signal', 0) if isinstance(macd_data, dict) else 0
            macd_histogram = macd_data.get('histogram', 0) if isinstance(macd_data, dict) else 0
            
            # Tratar ADX (pode ser float ou dict)
            adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else (adx_data if isinstance(adx_data, (int, float)) else 0)
            di_plus = adx_data.get('di_plus', 0) if isinstance(adx_data, dict) else 0
            di_minus = adx_data.get('di_minus', 0) if isinstance(adx_data, dict) else 0
            
            # Tratar ATR (pode ser float ou dict)
            atr = atr_raw if isinstance(atr_raw, (int, float)) else (atr_raw.get('atr', 0) if isinstance(atr_raw, dict) else 0)
            atr_pips = atr / 0.1 if symbol == 'XAUUSD' else atr / 0.0001
            
            # Tratar volume (pode ser float ou dict)
            volume_ratio = volume_data.get('ratio', 1.0) if isinstance(volume_data, dict) else 1.0
            
            if not all([current_price, bb_upper, bb_lower, bb_middle, atr]):
                return self.create_signal('HOLD', 0.0, 'insufficient_data')
            
            # === FILTRO DE VOLATILIDADE ===
            if atr_pips < self.min_atr_pips:
                return self.create_signal('HOLD', 0.0, 'volatility_too_low', {
                    'atr_pips': round(atr_pips, 2)
                })
            if atr_pips > self.max_atr_pips:
                return self.create_signal('HOLD', 0.0, 'volatility_too_high', {
                    'atr_pips': round(atr_pips, 2)
                })
            
            # Calcular métricas de breakout
            distance_from_bb_upper = current_price - bb_upper
            distance_from_bb_lower = bb_lower - current_price
            
            # Amplitude das bandas (volatilidade relativa)
            bb_width = bb_upper - bb_lower
            bb_width_pct = (bb_width / bb_middle) * 100
            
            # Squeeze detection (BB dentro do Keltner = consolidação)
            is_squeeze = bb_upper < kc_upper and bb_lower > kc_lower
            
            # Momentum da vela atual
            candle_body = abs(current_price - previous_close)
            candle_momentum = candle_body / atr if atr > 0 else 0
            
            # === BREAKOUT DE ALTA ===
            bullish_breakout = {
                # Preço rompeu banda superior de Bollinger
                'bb_breakout': current_price > bb_upper,
                
                # Também rompeu Keltner (mais forte)
                'kc_breakout': current_price > kc_upper,
                
                # Volume acima da média
                'volume_surge': volume_ratio >= self.volume_multiplier,
                
                # ADX indica força
                'adx_strong': adx > self.adx_min,
                
                # DI+ dominante
                'directional_positive': di_plus > di_minus,
                
                # MACD positivo e crescente
                'macd_bullish': macd_line > macd_signal and macd_histogram > 0,
                
                # RSI não em sobrecompra extrema (evita exhaustion)
                'rsi_ok': rsi < 75,
                
                # RSI mostrando força
                'rsi_strong': rsi > 55,
                
                # Vela com momentum
                'candle_momentum': candle_momentum > 0.5,
                
                # Saindo de squeeze (expansão)
                'squeeze_release': not is_squeeze or current_price > bb_upper
            }
            
            # === BREAKOUT DE BAIXA ===
            bearish_breakout = {
                # Preço rompeu banda inferior de Bollinger
                'bb_breakout': current_price < bb_lower,
                
                # Também rompeu Keltner (mais forte)
                'kc_breakout': current_price < kc_lower,
                
                # Volume acima da média
                'volume_surge': volume_ratio >= self.volume_multiplier,
                
                # ADX indica força
                'adx_strong': adx > self.adx_min,
                
                # DI- dominante
                'directional_negative': di_minus > di_plus,
                
                # MACD negativo e caindo
                'macd_bearish': macd_line < macd_signal and macd_histogram < 0,
                
                # RSI não em sobrevenda extrema
                'rsi_ok': rsi > 25,
                
                # RSI mostrando fraqueza
                'rsi_weak': rsi < 45,
                
                # Vela com momentum
                'candle_momentum': candle_momentum > 0.5,
                
                # Saindo de squeeze (expansão)
                'squeeze_release': not is_squeeze or current_price < bb_lower
            }
            
            # Pesos (breakout confirmado mais importante)
            weights_bull = {
                'bb_breakout': 2.0,
                'kc_breakout': 1.5,
                'volume_surge': 1.5,
                'adx_strong': 1.0,
                'directional_positive': 1.0,
                'macd_bullish': 1.0,
                'rsi_ok': 0.8,
                'rsi_strong': 0.8,
                'candle_momentum': 1.0,
                'squeeze_release': 1.2
            }
            
            weights_bear = {
                'bb_breakout': 2.0,
                'kc_breakout': 1.5,
                'volume_surge': 1.5,
                'adx_strong': 1.0,
                'directional_negative': 1.0,
                'macd_bearish': 1.0,
                'rsi_ok': 0.8,
                'rsi_weak': 0.8,
                'candle_momentum': 1.0,
                'squeeze_release': 1.2
            }
            
            bullish_score = self.calculate_score(bullish_breakout, weights_bull)
            bearish_score = self.calculate_score(bearish_breakout, weights_bear)
            
            # Determinar ação
            if bullish_score > bearish_score and bullish_score >= self.min_confidence:
                action = 'BUY'
                confidence = bullish_score
                reason = 'bullish_breakout_detected'
                conditions = bullish_breakout
                breakout_type = 'keltner_bb' if bullish_breakout['kc_breakout'] else 'bollinger'
                
            elif bearish_score > bullish_score and bearish_score >= self.min_confidence:
                action = 'SELL'
                confidence = bearish_score
                reason = 'bearish_breakout_detected'
                conditions = bearish_breakout
                breakout_type = 'keltner_bb' if bearish_breakout['kc_breakout'] else 'bollinger'
                
            else:
                action = 'HOLD'
                confidence = max(bullish_score, bearish_score)
                return self.create_signal(action, confidence, 'no_breakout_detected', {
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'is_squeeze': is_squeeze,
                    'bb_width_pct': round(bb_width_pct, 2)
                })
            
            # === CONFIRMAÇÃO MULTI-TIMEFRAME ===
            mtf_bonus = 0.0
            
            # Confirmar com H1
            if 'H1' in technical_analysis:
                h1_data = technical_analysis['H1']
                h1_trend = h1_data.get('trend', {})
                h1_direction = h1_trend.get('direction', 'neutral')
                h1_adx = h1_data.get('adx', {}).get('adx', 0)
                
                # H1 deve estar na mesma direção
                if (action == 'BUY' and h1_direction == 'bullish') or \
                   (action == 'SELL' and h1_direction == 'bearish'):
                    mtf_bonus += 0.1
                    # Bônus extra se H1 ADX forte
                    if h1_adx > 25:
                        mtf_bonus += 0.05
                else:
                    mtf_bonus -= 0.1
            
            # Confirmar com H4
            if 'H4' in technical_analysis:
                h4_data = technical_analysis['H4']
                h4_bb = h4_data.get('bollinger', {})
                h4_upper = h4_bb.get('upper', 0)
                h4_lower = h4_bb.get('lower', 0)
                
                # Não fazer breakout contra a tendência H4
                if action == 'BUY' and current_price > h4_upper:
                    mtf_bonus += 0.05  # Alinhado
                elif action == 'SELL' and current_price < h4_lower:
                    mtf_bonus += 0.05  # Alinhado
            
            confidence = min(max(confidence + mtf_bonus, 0.0), 1.0)
            
            # === CALCULAR SL/TP DINÂMICO ===
            sl_pips = 30  # Default
            tp_pips = 60  # Default
            
            if self.risk_calculator:
                dynamic_stops = self.risk_calculator.calculate_sl_tp(
                    symbol=symbol,
                    timeframe=primary_tf,
                    strategy='breakout',
                    atr=atr
                )
                sl_pips = dynamic_stops.get('sl_pips', sl_pips)
                tp_pips = dynamic_stops.get('tp_pips', tp_pips)
            else:
                # Fallback: usar ATR
                sl_pips = round(atr_pips * 2.0, 1)
                tp_pips = round(atr_pips * 4.0, 1)
            
            # === PROTEÇÃO CONTRA FALSE BREAKOUT ===
            # Se já houve rejeição significativa, reduzir confiança
            if action == 'BUY':
                rejection = (bb_upper - current_price) / atr if atr > 0 else 0
                if rejection > self.rejection_threshold:
                    confidence *= 0.7
                    reason = 'bullish_breakout_with_rejection'
            else:
                rejection = (current_price - bb_lower) / atr if atr > 0 else 0
                if rejection > self.rejection_threshold:
                    confidence *= 0.7
                    reason = 'bearish_breakout_with_rejection'
            
            # === CUIDADO COM NOTÍCIAS ===
            if news_analysis:
                is_blocking, _ = news_analysis.get('is_blocking', (False, None))
                if is_blocking:
                    confidence *= 0.5
                    logger.warning("Breakout detectado durante evento de notícias - cuidado!")
            
            # Construir detalhes
            details = {
                'current_price': current_price,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'bb_width_pct': round(bb_width_pct, 2),
                'kc_upper': kc_upper,
                'kc_lower': kc_lower,
                'adx': adx,
                'rsi': rsi,
                'volume_ratio': round(volume_ratio, 2),
                'atr_pips': round(atr_pips, 2),
                'is_squeeze': is_squeeze,
                'breakout_type': breakout_type,
                'conditions_met': sum(conditions.values()),
                'total_conditions': len(conditions),
                'sl_pips': sl_pips,
                'tp_pips': tp_pips,
                'timeframe': primary_tf
            }
            
            signal = self.create_signal(action, confidence, reason, details)
            
            if self.validate_signal(signal):
                logger.info(
                    f"Breakout: {action} @ {current_price:.2f} "
                    f"(tipo: {breakout_type}, confiança: {confidence:.2%}, "
                    f"vol: {volume_ratio:.1f}x, SL: {sl_pips}, TP: {tp_pips})"
                )
            
            return signal
            
        except Exception as e:
            import traceback
            logger.error(f"Erro na estratégia Breakout: {e}\n{traceback.format_exc()}")
            return self.create_signal('HOLD', 0.0, 'error')
