"""
Market Regime Detector - Detecta se mercado está TRENDING ou RANGING
====================================================================

Este módulo é crucial para escolher a estratégia correta:
- TRENDING → Use TrendFollowing, Scalping na direção
- RANGING → Use MeanReversion, RangeTrading

MÉTODOS DE DETECÇÃO:
1. ADX (Average Directional Index)
   - ADX > 35: Trending forte
   - ADX 25-35: Trending fraco
   - ADX < 25: Ranging
   
2. Bollinger Band Width
   - Bandas estreitas: Consolidação (potencial breakout)
   - Bandas largas: Alta volatilidade
   
3. ATR Relative
   - ATR crescente: Tendência desenvolvendo
   - ATR decrescente: Consolidação
   
4. Donchian Channel
   - Novos highs/lows: Trending
   - Preço no meio: Ranging
   
5. Hurst Exponent (avançado)
   - H > 0.5: Trending (memória longa)
   - H = 0.5: Random walk
   - H < 0.5: Mean reverting
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import numpy as np
import pandas as pd
from loguru import logger
import threading


class RegimeType(Enum):
    """Tipos de regime de mercado"""
    STRONG_TREND_UP = "STRONG_TREND_UP"       # Tendência de alta forte
    TREND_UP = "TREND_UP"                     # Tendência de alta
    WEAK_TREND_UP = "WEAK_TREND_UP"           # Tendência de alta fraca
    RANGING = "RANGING"                       # Mercado lateral
    WEAK_TREND_DOWN = "WEAK_TREND_DOWN"       # Tendência de baixa fraca
    TREND_DOWN = "TREND_DOWN"                 # Tendência de baixa
    STRONG_TREND_DOWN = "STRONG_TREND_DOWN"   # Tendência de baixa forte
    CONSOLIDATION = "CONSOLIDATION"           # Consolidação (pré-breakout)
    HIGH_VOLATILITY = "HIGH_VOLATILITY"       # Volatilidade extrema


@dataclass
class RegimeAnalysis:
    """Resultado da análise de regime"""
    regime: RegimeType
    confidence: float  # 0-1
    adx_value: float
    adx_direction: str  # 'rising', 'falling', 'flat'
    bb_width_percentile: float  # 0-100 (posição em relação ao histórico)
    atr_trend: str  # 'expanding', 'contracting', 'stable'
    donchian_position: float  # 0-1 (posição do preço no canal)
    is_consolidating: bool
    consolidation_bars: int
    breakout_potential: str  # 'high', 'medium', 'low', 'none'
    recommended_strategies: List[str]
    timestamp: datetime


class MarketRegimeDetector:
    """
    Detector de Regime de Mercado
    
    Analisa múltiplos indicadores para determinar se o mercado
    está em tendência ou lateral.
    """
    
    def __init__(self, config: Dict = None):
        """
        Args:
            config: Configurações do detector
        """
        self.config = config or {}
        
        # Thresholds configuráveis
        self.adx_strong = self.config.get('adx_strong_threshold', 35)
        self.adx_trend = self.config.get('adx_trend_threshold', 25)
        self.adx_ranging = self.config.get('adx_ranging_threshold', 20)
        
        self.bb_squeeze_percentile = self.config.get('bb_squeeze_percentile', 20)
        self.bb_wide_percentile = self.config.get('bb_wide_percentile', 80)
        
        self.consolidation_threshold = self.config.get('consolidation_bars', 12)
        
        # Cache
        self._cache: Dict[str, RegimeAnalysis] = {}
        self._cache_timeout = timedelta(minutes=5)
        self._lock = threading.Lock()
        
        logger.info("🔍 MarketRegimeDetector inicializado")
    
    def detect(
        self, 
        df: pd.DataFrame, 
        adx: float = None,
        di_plus: float = None,
        di_minus: float = None,
        symbol: str = "XAUUSD"
    ) -> RegimeAnalysis:
        """
        Detecta o regime de mercado atual.
        
        Args:
            df: DataFrame com OHLCV (mínimo 100 barras)
            adx: ADX pré-calculado (opcional)
            di_plus: DI+ pré-calculado (opcional)
            di_minus: DI- pré-calculado (opcional)
            symbol: Símbolo para cache
            
        Returns:
            RegimeAnalysis com análise completa
        """
        try:
            if df is None or len(df) < 50:
                return self._create_default_analysis()
            
            # 1. ADX Analysis
            adx_value, adx_direction = self._analyze_adx(df, adx)
            
            # 2. Bollinger Band Width Analysis
            bb_width_percentile = self._analyze_bb_width(df)
            
            # 3. ATR Trend Analysis
            atr_trend = self._analyze_atr_trend(df)
            
            # 4. Donchian Channel Position
            donchian_position = self._analyze_donchian(df)
            
            # 5. Consolidation Detection
            is_consolidating, consolidation_bars = self._detect_consolidation(df)
            
            # 6. Combine all factors to determine regime
            regime, confidence = self._determine_regime(
                adx_value=adx_value,
                adx_direction=adx_direction,
                di_plus=di_plus,
                di_minus=di_minus,
                bb_width_percentile=bb_width_percentile,
                atr_trend=atr_trend,
                donchian_position=donchian_position,
                is_consolidating=is_consolidating,
                df=df
            )
            
            # 7. Calculate breakout potential
            breakout_potential = self._calculate_breakout_potential(
                bb_width_percentile, is_consolidating, consolidation_bars, atr_trend
            )
            
            # 8. Get recommended strategies
            recommended_strategies = self._get_strategy_recommendations(regime, breakout_potential)
            
            analysis = RegimeAnalysis(
                regime=regime,
                confidence=confidence,
                adx_value=adx_value,
                adx_direction=adx_direction,
                bb_width_percentile=bb_width_percentile,
                atr_trend=atr_trend,
                donchian_position=donchian_position,
                is_consolidating=is_consolidating,
                consolidation_bars=consolidation_bars,
                breakout_potential=breakout_potential,
                recommended_strategies=recommended_strategies,
                timestamp=datetime.now()
            )
            
            logger.debug(
                f"🔍 Regime detectado: {regime.value} "
                f"(ADX={adx_value:.1f}, Conf={confidence:.2%})"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erro ao detectar regime: {e}")
            return self._create_default_analysis()
    
    def _analyze_adx(
        self, df: pd.DataFrame, 
        pre_calculated_adx: float = None
    ) -> Tuple[float, str]:
        """Analisa ADX e sua direção"""
        
        if pre_calculated_adx is not None:
            adx = pre_calculated_adx
        else:
            # Calcular ADX
            adx = self._calculate_adx(df)
        
        # Verificar direção do ADX (últimas 5 barras)
        if len(df) >= 20:
            try:
                adx_series = self._calculate_adx_series(df, 14)
                if len(adx_series) >= 5:
                    recent = adx_series[-5:]
                    slope = np.polyfit(range(len(recent)), recent, 1)[0]
                    
                    if slope > 0.5:
                        adx_direction = 'rising'
                    elif slope < -0.5:
                        adx_direction = 'falling'
                    else:
                        adx_direction = 'flat'
                else:
                    adx_direction = 'flat'
            except:
                adx_direction = 'flat'
        else:
            adx_direction = 'flat'
        
        return adx, adx_direction
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcula ADX manualmente"""
        try:
            high = df['High'].values
            low = df['Low'].values
            close = df['Close'].values
            
            # True Range
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))
            tr = np.maximum(np.maximum(tr1, tr2), tr3)
            
            # Directional Movement
            up_move = high - np.roll(high, 1)
            down_move = np.roll(low, 1) - low
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            # Smoothed averages
            atr = self._smooth(tr, period)
            plus_di = 100 * self._smooth(plus_dm, period) / atr
            minus_di = 100 * self._smooth(minus_dm, period) / atr
            
            # ADX
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            adx = self._smooth(dx, period)
            
            return float(adx[-1]) if len(adx) > 0 else 20.0
            
        except Exception as e:
            logger.error(f"Erro ao calcular ADX: {e}")
            return 20.0
    
    def _calculate_adx_series(self, df: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calcula série completa de ADX"""
        try:
            high = df['High'].values
            low = df['Low'].values
            close = df['Close'].values
            
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))
            tr = np.maximum(np.maximum(tr1, tr2), tr3)
            
            up_move = high - np.roll(high, 1)
            down_move = np.roll(low, 1) - low
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            atr = self._smooth(tr, period)
            plus_di = 100 * self._smooth(plus_dm, period) / (atr + 1e-10)
            minus_di = 100 * self._smooth(minus_dm, period) / (atr + 1e-10)
            
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            adx = self._smooth(dx, period)
            
            return adx
            
        except:
            return np.array([20.0])
    
    def _smooth(self, data: np.ndarray, period: int) -> np.ndarray:
        """Aplica suavização EMA-like"""
        alpha = 1.0 / period
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
        return result
    
    def _analyze_bb_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """Analisa largura das Bandas de Bollinger relativa ao histórico"""
        try:
            close = df['Close']
            
            # Calcular Bollinger Bands
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            upper = sma + 2 * std
            lower = sma - 2 * std
            
            # Largura relativa (normalizada pelo preço)
            width = (upper - lower) / sma
            
            # Percentil da largura atual vs histórico
            current_width = width.iloc[-1]
            percentile = (width < current_width).sum() / len(width) * 100
            
            return float(percentile)
            
        except Exception as e:
            logger.error(f"Erro ao analisar BB width: {e}")
            return 50.0
    
    def _analyze_atr_trend(self, df: pd.DataFrame, period: int = 14) -> str:
        """Analisa tendência do ATR"""
        try:
            high = df['High']
            low = df['Low']
            close = df['Close']
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            atr = tr.rolling(window=period).mean()
            
            if len(atr) < 10:
                return 'stable'
            
            # Comparar ATR recente com ATR anterior
            recent_atr = atr.iloc[-5:].mean()
            prev_atr = atr.iloc[-15:-5].mean()
            
            ratio = recent_atr / (prev_atr + 1e-10)
            
            if ratio > 1.15:
                return 'expanding'
            elif ratio < 0.85:
                return 'contracting'
            else:
                return 'stable'
                
        except:
            return 'stable'
    
    def _analyze_donchian(self, df: pd.DataFrame, period: int = 20) -> float:
        """Analisa posição do preço no canal Donchian"""
        try:
            high = df['High'].rolling(window=period).max()
            low = df['Low'].rolling(window=period).min()
            close = df['Close'].iloc[-1]
            
            channel_high = high.iloc[-1]
            channel_low = low.iloc[-1]
            
            # Posição 0-1 no canal
            position = (close - channel_low) / (channel_high - channel_low + 1e-10)
            
            return float(np.clip(position, 0, 1))
            
        except:
            return 0.5
    
    def _detect_consolidation(self, df: pd.DataFrame) -> Tuple[bool, int]:
        """Detecta se o mercado está em consolidação"""
        try:
            # Range das últimas N barras vs média
            lookback = min(20, len(df) - 1)
            
            recent_high = df['High'].iloc[-lookback:].max()
            recent_low = df['Low'].iloc[-lookback:].min()
            recent_range = recent_high - recent_low
            
            # ATR para comparação
            high = df['High']
            low = df['Low']
            close = df['Close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            
            # Consolidação se range < 4x ATR
            expected_range = atr * 4 * lookback / 14
            is_consolidating = recent_range < expected_range * 0.7
            
            # Contar barras dentro do range
            if is_consolidating:
                mid = (recent_high + recent_low) / 2
                range_size = recent_range * 0.4  # 40% do range
                inside_count = 0
                for i in range(-lookback, 0):
                    if abs(df['Close'].iloc[i] - mid) < range_size:
                        inside_count += 1
                consolidation_bars = inside_count
            else:
                consolidation_bars = 0
            
            return is_consolidating, consolidation_bars
            
        except:
            return False, 0
    
    def _determine_regime(
        self,
        adx_value: float,
        adx_direction: str,
        di_plus: float,
        di_minus: float,
        bb_width_percentile: float,
        atr_trend: str,
        donchian_position: float,
        is_consolidating: bool,
        df: pd.DataFrame
    ) -> Tuple[RegimeType, float]:
        """Determina o regime de mercado combinando todos os fatores"""
        
        # Determinar direção
        if di_plus is not None and di_minus is not None:
            is_bullish = di_plus > di_minus
        else:
            # Usar EMAs como fallback
            close = df['Close']
            ema_fast = close.ewm(span=9).mean().iloc[-1]
            ema_slow = close.ewm(span=21).mean().iloc[-1]
            is_bullish = ema_fast > ema_slow
        
        confidence = 0.5
        
        # Regime baseado no ADX
        if adx_value >= self.adx_strong:
            # Tendência forte
            confidence = min(0.5 + (adx_value - self.adx_strong) / 30, 0.95)
            
            if is_bullish:
                if adx_direction == 'rising':
                    return RegimeType.STRONG_TREND_UP, confidence
                else:
                    return RegimeType.TREND_UP, confidence * 0.9
            else:
                if adx_direction == 'rising':
                    return RegimeType.STRONG_TREND_DOWN, confidence
                else:
                    return RegimeType.TREND_DOWN, confidence * 0.9
        
        elif adx_value >= self.adx_trend:
            # Tendência fraca
            confidence = 0.4 + (adx_value - self.adx_trend) / 40
            
            if is_bullish:
                if donchian_position > 0.7:
                    return RegimeType.TREND_UP, confidence
                else:
                    return RegimeType.WEAK_TREND_UP, confidence * 0.85
            else:
                if donchian_position < 0.3:
                    return RegimeType.TREND_DOWN, confidence
                else:
                    return RegimeType.WEAK_TREND_DOWN, confidence * 0.85
        
        elif adx_value < self.adx_ranging:
            # Ranging / Consolidação
            if is_consolidating:
                # Consolidação com potencial breakout
                if bb_width_percentile < self.bb_squeeze_percentile:
                    return RegimeType.CONSOLIDATION, 0.7
                else:
                    return RegimeType.RANGING, 0.6
            else:
                if bb_width_percentile > self.bb_wide_percentile:
                    return RegimeType.HIGH_VOLATILITY, 0.5
                else:
                    return RegimeType.RANGING, 0.55
        
        else:
            # Zona de transição
            if atr_trend == 'expanding':
                # Pode estar saindo de ranging para trending
                if is_bullish:
                    return RegimeType.WEAK_TREND_UP, 0.4
                else:
                    return RegimeType.WEAK_TREND_DOWN, 0.4
            else:
                return RegimeType.RANGING, 0.5
    
    def _calculate_breakout_potential(
        self,
        bb_width_percentile: float,
        is_consolidating: bool,
        consolidation_bars: int,
        atr_trend: str
    ) -> str:
        """Calcula potencial de breakout"""
        
        score = 0
        
        # BB squeeze
        if bb_width_percentile < 15:
            score += 3
        elif bb_width_percentile < 25:
            score += 2
        elif bb_width_percentile < 35:
            score += 1
        
        # Consolidação
        if is_consolidating:
            if consolidation_bars >= 15:
                score += 3
            elif consolidation_bars >= 10:
                score += 2
            elif consolidation_bars >= 5:
                score += 1
        
        # ATR contraindo
        if atr_trend == 'contracting':
            score += 2
        
        # Determinar potencial
        if score >= 6:
            return 'high'
        elif score >= 4:
            return 'medium'
        elif score >= 2:
            return 'low'
        else:
            return 'none'
    
    def _get_strategy_recommendations(
        self, 
        regime: RegimeType, 
        breakout_potential: str
    ) -> List[str]:
        """Retorna estratégias recomendadas para o regime"""
        
        recommendations = {
            RegimeType.STRONG_TREND_UP: ['trend_following', 'scalping'],
            RegimeType.TREND_UP: ['trend_following', 'breakout'],
            RegimeType.WEAK_TREND_UP: ['trend_following'],
            
            RegimeType.STRONG_TREND_DOWN: ['trend_following', 'scalping'],
            RegimeType.TREND_DOWN: ['trend_following', 'breakout'],
            RegimeType.WEAK_TREND_DOWN: ['trend_following'],
            
            RegimeType.RANGING: ['mean_reversion', 'range_trading'],
            RegimeType.CONSOLIDATION: ['breakout'],
            RegimeType.HIGH_VOLATILITY: ['breakout'],
        }
        
        base = recommendations.get(regime, ['trend_following'])
        
        # Adicionar breakout se potencial alto
        if breakout_potential in ['high', 'medium'] and 'breakout' not in base:
            base = base + ['breakout']
        
        return base
    
    def _create_default_analysis(self) -> RegimeAnalysis:
        """Cria análise padrão em caso de erro"""
        return RegimeAnalysis(
            regime=RegimeType.RANGING,
            confidence=0.3,
            adx_value=20.0,
            adx_direction='flat',
            bb_width_percentile=50.0,
            atr_trend='stable',
            donchian_position=0.5,
            is_consolidating=False,
            consolidation_bars=0,
            breakout_potential='none',
            recommended_strategies=['trend_following'],
            timestamp=datetime.now()
        )
    
    # =========================================
    # MÉTODOS PÚBLICOS SIMPLIFICADOS
    # =========================================
    
    def is_trending(self, df: pd.DataFrame) -> bool:
        """Retorna True se mercado está em tendência"""
        analysis = self.detect(df)
        return analysis.regime in [
            RegimeType.STRONG_TREND_UP, RegimeType.TREND_UP,
            RegimeType.STRONG_TREND_DOWN, RegimeType.TREND_DOWN
        ]
    
    def is_ranging(self, df: pd.DataFrame) -> bool:
        """Retorna True se mercado está lateral"""
        analysis = self.detect(df)
        return analysis.regime in [
            RegimeType.RANGING, RegimeType.CONSOLIDATION
        ]
    
    def get_trend_direction(self, df: pd.DataFrame) -> str:
        """Retorna direção da tendência: 'UP', 'DOWN', ou 'NEUTRAL'"""
        analysis = self.detect(df)
        
        if analysis.regime in [RegimeType.STRONG_TREND_UP, RegimeType.TREND_UP, RegimeType.WEAK_TREND_UP]:
            return 'UP'
        elif analysis.regime in [RegimeType.STRONG_TREND_DOWN, RegimeType.TREND_DOWN, RegimeType.WEAK_TREND_DOWN]:
            return 'DOWN'
        else:
            return 'NEUTRAL'


# =========================================
# SINGLETON
# =========================================

_regime_detector: Optional[MarketRegimeDetector] = None


def get_regime_detector(config: Dict = None) -> MarketRegimeDetector:
    """Factory function para obter detector singleton"""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = MarketRegimeDetector(config)
    return _regime_detector
