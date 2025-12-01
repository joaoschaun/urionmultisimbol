"""
Estratégia: Trend Following v2.0
Opera seguindo tendências fortes identificadas por múltiplos indicadores

Melhorias v2.0:
- Filtro de sessão de mercado
- SL/TP dinâmico baseado em ATR
- Detector de divergências
- Multi-timeframe analysis (H1, H4)
- Volume profile confirmation
"""

from typing import Dict, Optional
from datetime import datetime
from loguru import logger
from .base_strategy import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    """
    Estratégia de seguimento de tendência v2.0
    
    Regras:
    - ADX > 25 (tendência forte)
    - EMA 9 > EMA 21 > EMA 50 (alta) ou inverso (baixa)
    - MACD confirma direção
    - Preço acima/abaixo das médias móveis
    - RSI não em extremos (evita sobrecompra/sobrevenda)
    - Confirmação H1/H4
    - Volume acima da média
    - Sem divergência contra
    """
    
    def __init__(self, config: Dict):
        super().__init__('TrendFollowing', config)
        
        # Parâmetros configuráveis
        self.adx_threshold = config.get('adx_threshold', 30)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.min_ema_separation = config.get('min_ema_separation', 0.0001)
        
        # Novos parâmetros v2.0
        self.min_atr_pips = config.get('min_atr_pips', 5.0)
        self.max_atr_pips = config.get('max_atr_pips', 50.0)
        self.use_session_filter = config.get('use_session_filter', True)
        self.use_divergence = config.get('use_divergence', True)
        self.min_volume_ratio = config.get('min_volume_ratio', 1.0)
        
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
            from ..analysis.divergence_detector import get_divergence_detector
            self.divergence_detector = get_divergence_detector()
        except ImportError:
            self.divergence_detector = None
            
        try:
            from ..core.dynamic_risk_calculator import get_dynamic_calculator
            self.risk_calculator = get_dynamic_calculator()
        except ImportError:
            self.risk_calculator = None
    
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
            # Usar timeframe principal (H1 para trend following)
            primary_tf = 'H1' if 'H1' in technical_analysis else 'M15'
            if primary_tf not in technical_analysis:
                logger.warning(f"{primary_tf} não disponível para TrendFollowing")
                return self.create_signal('HOLD', 0.0, 'no_data')
            
            tf_data = technical_analysis[primary_tf]
            symbol = tf_data.get('symbol', 'XAUUSD')
            
            # === FILTRO DE SESSÃO ===
            if self.use_session_filter and self.session_manager:
                session_info = self.session_manager.get_current_session()
                session_quality = self.session_manager.get_session_quality()
                
                # Trend Following funciona melhor em London/NY
                min_quality = 2  # moderate
                if session_quality.value < min_quality:
                    return self.create_signal('HOLD', 0.0, 'session_quality_low', {
                        'session': session_info['current_session'],
                        'quality': session_quality.name
                    })
            
            # Extrair indicadores
            current_price = tf_data.get('current_price', 0)
            rsi = tf_data.get('rsi', 50)
            macd_data = tf_data.get('macd', {})
            adx_data = tf_data.get('adx', {})
            ema = tf_data.get('ema', {})
            atr_raw = tf_data.get('atr', 0)  # Pode ser float ou dict
            volume_data = tf_data.get('volume', {})
            
            # Valores necessários
            adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else 0
            di_plus = adx_data.get('di_plus', 0) if isinstance(adx_data, dict) else 0
            di_minus = adx_data.get('di_minus', 0) if isinstance(adx_data, dict) else 0
            
            macd_line = macd_data.get('macd', 0) if isinstance(macd_data, dict) else 0
            macd_signal = macd_data.get('signal', 0) if isinstance(macd_data, dict) else 0
            macd_histogram = macd_data.get('histogram', 0) if isinstance(macd_data, dict) else 0
            
            ema_9 = ema.get('ema_9', 0) if isinstance(ema, dict) else 0
            ema_21 = ema.get('ema_21', 0) if isinstance(ema, dict) else 0
            ema_50 = ema.get('ema_50', 0) if isinstance(ema, dict) else 0
            ema_200 = ema.get('ema_200', ema_50) if isinstance(ema, dict) else ema_50
            
            # ATR pode vir como float diretamente ou como dict
            atr = atr_raw if isinstance(atr_raw, (int, float)) else atr_raw.get('atr', 0)
            atr_pips = atr / 0.1 if symbol == 'XAUUSD' else atr / 0.0001
            
            volume_ratio = volume_data.get('ratio', 1.0) if isinstance(volume_data, dict) else 1.0
            
            # Verificar se há dados suficientes
            if not all([adx, ema_9, ema_21, ema_50, current_price]):
                return self.create_signal('HOLD', 0.0, 'insufficient_data')
            
            # === FILTRO DE VOLATILIDADE ATR ===
            if atr_pips < self.min_atr_pips:
                return self.create_signal('HOLD', 0.0, 'volatility_too_low', {
                    'atr_pips': round(atr_pips, 2),
                    'min_required': self.min_atr_pips
                })
            if atr_pips > self.max_atr_pips:
                return self.create_signal('HOLD', 0.0, 'volatility_too_high', {
                    'atr_pips': round(atr_pips, 2),
                    'max_allowed': self.max_atr_pips
                })
            
            # === DETECÇÃO DE DIVERGÊNCIA ===
            divergence_penalty = 0.0
            divergence_info = None
            
            if self.use_divergence and self.divergence_detector:
                div_signal = self.divergence_detector.get_trade_signal(
                    symbol, primary_tf, tf_data
                )
                if div_signal and div_signal.get('signal') != 'NEUTRAL':
                    divergence_info = div_signal
                    # Se há divergência contra a tendência, penalizar
                    # (divergência bullish enquanto tendência é bearish, etc)
            
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
                'price_above_ema': current_price > ema_9 and current_price > ema_50,
                
                # MACD positivo e crescendo
                'macd_positive': macd_line > macd_signal and macd_histogram > 0,
                
                # RSI não em sobrecompra
                'rsi_not_overbought': rsi < self.rsi_overbought,
                
                # RSI em zona de tendência (40-70)
                'rsi_trending': 40 < rsi < 70,
                
                # Volume confirmando
                'volume_confirmation': volume_ratio >= self.min_volume_ratio,
                
                # Preço acima da EMA 200 (tendência macro)
                'above_ema_200': current_price > ema_200
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
                'price_below_ema': current_price < ema_9 and current_price < ema_50,
                
                # MACD negativo e caindo
                'macd_negative': macd_line < macd_signal and macd_histogram < 0,
                
                # RSI não em sobrevenda
                'rsi_not_oversold': rsi > self.rsi_oversold,
                
                # RSI em zona de tendência (30-60)
                'rsi_trending': 30 < rsi < 60,
                
                # Volume confirmando
                'volume_confirmation': volume_ratio >= self.min_volume_ratio,
                
                # Preço abaixo da EMA 200 (tendência macro)
                'below_ema_200': current_price < ema_200
            }
            
            # Calcular scores
            bullish_score = self.calculate_score(bullish_conditions)
            bearish_score = self.calculate_score(bearish_conditions)
            
            # Aplicar penalidade de divergência
            if divergence_info:
                div_type = divergence_info.get('divergence_type', '')
                if 'bullish' in div_type.lower() and bearish_score > bullish_score:
                    # Divergência bullish contradiz tendência bearish
                    bearish_score *= 0.7
                elif 'bearish' in div_type.lower() and bullish_score > bearish_score:
                    # Divergência bearish contradiz tendência bullish
                    bullish_score *= 0.7
            
            # Determinar ação
            if bullish_score > bearish_score and bullish_score >= self.min_confidence:
                action = 'BUY'
                confidence = bullish_score
                reason = 'strong_uptrend_detected'
                conditions = bullish_conditions
                
            elif bearish_score > bullish_score and bearish_score >= self.min_confidence:
                action = 'SELL'
                confidence = bearish_score
                reason = 'strong_downtrend_detected'
                conditions = bearish_conditions
                
            else:
                action = 'HOLD'
                confidence = max(bullish_score, bearish_score)
                reason = 'no_clear_trend'
                return self.create_signal(action, confidence, reason, {
                    'bullish_score': bullish_score,
                    'bearish_score': bearish_score,
                    'adx': adx
                })
            
            # === CONFIRMAÇÃO MULTI-TIMEFRAME ===
            mtf_bonus = 0.0
            
            # Confirmar com H4
            if 'H4' in technical_analysis:
                h4_data = technical_analysis['H4']
                h4_ema = h4_data.get('ema', {})
                h4_ema_9 = h4_ema.get('ema_9', 0)
                h4_ema_21 = h4_ema.get('ema_21', 0)
                
                if action == 'BUY' and h4_ema_9 > h4_ema_21:
                    mtf_bonus += 0.05
                elif action == 'SELL' and h4_ema_9 < h4_ema_21:
                    mtf_bonus += 0.05
                else:
                    mtf_bonus -= 0.05
            
            # Confirmar com D1
            if 'D1' in technical_analysis:
                d1_data = technical_analysis['D1']
                d1_trend = d1_data.get('trend', {})
                d1_direction = d1_trend.get('direction', 'neutral')
                
                if (action == 'BUY' and d1_direction == 'bullish') or \
                   (action == 'SELL' and d1_direction == 'bearish'):
                    mtf_bonus += 0.05
            
            confidence = min(confidence + mtf_bonus, 1.0)
            
            # === CALCULAR SL/TP DINÂMICO ===
            sl_pips = 50  # Default
            tp_pips = 100  # Default
            
            if self.risk_calculator:
                dynamic_stops = self.risk_calculator.calculate_sl_tp(
                    symbol=symbol,
                    timeframe=primary_tf,
                    strategy='trend_following',
                    atr=atr
                )
                sl_pips = dynamic_stops.get('sl_pips', sl_pips)
                tp_pips = dynamic_stops.get('tp_pips', tp_pips)
            else:
                # Fallback: usar ATR
                sl_pips = round(atr_pips * 2.5, 1)
                tp_pips = round(atr_pips * 5.0, 1)
            
            # === AJUSTE COM NOTÍCIAS ===
            if news_analysis:
                news_sentiment = news_analysis.get('sentiment', {})
                news_overall = news_sentiment.get('overall_sentiment', 'neutral')
                
                if (action == 'BUY' and news_overall == 'bullish') or \
                   (action == 'SELL' and news_overall == 'bearish'):
                    confidence = min(confidence * 1.05, 1.0)
                elif news_overall != 'neutral':
                    confidence *= 0.95
            
            # Construir detalhes
            details = {
                'current_price': current_price,
                'adx': adx,
                'di_plus': di_plus,
                'di_minus': di_minus,
                'ema_9': ema_9,
                'ema_21': ema_21,
                'ema_50': ema_50,
                'ema_200': ema_200,
                'rsi': rsi,
                'macd_histogram': macd_histogram,
                'atr_pips': round(atr_pips, 2),
                'volume_ratio': round(volume_ratio, 2),
                'conditions_met': sum(conditions.values()),
                'total_conditions': len(conditions),
                'sl_pips': sl_pips,
                'tp_pips': tp_pips,
                'timeframe': primary_tf
            }
            
            if divergence_info:
                details['divergence'] = divergence_info
            
            signal = self.create_signal(action, confidence, reason, details)
            
            if self.validate_signal(signal):
                logger.info(
                    f"TrendFollowing: {action} @ {current_price:.2f} "
                    f"(confiança: {confidence:.2%}, ADX: {adx:.1f}, "
                    f"SL: {sl_pips}, TP: {tp_pips})"
                )
            
            return signal
            
        except Exception as e:
            import traceback
            logger.error(f"Erro na estratégia TrendFollowing: {e}\n{traceback.format_exc()}")
            return self.create_signal('HOLD', 0.0, 'error')
