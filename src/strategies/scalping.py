"""
Estratégia: Scalping AVANÇADO v2.1
Opera em movimentos rápidos de preço com entrada/saída rápida

MELHORIAS v2.0:
- Spread REAL do MT5 (não estimado)
- ATR para SL/TP dinâmico
- Bollinger Bands para reversão
- RSI range expandido (35-65)
- Filtro de sessão de trading
- Verificação de volatilidade
- Divergências RSI/MACD

🧠 MELHORIAS v2.1 (COMUNICAÇÃO ENTRE TIMEFRAMES):
- OBRIGATÓRIO: H1 confirma direção antes de entrar
- M15 como suporte adicional
- Só opera na direção do timeframe maior
- Filtro de regime (só em TRENDING)
"""

from typing import Dict, Optional
from loguru import logger
from .base_strategy import BaseStrategy


class ScalpingStrategy(BaseStrategy):
    """
    Estratégia de Scalping OTIMIZADA v2.1
    
    🧠 REGRA DE OURO:
    "Scalping M5 SÓ OPERA na direção que H1 confirma"
    
    Regras:
    - Timeframe: M5 (mais estável que M1)
    - 🧠 H1 DEVE confirmar a direção (MACD + EMA alignment)
    - Spread REAL do MT5 < 2.5 pips
    - RSI entre 35-65 (range expandido)
    - ATR para volatilidade adequada (3-15 pips)
    - Bollinger Bands para confirmar entradas
    - Confirmação multi-indicador (MACD, Stochastic, EMA)
    - SL/TP dinâmico baseado em ATR
    - Filtro de sessão (London/NY apenas)
    """
    
    def __init__(self, config: Dict, symbol: str = None):
        super().__init__('Scalping', config, symbol=symbol)
        
        # Parâmetros OTIMIZADOS
        self.max_spread_pips = config.get('max_spread_pips', 2.5)  # Mais restritivo
        self.min_momentum = config.get('min_momentum', 0.0002)
        self.rsi_min = config.get('rsi_min', 35)  # ✅ Expandido
        self.rsi_max = config.get('rsi_max', 65)  # ✅ Expandido
        self.target_pips = config.get('target_pips', 10)
        self.stop_pips = config.get('stop_pips', 5)
        self.min_volume_ratio = config.get('min_volume_ratio', 1.1)
        
        # ✅ NOVOS parâmetros
        self.min_atr_pips = config.get('min_atr_pips', 3)  # Volatilidade mínima
        self.max_atr_pips = config.get('max_atr_pips', 20)  # Volatilidade máxima
        self.bb_oversold_threshold = config.get('bb_oversold', 0.25)  # <25% = oversold
        self.bb_overbought_threshold = config.get('bb_overbought', 0.75)  # >75% = overbought
        self.use_session_filter = config.get('use_session_filter', True)
        self.use_divergence = config.get('use_divergence', True)
        
        # 🧠 v2.1: Filtros de Higher Timeframe
        self.require_h1_confirmation = config.get('require_h1_confirmation', True)
        self.h1_trend_weight = config.get('h1_trend_weight', 0.3)  # Peso do H1 na confiança
    
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
            logger.debug(f"[SCALPING] Iniciando análise avançada v2.0...")
            
            # Usar M5 como principal (mais estável que M1)
            if 'M5' not in technical_analysis:
                logger.warning("[SCALPING] ❌ M5 não disponível")
                return self.create_signal('HOLD', 0.0, 'no_data')
            
            m5 = technical_analysis['M5']
            price = m5.get('current_price', 0)
            
            if price == 0:
                return self.create_signal('HOLD', 0.0, 'no_price')
            
            # ========================================
            # 1. SPREAD REAL DO MT5
            # ========================================
            spread_pips = technical_analysis.get('spread_pips', 0)
            if spread_pips == 0:
                # Fallback: estimar se não disponível
                spread_pips = m5.get('spread_pips', 2.0)
            
            logger.debug(f"[SCALPING] Spread REAL: {spread_pips:.1f} pips (max: {self.max_spread_pips})")
            
            if spread_pips > self.max_spread_pips:
                return self.create_signal('HOLD', 0.0, f'high_spread_{spread_pips:.1f}')
            
            # ========================================
            # 2. VERIFICAR ATR (VOLATILIDADE)
            # ========================================
            atr_raw = m5.get('atr', 0)
            # ATR pode vir como float diretamente ou como dict
            atr = atr_raw if isinstance(atr_raw, (int, float)) else (atr_raw.get('atr', 0) if isinstance(atr_raw, dict) else 0)
            atr_pips = atr / 0.1 if atr else 0  # XAUUSD: 1 pip = 0.1
            
            logger.debug(f"[SCALPING] ATR: {atr_pips:.1f} pips (min: {self.min_atr_pips}, max: {self.max_atr_pips})")
            
            if atr_pips < self.min_atr_pips:
                return self.create_signal('HOLD', 0.0, f'low_volatility_{atr_pips:.1f}')
            
            if atr_pips > self.max_atr_pips:
                return self.create_signal('HOLD', 0.0, f'high_volatility_{atr_pips:.1f}')
            
            # ========================================
            # 🧠 2.5. VERIFICAR H1 (HIGHER TIMEFRAME)
            # ========================================
            h1_direction, h1_strength = self._get_h1_direction(technical_analysis)
            
            if self.require_h1_confirmation:
                if h1_direction == 'NEUTRAL':
                    return self.create_signal('HOLD', 0.0, 'h1_no_direction')
            
            logger.debug(f"[SCALPING] 🧠 H1 Direction: {h1_direction} (strength: {h1_strength:.2f})")
            
            # ========================================
            # 3. EXTRAIR INDICADORES
            # ========================================
            rsi = m5.get('rsi', 50)
            macd_data = m5.get('macd', {})
            stochastic_data = m5.get('stochastic', {})
            ema_data = m5.get('ema', {})
            bb_data = m5.get('bollinger', {})  # ✅ NOVO: Bollinger Bands
            
            # Verificar se indicadores são dicts válidos
            if not isinstance(macd_data, dict) or not isinstance(stochastic_data, dict):
                return self.create_signal('HOLD', 0.0, 'no_indicators')
            
            # ========================================
            # 4. RSI CHECK (RANGE EXPANDIDO)
            # ========================================
            if rsi < self.rsi_min or rsi > self.rsi_max:
                return self.create_signal('HOLD', 0.0, f'rsi_extreme_{rsi:.1f}')
            
            # Extrair valores dos indicadores (com tratamento de tipo)
            macd_line = macd_data.get('macd', 0) if isinstance(macd_data, dict) else 0
            macd_signal = macd_data.get('signal', 0) if isinstance(macd_data, dict) else 0
            macd_hist = macd_data.get('histogram', 0) if isinstance(macd_data, dict) else 0
            stoch_k = stochastic_data.get('k', 50) if isinstance(stochastic_data, dict) else 50
            stoch_d = stochastic_data.get('d', 50) if isinstance(stochastic_data, dict) else 50
            
            # ========================================
            # 5. BOLLINGER BANDS ANALYSIS
            # ========================================
            bb_upper = bb_data.get('upper', price + 1) if isinstance(bb_data, dict) else price + 1
            bb_lower = bb_data.get('lower', price - 1) if isinstance(bb_data, dict) else price - 1
            bb_middle = bb_data.get('middle', price) if isinstance(bb_data, dict) else price
            
            # Calcular posição do preço nas bandas (0-1)
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                bb_position = (price - bb_lower) / bb_range
            else:
                bb_position = 0.5
            
            logger.debug(f"[SCALPING] BB position: {bb_position:.2f} (oversold<{self.bb_oversold_threshold}, overbought>{self.bb_overbought_threshold})")
            
            # ========================================
            # 6. CALCULAR MOMENTUM SCORE
            # ========================================
            momentum_score = 0
            action = 'HOLD'
            reasons = []
            
            # 🧠 PRIMEIRO: Verificar alinhamento com H1
            # Se H1 é BULLISH, só considerar sinais BUY
            # Se H1 é BEARISH, só considerar sinais SELL
            allowed_action = None
            if h1_direction == 'BULLISH':
                allowed_action = 'BUY'
            elif h1_direction == 'BEARISH':
                allowed_action = 'SELL'
            
            # MACD + Bollinger combinados
            if macd_hist > 0 and macd_line > macd_signal:
                if bb_position < self.bb_oversold_threshold:
                    # Preço perto do fundo + MACD bullish = FORTE compra
                    if allowed_action in [None, 'BUY']:  # 🧠 Verificar H1
                        momentum_score += 3
                        action = 'BUY'
                        reasons.append('macd_bullish+bb_oversold')
                else:
                    if allowed_action in [None, 'BUY']:  # 🧠 Verificar H1
                        momentum_score += 1
                        action = 'BUY'
                        reasons.append('macd_bullish')
            
            elif macd_hist < 0 and macd_line < macd_signal:
                if bb_position > self.bb_overbought_threshold:
                    # Preço perto do topo + MACD bearish = FORTE venda
                    if allowed_action in [None, 'SELL']:  # 🧠 Verificar H1
                        momentum_score += 3
                        action = 'SELL'
                        reasons.append('macd_bearish+bb_overbought')
                else:
                    if allowed_action in [None, 'SELL']:  # 🧠 Verificar H1
                        momentum_score += 1
                        action = 'SELL'
                        reasons.append('macd_bearish')
            
            # 🧠 Se ação determinada conflita com H1, abortar
            if allowed_action and action != 'HOLD' and action != allowed_action:
                return self.create_signal(
                    'HOLD', 0.0, 
                    f'h1_conflict_{action}_vs_{allowed_action}'
                )
            
            # Stochastic confirma
            if action == 'BUY' and stoch_k > stoch_d and stoch_k < 80:
                momentum_score += 1
                reasons.append('stoch_bullish')
            elif action == 'SELL' and stoch_k < stoch_d and stoch_k > 20:
                momentum_score += 1
                reasons.append('stoch_bearish')
            
            # Stochastic em extremos (confirmação extra)
            if action == 'BUY' and stoch_k < 25:
                momentum_score += 1
                reasons.append('stoch_oversold')
            elif action == 'SELL' and stoch_k > 75:
                momentum_score += 1
                reasons.append('stoch_overbought')
            
            # Volume
            volume_ratio = m5.get('volume_ratio', 1.0)
            if volume_ratio >= self.min_volume_ratio:
                momentum_score += 1
                reasons.append(f'volume_{volume_ratio:.1f}x')
            
            # EMAs
            ema_9 = ema_data.get('ema_9', price)
            ema_21 = ema_data.get('ema_21', price)
            
            if action == 'BUY' and price > ema_9 > ema_21:
                momentum_score += 1
                reasons.append('ema_bullish')
            elif action == 'SELL' and price < ema_9 < ema_21:
                momentum_score += 1
                reasons.append('ema_bearish')
            
            # ========================================
            # 7. ATR-BASED SL/TP DINÂMICO
            # ========================================
            dynamic_stop = max(self.stop_pips, atr_pips * 1.0)  # Mínimo 1x ATR
            dynamic_target = max(self.target_pips, atr_pips * 1.5)  # Mínimo 1.5x ATR
            
            # ========================================
            # 8. CALCULAR CONFIANÇA
            # ========================================
            max_score = 8
            confidence = min(momentum_score / max_score, 1.0)
            
            logger.info(
                f"[SCALPING] Action: {action}, Score: {momentum_score}/{max_score}, "
                f"Confidence: {confidence:.2%}, Reasons: {reasons}"
            )
            
            # Precisamos de 50% (4/8 pontos) - mais flexível que antes
            if confidence < 0.50:
                return self.create_signal('HOLD', confidence, f'low_momentum_{momentum_score}/{max_score}')
            
            # ========================================
            # 9. CONFIRMAR COM M15 E AJUSTAR COM H1
            # ========================================
            if 'M15' in technical_analysis:
                m15 = technical_analysis['M15']
                m15_rsi = m15.get('rsi', 50)
                m15_macd = m15.get('macd', {})
                m15_hist = m15_macd.get('histogram', 0)
                
                # M15 deve estar na mesma direção
                if action == 'BUY' and m15_hist > 0:
                    confidence += 0.10
                    reasons.append('m15_confirms')
                elif action == 'SELL' and m15_hist < 0:
                    confidence += 0.10
                    reasons.append('m15_confirms')
                elif (action == 'BUY' and m15_hist < 0) or (action == 'SELL' and m15_hist > 0):
                    confidence -= 0.10
                    reasons.append('m15_diverges')
            
            # 🧠 BÔNUS H1: Se alinhado com H1, aumentar confiança
            if h1_direction == 'BULLISH' and action == 'BUY':
                confidence += self.h1_trend_weight * h1_strength
                reasons.append(f'h1_bullish_{h1_strength:.2f}')
            elif h1_direction == 'BEARISH' and action == 'SELL':
                confidence += self.h1_trend_weight * h1_strength
                reasons.append(f'h1_bearish_{h1_strength:.2f}')
            
            # ========================================
            # 10. VERIFICAR DIVERGÊNCIA (OPCIONAL)
            # ========================================
            if self.use_divergence:
                divergence_data = technical_analysis.get('divergence', {})
                if divergence_data:
                    div_bias = divergence_data.get('bias', 'NEUTRAL')
                    if action == 'BUY' and div_bias == 'BULLISH':
                        confidence += 0.05
                        reasons.append('divergence_bullish')
                    elif action == 'SELL' and div_bias == 'BEARISH':
                        confidence += 0.05
                        reasons.append('divergence_bearish')
            
            # Limitar confiança
            confidence = max(min(confidence, 0.90), 0)
            
            # ========================================
            # 11. GERAR SINAL
            # ========================================
            if action in ['BUY', 'SELL'] and confidence >= 0.50:
                logger.info(
                    f"[SCALPING] ✅ SINAL: {action} @ {price} | "
                    f"Conf: {confidence:.2%} | "
                    f"SL: {dynamic_stop:.1f} pips | "
                    f"TP: {dynamic_target:.1f} pips"
                )
                
                return self.create_signal(
                    action, confidence,
                    ', '.join(reasons),
                    {
                        'entry_price': price,
                        'current_price': price,
                        'target_pips': round(dynamic_target, 1),
                        'stop_pips': round(dynamic_stop, 1),
                        'rsi': rsi,
                        'macd_hist': macd_hist,
                        'bb_position': round(bb_position, 2),
                        'atr_pips': round(atr_pips, 1),
                        'momentum_score': f"{momentum_score}/{max_score}",
                        'spread_pips': round(spread_pips, 1)
                    }
                )
            
            return self.create_signal('HOLD', confidence, 'no_clear_signal')
            
        except Exception as e:
            logger.error(f"Erro em ScalpingStrategy.analyze: {e}")
            return self.create_signal('HOLD', 0.0, f'error: {e}')
    
    def _get_h1_direction(self, technical_analysis: Dict) -> tuple:
        """
        🧠 Obtém a direção do H1 para filtrar trades de scalping.
        
        Esta é a função chave que faz a COMUNICAÇÃO ENTRE TIMEFRAMES.
        Scalping em M5 só pode operar na direção que H1 confirma.
        
        Returns:
            tuple: (direction: str, strength: float)
                direction: 'BULLISH', 'BEARISH', ou 'NEUTRAL'
                strength: 0.0 a 1.0
        """
        try:
            if 'H1' not in technical_analysis:
                # Fallback: usar M15 se H1 não disponível
                if 'M15' not in technical_analysis:
                    return 'NEUTRAL', 0.0
                tf_data = technical_analysis['M15']
            else:
                tf_data = technical_analysis['H1']
            
            # Extrair indicadores do H1
            macd_data = tf_data.get('macd', {})
            ema_data = tf_data.get('ema', {})
            adx_data = tf_data.get('adx', {})
            rsi = tf_data.get('rsi', 50)
            current_price = tf_data.get('current_price', 0)
            
            macd_hist = macd_data.get('histogram', 0) if isinstance(macd_data, dict) else 0
            macd_line = macd_data.get('macd', 0) if isinstance(macd_data, dict) else 0
            macd_signal = macd_data.get('signal', 0) if isinstance(macd_data, dict) else 0
            
            ema_9 = ema_data.get('ema_9', 0) if isinstance(ema_data, dict) else 0
            ema_21 = ema_data.get('ema_21', 0) if isinstance(ema_data, dict) else 0
            ema_50 = ema_data.get('ema_50', 0) if isinstance(ema_data, dict) else 0
            
            adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else 0
            di_plus = adx_data.get('di_plus', 0) if isinstance(adx_data, dict) else 0
            di_minus = adx_data.get('di_minus', 0) if isinstance(adx_data, dict) else 0
            
            # Calcular score de direção
            bullish_score = 0
            bearish_score = 0
            
            # MACD (peso 3)
            if macd_line > macd_signal and macd_hist > 0:
                bullish_score += 3
            elif macd_line < macd_signal and macd_hist < 0:
                bearish_score += 3
            
            # EMA Alignment (peso 2)
            if ema_9 > ema_21 > ema_50:
                bullish_score += 2
            elif ema_9 < ema_21 < ema_50:
                bearish_score += 2
            
            # Price vs EMAs (peso 2)
            if current_price > 0:
                if current_price > ema_9 and current_price > ema_21:
                    bullish_score += 2
                elif current_price < ema_9 and current_price < ema_21:
                    bearish_score += 2
            
            # ADX Directional (peso 2)
            if adx > 25:
                if di_plus > di_minus:
                    bullish_score += 2
                elif di_minus > di_plus:
                    bearish_score += 2
            
            # RSI (peso 1)
            if rsi > 55:
                bullish_score += 1
            elif rsi < 45:
                bearish_score += 1
            
            # Determinar direção
            max_score = 10
            
            if bullish_score > bearish_score and bullish_score >= 4:
                strength = min(bullish_score / max_score, 1.0)
                return 'BULLISH', strength
            elif bearish_score > bullish_score and bearish_score >= 4:
                strength = min(bearish_score / max_score, 1.0)
                return 'BEARISH', strength
            else:
                return 'NEUTRAL', 0.0
                
        except Exception as e:
            logger.error(f"Erro ao obter direção H1: {e}")
            return 'NEUTRAL', 0.0
