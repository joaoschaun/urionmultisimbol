"""
Estratégia: CATAMILHO Ultra-Ativo v1.0
Scalping de alta frequência com mean reversion

🎯 CARACTERÍSTICAS:
- Timeframe principal: M1
- Timeframe filtro: M5 (contexto)
- Objetivo: 3-6 pips líquidos por trade
- Duração média: 1-5 minutos
- Frequência: 30-100 trades/dia
- Pares: EURUSD, GBPUSD, USDJPY (spreads baixos)

📐 ARQUITETURA:
- Filtro M5: ADX < 28 (mercado lateral), ATR normal, preço perto da EMA50
- Setup M1: Bollinger touch + RSI extremo + candle de reversão
- Gestão: TP 5 pips, SL 8 pips, trailing após 3 pips

🔧 MÁQUINA DE ESTADOS:
IDLE → ARMED → IN_TRADE → COOLDOWN → IDLE

Autor: João Schaun
Versão: 1.0
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import numpy as np

from .base_strategy import BaseStrategy


class CatamilhoStrategy(BaseStrategy):
    """
    Estratégia Catamilho - Scalping M1 com filtro M5
    
    🎯 REGRAS DE OURO:
    1. M5 deve estar em range (ADX < 28)
    2. M1 toca Bollinger + RSI extremo + candle de reversão
    3. Só opera em sessões de alta liquidez
    4. Risk 0.3% por trade, max 2% loss diário
    """
    
    def __init__(self, config: Dict, symbol: str = None):
        super().__init__('Catamilho', config, symbol=symbol)
        
        # =====================================================
        # PARÂMETROS DE CONTEXTO M5
        # =====================================================
        self.adx_max = config.get('adx_max', 28.0)
        self.atr_min = config.get('atr_min', 0.0005)
        self.atr_max = config.get('atr_max', 0.0025)
        self.ema_distance_max_pips = config.get('ema_distance_max_pips', 30.0)
        
        # =====================================================
        # PARÂMETROS DE SETUP M1
        # =====================================================
        self.ema_fast = config.get('ema_fast', 8)
        self.ema_mid = config.get('ema_mid', 21)
        self.ema_slow = config.get('ema_slow', 50)
        self.bb_period = config.get('bb_period', 20)
        self.bb_deviation = config.get('bb_deviation', 2.0)
        self.rsi_period = config.get('rsi_period', 9)
        self.rsi_oversold = config.get('rsi_oversold', 30.0)
        self.rsi_overbought = config.get('rsi_overbought', 70.0)
        self.volume_period = config.get('volume_period', 10)
        
        # =====================================================
        # PARÂMETROS DE ENTRADA
        # =====================================================
        self.spread_max_pips = config.get('spread_max_pips', 1.5)
        self.wick_min_percent = config.get('wick_min_percent', 40.0)
        self.body_max_pips = config.get('body_max_pips', 2.0)
        
        # =====================================================
        # PARÂMETROS DE SAÍDA
        # =====================================================
        self.tp_pips = config.get('tp_pips', 5.0)
        self.sl_pips = config.get('sl_pips', 8.0)
        self.trailing_start_pips = config.get('trailing_start_pips', 3.0)
        self.trailing_step_pips = config.get('trailing_step_pips', 1.0)
        self.breakeven_pips = config.get('breakeven_pips', 3.0)
        self.max_candles_in_trade = config.get('max_candles_in_trade', 5)
        
        # =====================================================
        # PARÂMETROS DE RISCO
        # =====================================================
        self.risk_per_trade = config.get('risk_per_trade', 0.003)  # 0.3%
        self.max_loss_day = config.get('max_loss_day', -0.02)  # -2%
        self.max_trades_day = config.get('max_trades_day', 100)
        self.max_losses_row = config.get('max_losses_row', 4)
        self.max_trades_hour = config.get('max_trades_hour', 25)
        self.cooldown_after_loss_seconds = config.get('cooldown_after_loss_seconds', 15)
        
        # =====================================================
        # HORÁRIOS DE OPERAÇÃO (UTC)
        # =====================================================
        self.session_start_hour = config.get('session_start_hour', 7)
        self.session_end_hour = config.get('session_end_hour', 20)
        
        # =====================================================
        # AUTO-ATIVAÇÃO INTELIGENTE
        # =====================================================
        self.auto_mode = config.get('auto_mode', True)  # Só opera quando viável
        
        # Horários ótimos por sessão (UTC)
        self.london_start = config.get('london_start', 7)
        self.london_end = config.get('london_end', 11)
        self.ny_start = config.get('ny_start', 13)
        self.ny_end = config.get('ny_end', 17)
        self.overlap_start = config.get('overlap_start', 13)
        self.overlap_end = config.get('overlap_end', 16)
        
        # Dias da semana (0=segunda, 4=sexta)
        self.avoid_monday_before_hour = config.get('avoid_monday_before_hour', 9)
        self.avoid_friday_after_hour = config.get('avoid_friday_after_hour', 18)
        
        # Limites dinâmicos de spread por volatilidade
        self.spread_max_london = config.get('spread_max_london', 1.2)
        self.spread_max_ny = config.get('spread_max_ny', 1.3)
        self.spread_max_overlap = config.get('spread_max_overlap', 1.0)  # Mais restritivo no overlap
        self.spread_max_asia = config.get('spread_max_asia', 2.0)  # Mais flexível na Ásia
        
        # Condições mínimas de mercado
        self.min_liquidity_ratio = config.get('min_liquidity_ratio', 0.7)  # 70% da liquidez normal
        self.volatility_sweet_spot_min = config.get('volatility_sweet_spot_min', 0.3)  # % do ATR médio
        self.volatility_sweet_spot_max = config.get('volatility_sweet_spot_max', 1.5)  # % do ATR médio
        
        # Contadores de performance para auto-ajuste
        self.trades_today = 0
        self.wins_today = 0
        self.losses_today = 0
        self.pnl_today = 0.0
        self.last_reset_date: Optional[datetime] = None
        
        # =====================================================
        # ESTADO INTERNO
        # =====================================================
        self.state = 'IDLE'  # IDLE, ARMED, IN_TRADE, COOLDOWN
        self.last_signal_time: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None
        self.viability_score = 0.0  # Score de viabilidade atual (0-100)
        self.viability_reason = "not_checked"
        
        logger.info(
            f"🌽 Catamilho inicializada para {self.symbol} | "
            f"ADX<{self.adx_max} | RSI({self.rsi_period}) | "
            f"TP:{self.tp_pips}p SL:{self.sl_pips}p | "
            f"Auto-Mode: {'ON' if self.auto_mode else 'OFF'}"
        )
    
    def _get_pip_value(self) -> float:
        """Retorna o valor do pip para o símbolo"""
        if 'JPY' in self.symbol:
            return 0.01
        elif 'XAU' in self.symbol:
            return 0.01  # Gold: 1 pip = $0.01
        else:
            return 0.0001  # Majors
    
    def _calculate_ema(self, closes: list, period: int) -> float:
        """Calcula EMA manualmente"""
        if len(closes) < period:
            return closes[-1] if closes else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period
        
        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_rsi(self, closes: list, period: int = 14) -> float:
        """Calcula RSI"""
        if len(closes) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return 50.0
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_bollinger(self, closes: list, period: int = 20, deviation: float = 2.0) -> tuple:
        """Calcula Bollinger Bands"""
        if len(closes) < period:
            return closes[-1], closes[-1], closes[-1]
        
        recent = closes[-period:]
        sma = sum(recent) / period
        
        variance = sum((x - sma) ** 2 for x in recent) / period
        std = variance ** 0.5
        
        upper = sma + (deviation * std)
        lower = sma - (deviation * std)
        
        return upper, sma, lower
    
    def _calculate_adx(self, highs: list, lows: list, closes: list, period: int = 14) -> float:
        """Calcula ADX simplificado"""
        if len(closes) < period + 1:
            return 0.0
        
        try:
            # True Range
            tr_list = []
            for i in range(1, len(closes)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
                tr_list.append(tr)
            
            if len(tr_list) < period:
                return 0.0
            
            # +DM e -DM
            plus_dm = []
            minus_dm = []
            
            for i in range(1, len(highs)):
                up_move = highs[i] - highs[i-1]
                down_move = lows[i-1] - lows[i]
                
                if up_move > down_move and up_move > 0:
                    plus_dm.append(up_move)
                else:
                    plus_dm.append(0)
                
                if down_move > up_move and down_move > 0:
                    minus_dm.append(down_move)
                else:
                    minus_dm.append(0)
            
            # ATR
            atr = sum(tr_list[-period:]) / period
            if atr == 0:
                return 0.0
            
            # +DI e -DI
            plus_di = (sum(plus_dm[-period:]) / period) / atr * 100
            minus_di = (sum(minus_dm[-period:]) / period) / atr * 100
            
            # DX
            if plus_di + minus_di == 0:
                return 0.0
            
            dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
            
            return dx
            
        except Exception as e:
            logger.error(f"Erro ao calcular ADX: {e}")
            return 0.0
    
    def _calculate_atr(self, highs: list, lows: list, closes: list, period: int = 14) -> float:
        """Calcula ATR"""
        if len(closes) < period + 1:
            return 0.0
        
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return 0.0
        
        return sum(tr_list[-period:]) / period
    
    def _get_current_session(self) -> str:
        """Identifica a sessão de mercado atual"""
        now = datetime.utcnow()
        hour = now.hour
        
        # Overlap Londres/NY (melhor liquidez)
        if self.overlap_start <= hour < self.overlap_end:
            return 'OVERLAP'
        # Sessão de Londres
        elif self.london_start <= hour < self.london_end:
            return 'LONDON'
        # Sessão de Nova York
        elif self.ny_start <= hour < self.ny_end:
            return 'NEW_YORK'
        # Sessão da Ásia (baixa liquidez para majors)
        elif hour >= 23 or hour < 7:
            return 'ASIA'
        else:
            return 'TRANSITION'
    
    def _check_day_viability(self) -> tuple:
        """
        Verifica se o dia é viável para operações
        
        Returns:
            tuple: (is_viable: bool, reason: str, score_adjustment: int)
        """
        now = datetime.utcnow()
        weekday = now.weekday()  # 0=segunda, 4=sexta, 5=sábado, 6=domingo
        hour = now.hour
        
        # Sábado e Domingo: mercado fechado
        if weekday >= 5:
            return False, 'weekend', -100
        
        # Segunda-feira cedo: spreads altos, baixa liquidez
        if weekday == 0 and hour < self.avoid_monday_before_hour:
            return False, 'monday_early', -50
        
        # Sexta-feira tarde: posições sendo fechadas, volatilidade errática
        if weekday == 4 and hour >= self.avoid_friday_after_hour:
            return False, 'friday_late', -30
        
        # Dias ótimos: terça a quinta
        if weekday in [1, 2, 3]:
            return True, 'optimal_day', +10
        
        return True, 'ok', 0
    
    def _get_max_spread_for_session(self, session: str) -> float:
        """Retorna o spread máximo permitido para a sessão atual"""
        spread_limits = {
            'OVERLAP': self.spread_max_overlap,
            'LONDON': self.spread_max_london,
            'NEW_YORK': self.spread_max_ny,
            'ASIA': self.spread_max_asia,
            'TRANSITION': self.spread_max_pips
        }
        return spread_limits.get(session, self.spread_max_pips)
    
    def _check_viability(self, technical_analysis: Dict) -> tuple:
        """
        🌽 VERIFICAÇÃO COMPLETA DE VIABILIDADE
        
        Analisa se as condições de mercado são ideais para operar.
        Só permite trades quando o score >= 60.
        
        Returns:
            tuple: (is_viable: bool, score: float, reasons: list)
        """
        score = 50.0  # Base score
        reasons = []
        
        now = datetime.utcnow()
        
        # ============================================
        # 1. VERIFICAÇÃO DO DIA
        # ============================================
        day_ok, day_reason, day_adjustment = self._check_day_viability()
        if not day_ok:
            self.viability_score = 0
            self.viability_reason = day_reason
            return False, 0.0, [day_reason]
        
        score += day_adjustment
        if day_adjustment > 0:
            reasons.append(f'day:{day_reason}')
        
        # ============================================
        # 2. VERIFICAÇÃO DA SESSÃO
        # ============================================
        session = self._get_current_session()
        
        session_scores = {
            'OVERLAP': +25,     # Melhor momento
            'LONDON': +15,      # Muito bom
            'NEW_YORK': +10,    # Bom
            'TRANSITION': -10,  # Evitar
            'ASIA': -20         # Não recomendado para majors
        }
        
        score += session_scores.get(session, 0)
        reasons.append(f'session:{session}')
        
        # Não operar na Ásia (sem modo forçado)
        if session == 'ASIA' and self.auto_mode:
            self.viability_score = score
            self.viability_reason = 'asia_session'
            return False, score, ['asia_session']
        
        # ============================================
        # 3. VERIFICAÇÃO DO SPREAD
        # ============================================
        m1_data = technical_analysis.get('M1', {})
        spread_pips = m1_data.get('spread_pips', 999)
        max_spread = self._get_max_spread_for_session(session)
        
        if spread_pips > max_spread:
            score -= 30
            reasons.append(f'spread_high:{spread_pips:.1f}>{max_spread:.1f}')
        elif spread_pips <= max_spread * 0.5:
            score += 15  # Spread muito bom
            reasons.append(f'spread_excellent:{spread_pips:.1f}')
        elif spread_pips <= max_spread * 0.8:
            score += 5   # Spread bom
            reasons.append(f'spread_good:{spread_pips:.1f}')
        
        # ============================================
        # 4. VERIFICAÇÃO DE VOLATILIDADE (ATR)
        # ============================================
        m5_data = technical_analysis.get('M5', {})
        atr_current = m5_data.get('atr', 0)
        
        if atr_current > 0:
            # Comparar com range esperado
            if self.atr_min <= atr_current <= self.atr_max:
                atr_ratio = (atr_current - self.atr_min) / (self.atr_max - self.atr_min)
                
                # Sweet spot: meio do range
                if 0.3 <= atr_ratio <= 0.7:
                    score += 15
                    reasons.append('atr_sweet_spot')
                else:
                    score += 5
                    reasons.append('atr_ok')
            elif atr_current < self.atr_min:
                score -= 20
                reasons.append('atr_too_low')
            else:
                score -= 15
                reasons.append('atr_too_high')
        
        # ============================================
        # 5. VERIFICAÇÃO DE ADX (Trending vs Range)
        # ============================================
        adx_data = m5_data.get('adx', {})
        adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else 0
        
        if adx > 0:
            if adx < 20:  # Mercado muito lateral - ideal
                score += 15
                reasons.append(f'adx_ideal:{adx:.0f}')
            elif adx < self.adx_max:  # Lateral aceitável
                score += 5
                reasons.append(f'adx_ok:{adx:.0f}')
            else:  # Trending - ruim para mean reversion
                score -= 25
                reasons.append(f'adx_trending:{adx:.0f}')
        
        # ============================================
        # 6. VERIFICAÇÃO DE PERFORMANCE DIÁRIA
        # ============================================
        self._reset_daily_counters_if_needed()
        
        # Se já perdeu muito hoje, parar
        if self.pnl_today <= self.max_loss_day * 100:  # Convertendo para %
            self.viability_score = 0
            self.viability_reason = 'daily_loss_limit'
            return False, 0.0, ['daily_loss_limit_reached']
        
        # Se muitos losses seguidos, reduzir score
        if self.losses_today - self.wins_today >= 3:
            score -= 20
            reasons.append('bad_day')
        
        # Se está ganhando, boost
        if self.wins_today > self.losses_today and self.trades_today >= 3:
            score += 10
            reasons.append('winning_day')
        
        # ============================================
        # 7. LIMITE DE TRADES
        # ============================================
        if self.trades_today >= self.max_trades_day:
            self.viability_score = 0
            self.viability_reason = 'max_trades_reached'
            return False, 0.0, ['max_trades_per_day']
        
        # ============================================
        # 8. DECISÃO FINAL
        # ============================================
        self.viability_score = min(max(score, 0), 100)
        
        # Threshold de viabilidade: 60 pontos
        if score >= 60:
            self.viability_reason = f"viable_{score:.0f}"
            return True, score, reasons
        else:
            self.viability_reason = f"not_viable_{score:.0f}"
            return False, score, reasons
    
    def _reset_daily_counters_if_needed(self):
        """Reseta contadores diários se for um novo dia"""
        now = datetime.utcnow()
        today = now.date()
        
        if self.last_reset_date is None or self.last_reset_date != today:
            self.trades_today = 0
            self.wins_today = 0
            self.losses_today = 0
            self.pnl_today = 0.0
            self.last_reset_date = today
            logger.info(f"🌽 [{self.symbol}] Contadores diários resetados")
    
    def _check_session(self) -> bool:
        """Verifica se está em horário de operação básico"""
        now = datetime.utcnow()
        return self.session_start_hour <= now.hour < self.session_end_hour
    
    def _check_cooldown(self) -> bool:
        """Verifica se está em cooldown"""
        if self.cooldown_until is None:
            return False
        return datetime.utcnow() < self.cooldown_until
    
    def _check_context_m5(self, technical_analysis: Dict) -> tuple:
        """
        Verifica contexto M5 para filtrar operações
        
        Returns:
            tuple: (is_valid: bool, reason: str)
        """
        m5_data = technical_analysis.get('M5', {})
        
        if not m5_data:
            return False, 'no_m5_data'
        
        # Extrair dados M5
        adx_data = m5_data.get('adx', {})
        atr_value = m5_data.get('atr', 0)
        ema_data = m5_data.get('ema', {})
        current_price = m5_data.get('current_price', 0)
        
        # ADX
        adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else 0
        
        # Filtro 1: ADX < max (mercado lateral)
        if adx > self.adx_max:
            return False, f'adx_too_high_{adx:.1f}'
        
        # Filtro 2: ATR em range normal
        if atr_value < self.atr_min or atr_value > self.atr_max:
            return False, f'atr_out_of_range_{atr_value:.5f}'
        
        # Filtro 3: Preço perto da EMA50
        ema_50 = ema_data.get('ema_50', 0) if isinstance(ema_data, dict) else 0
        
        if ema_50 > 0 and current_price > 0:
            pip = self._get_pip_value()
            distance_pips = abs(current_price - ema_50) / pip
            
            if distance_pips > self.ema_distance_max_pips:
                return False, f'price_far_from_ema_{distance_pips:.1f}p'
        
        return True, 'context_ok'
    
    def _analyze_m1_setup(self, technical_analysis: Dict) -> Dict:
        """
        Analisa setup de entrada em M1
        
        Returns:
            Dict com 'action', 'confidence', 'reason', 'details'
        """
        m1_data = technical_analysis.get('M1', {})
        
        if not m1_data:
            return {'action': 'HOLD', 'confidence': 0, 'reason': 'no_m1_data'}
        
        # Extrair indicadores M1
        close_price = m1_data.get('current_price', 0)
        
        # EMAs
        ema_data = m1_data.get('ema', {})
        ema_8 = ema_data.get('ema_9', 0) if isinstance(ema_data, dict) else 0  # Aproximando
        ema_21 = ema_data.get('ema_21', 0) if isinstance(ema_data, dict) else 0
        ema_50 = ema_data.get('ema_50', 0) if isinstance(ema_data, dict) else 0
        
        # Bollinger
        bb_data = m1_data.get('bollinger', {})
        bb_upper = bb_data.get('upper', 0) if isinstance(bb_data, dict) else 0
        bb_lower = bb_data.get('lower', 0) if isinstance(bb_data, dict) else 0
        bb_middle = bb_data.get('middle', 0) if isinstance(bb_data, dict) else 0
        
        # RSI
        rsi = m1_data.get('rsi', 50)
        rsi_prev = m1_data.get('rsi_prev', rsi)  # Pode não estar disponível
        
        # Volume
        volume = m1_data.get('volume', 0)
        volume_ma = m1_data.get('volume_ma', 0)
        
        # Candle atual
        candle = m1_data.get('candle', {})
        open_price = candle.get('open', close_price) if isinstance(candle, dict) else close_price
        high_price = candle.get('high', close_price) if isinstance(candle, dict) else close_price
        low_price = candle.get('low', close_price) if isinstance(candle, dict) else close_price
        
        # Cálculos do candle
        pip = self._get_pip_value()
        candle_range = high_price - low_price
        candle_range_pips = candle_range / pip if pip > 0 else 0
        body = abs(close_price - open_price)
        body_pips = body / pip if pip > 0 else 0
        
        # Pavios
        if close_price >= open_price:  # Candle de alta
            upper_wick = high_price - close_price
            lower_wick = open_price - low_price
        else:  # Candle de baixa
            upper_wick = high_price - open_price
            lower_wick = close_price - low_price
        
        upper_wick_pct = (upper_wick / candle_range * 100) if candle_range > 0 else 0
        lower_wick_pct = (lower_wick / candle_range * 100) if candle_range > 0 else 0
        
        # =====================================================
        # SETUP BUY (Catando pra cima)
        # =====================================================
        buy_conditions = []
        buy_score = 0
        
        # 1. Close abaixo da EMA21 mas acima da EMA50
        if ema_21 > 0 and ema_50 > 0:
            if close_price < ema_21 and close_price > ema_50:
                buy_conditions.append('price_between_ema21_50')
                buy_score += 2
        
        # 2. Low tocou ou passou da Bollinger Lower
        if bb_lower > 0 and low_price <= bb_lower:
            buy_conditions.append('touched_bb_lower')
            buy_score += 3
        
        # 3. RSI oversold e virando
        if rsi < self.rsi_oversold:
            buy_conditions.append(f'rsi_oversold_{rsi:.1f}')
            buy_score += 2
            
            # Verificar se RSI está subindo (se disponível)
            if rsi > rsi_prev:
                buy_conditions.append('rsi_turning_up')
                buy_score += 1
        
        # 4. Pavio inferior significativo
        if lower_wick_pct >= self.wick_min_percent:
            buy_conditions.append(f'lower_wick_{lower_wick_pct:.0f}%')
            buy_score += 2
        
        # 5. Corpo pequeno (doji/reversão)
        if body_pips <= self.body_max_pips:
            buy_conditions.append('small_body')
            buy_score += 1
        
        # 6. Volume acima da média
        if volume_ma > 0 and volume > volume_ma:
            buy_conditions.append('high_volume')
            buy_score += 1
        
        # =====================================================
        # SETUP SELL (Catando pra baixo)
        # =====================================================
        sell_conditions = []
        sell_score = 0
        
        # 1. Close acima da EMA21 mas abaixo da EMA50
        if ema_21 > 0 and ema_50 > 0:
            if close_price > ema_21 and close_price < ema_50:
                sell_conditions.append('price_between_ema21_50')
                sell_score += 2
        
        # 2. High tocou ou passou da Bollinger Upper
        if bb_upper > 0 and high_price >= bb_upper:
            sell_conditions.append('touched_bb_upper')
            sell_score += 3
        
        # 3. RSI overbought e virando
        if rsi > self.rsi_overbought:
            sell_conditions.append(f'rsi_overbought_{rsi:.1f}')
            sell_score += 2
            
            if rsi < rsi_prev:
                sell_conditions.append('rsi_turning_down')
                sell_score += 1
        
        # 4. Pavio superior significativo
        if upper_wick_pct >= self.wick_min_percent:
            sell_conditions.append(f'upper_wick_{upper_wick_pct:.0f}%')
            sell_score += 2
        
        # 5. Corpo pequeno
        if body_pips <= self.body_max_pips:
            sell_conditions.append('small_body')
            sell_score += 1
        
        # 6. Volume acima da média
        if volume_ma > 0 and volume > volume_ma:
            sell_conditions.append('high_volume')
            sell_score += 1
        
        # =====================================================
        # DETERMINAR AÇÃO
        # =====================================================
        min_score = 6  # Threshold mínimo para entrada
        
        if buy_score >= min_score and buy_score > sell_score:
            confidence = min(buy_score / 12.0, 1.0)  # Max score = 12
            return {
                'action': 'BUY',
                'confidence': confidence,
                'reason': '+'.join(buy_conditions[:3]),
                'details': {
                    'score': buy_score,
                    'conditions': buy_conditions,
                    'rsi': rsi,
                    'bb_lower': bb_lower,
                    'close': close_price
                }
            }
        
        elif sell_score >= min_score and sell_score > buy_score:
            confidence = min(sell_score / 12.0, 1.0)
            return {
                'action': 'SELL',
                'confidence': confidence,
                'reason': '+'.join(sell_conditions[:3]),
                'details': {
                    'score': sell_score,
                    'conditions': sell_conditions,
                    'rsi': rsi,
                    'bb_upper': bb_upper,
                    'close': close_price
                }
            }
        
        return {
            'action': 'HOLD',
            'confidence': 0,
            'reason': f'no_setup_buy{buy_score}_sell{sell_score}',
            'details': {
                'buy_score': buy_score,
                'sell_score': sell_score
            }
        }
    
    def analyze(self, technical_analysis: Dict,
                news_analysis: Optional[Dict] = None) -> Dict:
        """
        Método principal de análise da estratégia Catamilho
        
        🌽 v1.1: Com AUTO-ATIVAÇÃO INTELIGENTE
        Só opera quando as condições de mercado são ideais.
        
        Args:
            technical_analysis: Análise técnica multi-timeframe
            news_analysis: Análise de notícias (opcional)
            
        Returns:
            Dict com sinal de trading
        """
        try:
            # ========================================
            # 0. VERIFICAÇÃO DE VIABILIDADE INTELIGENTE
            # ========================================
            if self.auto_mode:
                is_viable, viability_score, viability_reasons = self._check_viability(technical_analysis)
                
                if not is_viable:
                    # Log a cada 10 minutos para não poluir
                    now = datetime.utcnow()
                    if self.last_signal_time is None or (now - self.last_signal_time).seconds > 600:
                        session = self._get_current_session()
                        logger.debug(
                            f"🌽 [{self.symbol}] Catamilho inativa | "
                            f"Score: {viability_score:.0f}/60 | "
                            f"Sessão: {session} | "
                            f"Razão: {self.viability_reason}"
                        )
                        self.last_signal_time = now
                    
                    return self.create_signal(
                        'HOLD', 0.0, 
                        f'not_viable_{viability_score:.0f}_{self.viability_reason}'
                    )
            
            # ========================================
            # 1. VERIFICAÇÕES DE ESTADO
            # ========================================
            
            # Verificar horário de sessão básico
            if not self._check_session():
                return self.create_signal('HOLD', 0.0, 'outside_session')
            
            # Verificar cooldown
            if self._check_cooldown():
                return self.create_signal('HOLD', 0.0, 'in_cooldown')
            
            # ========================================
            # 2. VERIFICAR SPREAD (dinâmico por sessão)
            # ========================================
            m1_data = technical_analysis.get('M1', {})
            spread_pips = m1_data.get('spread_pips', 0)
            session = self._get_current_session()
            max_spread = self._get_max_spread_for_session(session)
            
            if spread_pips > max_spread:
                return self.create_signal(
                    'HOLD', 0.0, 
                    f'spread_{spread_pips:.1f}p>{max_spread:.1f}p'
                )
            
            # ========================================
            # 3. VERIFICAR CONTEXTO M5
            # ========================================
            context_ok, context_reason = self._check_context_m5(technical_analysis)
            
            if not context_ok:
                return self.create_signal('HOLD', 0.0, f'm5_{context_reason}')
            
            # ========================================
            # 4. VERIFICAR NOTÍCIAS (se disponível)
            # ========================================
            if news_analysis:
                high_impact = news_analysis.get('high_impact_soon', False)
                if high_impact:
                    return self.create_signal('HOLD', 0.0, 'news_warning')
            
            # ========================================
            # 5. ANALISAR SETUP M1
            # ========================================
            setup = self._analyze_m1_setup(technical_analysis)
            
            if setup['action'] == 'HOLD':
                return self.create_signal('HOLD', 0.0, setup['reason'])
            
            # ========================================
            # 6. GERAR SINAL
            # ========================================
            action = setup['action']
            confidence = setup['confidence']
            
            # Ajustar confiança baseado na viabilidade
            if self.auto_mode and self.viability_score > 0:
                viability_boost = (self.viability_score - 60) / 100  # -0.4 a +0.4
                confidence = min(max(confidence + viability_boost * 0.2, 0.5), 1.0)
            
            reason = f"catamilho_{setup['reason']}_v{self.viability_score:.0f}"
            
            # Calcular SL/TP
            current_price = m1_data.get('current_price', 0)
            pip = self._get_pip_value()
            
            if action == 'BUY':
                sl = current_price - (self.sl_pips * pip)
                tp = current_price + (self.tp_pips * pip)
            else:  # SELL
                sl = current_price + (self.sl_pips * pip)
                tp = current_price - (self.tp_pips * pip)
            
            # Determinar casas decimais
            digits = 2 if self.symbol in ['XAUUSD', 'XAGUSD'] else 5
            if 'JPY' in self.symbol:
                digits = 3
            
            signal = {
                'strategy': self.name,
                'symbol': self.symbol,
                'action': action,
                'confidence': round(confidence, 3),
                'reason': reason,
                'details': setup['details'],
                'price': current_price,
                'sl': round(sl, digits),
                'tp': round(tp, digits),
                'trailing_start': self.trailing_start_pips,
                'trailing_step': self.trailing_step_pips,
                'breakeven': self.breakeven_pips,
                'max_duration_candles': self.max_candles_in_trade
            }
            
            logger.info(
                f"🌽 CATAMILHO {action} {self.symbol} | "
                f"Conf: {confidence:.0%} | {reason} | "
                f"SL: {sl:.5f} TP: {tp:.5f}"
            )
            
            self.state = 'ARMED'
            self.last_signal_time = datetime.utcnow()
            
            return signal
            
        except Exception as e:
            logger.error(f"🌽 Erro em CatamilhoStrategy.analyze: {e}")
            return self.create_signal('HOLD', 0.0, f'error: {e}')
    
    def on_trade_closed(self, profit: float, reason: str = ''):
        """
        Callback quando um trade é fechado
        Atualiza estado interno, contadores e cooldown
        
        🌽 v1.1: Atualiza contadores de performance diária
        """
        # Resetar contadores se for novo dia
        self._reset_daily_counters_if_needed()
        
        # Atualizar contadores
        self.trades_today += 1
        self.pnl_today += profit
        
        if profit > 0:
            self.wins_today += 1
            logger.info(
                f"🌽 [{self.symbol}] WIN +${profit:.2f} | "
                f"Dia: {self.wins_today}W/{self.losses_today}L | "
                f"PnL: ${self.pnl_today:.2f}"
            )
        else:
            self.losses_today += 1
            
            # Entrar em cooldown após perda
            cooldown_seconds = self.cooldown_after_loss_seconds
            
            # Cooldown progressivo: mais perdas = mais cooldown
            losses_row = self.losses_today - self.wins_today
            if losses_row >= 2:
                cooldown_seconds *= 2
            if losses_row >= 3:
                cooldown_seconds *= 2
            
            self.cooldown_until = datetime.utcnow() + timedelta(seconds=cooldown_seconds)
            
            logger.warning(
                f"🌽 [{self.symbol}] LOSS -${abs(profit):.2f} | "
                f"Dia: {self.wins_today}W/{self.losses_today}L | "
                f"PnL: ${self.pnl_today:.2f} | "
                f"Cooldown: {cooldown_seconds}s"
            )
            
            # Se muitas perdas seguidas, parar por mais tempo
            if losses_row >= self.max_losses_row:
                # Cooldown de 5 minutos após max losses
                self.cooldown_until = datetime.utcnow() + timedelta(minutes=5)
                logger.warning(
                    f"🌽 [{self.symbol}] Max losses seguidos ({self.max_losses_row}) - "
                    f"Cooldown estendido: 5 minutos"
                )
        
        self.state = 'IDLE'
    
    def get_status(self) -> Dict:
        """
        Retorna status atual da estratégia para monitoramento
        """
        session = self._get_current_session()
        
        return {
            'name': self.name,
            'symbol': self.symbol,
            'state': self.state,
            'session': session,
            'viability_score': self.viability_score,
            'viability_reason': self.viability_reason,
            'trades_today': self.trades_today,
            'wins_today': self.wins_today,
            'losses_today': self.losses_today,
            'pnl_today': self.pnl_today,
            'winrate_today': (
                round(self.wins_today / self.trades_today * 100, 1) 
                if self.trades_today > 0 else 0
            ),
            'auto_mode': self.auto_mode,
            'in_cooldown': self._check_cooldown(),
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None
        }