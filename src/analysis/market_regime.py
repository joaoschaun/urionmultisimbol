"""
Market Regime Detector
Detecção automática de regime de mercado para ajuste adaptativo de estratégias

Features:
- Classificação: Trending, Ranging, Volatile
- Indicadores múltiplos
- Machine Learning para classificação
- Ajuste automático de parâmetros
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class MarketRegime(Enum):
    """Regimes de mercado"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"


@dataclass
class RegimeInfo:
    """Informações do regime detectado"""
    regime: MarketRegime
    confidence: float          # 0-1
    strength: float           # Força do regime
    atr_percentile: float     # Percentil do ATR
    trend_strength: float     # Força da tendência (ADX)
    volatility_state: str     # low, normal, high, extreme
    recommended_strategy: str  # Estratégia recomendada
    risk_adjustment: float    # Multiplicador de risco
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        return {
            'regime': self.regime.value,
            'confidence': round(self.confidence, 2),
            'strength': round(self.strength, 2),
            'atr_percentile': round(self.atr_percentile, 2),
            'trend_strength': round(self.trend_strength, 2),
            'volatility_state': self.volatility_state,
            'recommended_strategy': self.recommended_strategy,
            'risk_adjustment': round(self.risk_adjustment, 2),
            'timestamp': self.timestamp.isoformat()
        }


class MarketRegimeDetector:
    """
    Detector de Regime de Mercado
    
    Usa múltiplos indicadores para classificar o estado atual do mercado:
    - ADX para força da tendência
    - ATR para volatilidade
    - Bollinger Band width para expansão/contração
    - Hurst exponent para persistência
    """
    
    # Limiares de classificação
    ADX_TRENDING = 25          # ADX > 25 = tendência
    ADX_STRONG_TREND = 40      # ADX > 40 = tendência forte
    ATR_LOW_PERCENTILE = 20    # ATR < 20% = baixa volatilidade
    ATR_HIGH_PERCENTILE = 80   # ATR > 80% = alta volatilidade
    BB_WIDTH_SQUEEZE = 0.01    # BB width < 1% = squeeze
    BB_WIDTH_EXPANSION = 0.03  # BB width > 3% = expansão
    
    # Parâmetros por regime
    REGIME_PARAMS = {
        MarketRegime.TRENDING_UP: {
            'strategy': 'trend_following',
            'risk_mult': 1.2,
            'sl_mult': 2.5,
            'tp_mult': 4.0,
        },
        MarketRegime.TRENDING_DOWN: {
            'strategy': 'trend_following',
            'risk_mult': 1.2,
            'sl_mult': 2.5,
            'tp_mult': 4.0,
        },
        MarketRegime.RANGING: {
            'strategy': 'mean_reversion',
            'risk_mult': 0.8,
            'sl_mult': 1.5,
            'tp_mult': 1.5,
        },
        MarketRegime.VOLATILE: {
            'strategy': 'breakout',
            'risk_mult': 0.6,
            'sl_mult': 3.0,
            'tp_mult': 2.0,
        },
        MarketRegime.QUIET: {
            'strategy': 'range_trading',
            'risk_mult': 1.0,
            'sl_mult': 1.5,
            'tp_mult': 1.5,
        },
        MarketRegime.BREAKOUT: {
            'strategy': 'breakout',
            'risk_mult': 1.0,
            'sl_mult': 2.0,
            'tp_mult': 3.0,
        },
    }
    
    def __init__(
        self,
        atr_period: int = 14,
        adx_period: int = 14,
        lookback: int = 100,
        bb_period: int = 20,
        bb_std: float = 2.0
    ):
        """
        Inicializa o detector
        
        Args:
            atr_period: Período do ATR
            adx_period: Período do ADX
            lookback: Período para análise histórica
            bb_period: Período do Bollinger Bands
            bb_std: Desvio padrão do BB
        """
        self.atr_period = atr_period
        self.adx_period = adx_period
        self.lookback = lookback
        self.bb_period = bb_period
        self.bb_std = bb_std
        
        self._regime_history: List[RegimeInfo] = []
        
        logger.info(
            f"📊 Market Regime Detector inicializado | "
            f"ATR: {atr_period} | ADX: {adx_period} | Lookback: {lookback}"
        )
    
    def calculate_atr(self, data: pd.DataFrame) -> pd.Series:
        """Calcula Average True Range"""
        high = data['high']
        low = data['low']
        close = data['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.atr_period).mean()
        
        return atr
    
    def calculate_adx(self, data: pd.DataFrame) -> pd.Series:
        """Calcula Average Directional Index"""
        high = data['high']
        low = data['low']
        close = data['close']
        
        # +DM e -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        # TR
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Smoothed
        atr = tr.rolling(self.adx_period).mean()
        plus_di = 100 * (plus_dm.rolling(self.adx_period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(self.adx_period).mean() / atr)
        
        # DX e ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(self.adx_period).mean()
        
        return adx
    
    def calculate_bollinger_width(self, data: pd.DataFrame) -> pd.Series:
        """Calcula largura das Bollinger Bands relativa ao preço"""
        close = data['close']
        
        middle = close.rolling(self.bb_period).mean()
        std = close.rolling(self.bb_period).std()
        
        upper = middle + self.bb_std * std
        lower = middle - self.bb_std * std
        
        width = (upper - lower) / middle
        
        return width
    
    def calculate_hurst(self, data: pd.DataFrame, max_lag: int = 20) -> float:
        """
        Calcula Hurst Exponent (simplificado)
        
        H < 0.5: Mean reverting
        H = 0.5: Random walk
        H > 0.5: Trending
        """
        try:
            prices = data['close'].values[-100:]
            
            if len(prices) < max_lag * 2:
                return 0.5
            
            lags = range(2, max_lag)
            tau = []
            
            for lag in lags:
                pp = np.subtract(prices[lag:], prices[:-lag])
                tau.append(np.std(pp))
            
            reg = np.polyfit(np.log(list(lags)), np.log(tau), 1)
            hurst = reg[0]
            
            return max(0, min(1, hurst))
        except:
            return 0.5
    
    def classify_volatility(self, atr_percentile: float) -> str:
        """Classifica nível de volatilidade"""
        if atr_percentile < 20:
            return "low"
        elif atr_percentile < 40:
            return "normal"
        elif atr_percentile < 80:
            return "high"
        else:
            return "extreme"
    
    def detect_regime(self, data: pd.DataFrame) -> RegimeInfo:
        """
        Detecta regime de mercado atual
        
        Args:
            data: DataFrame com OHLCV
            
        Returns:
            RegimeInfo com classificação
        """
        if len(data) < self.lookback:
            return RegimeInfo(
                regime=MarketRegime.UNKNOWN,
                confidence=0,
                strength=0,
                atr_percentile=50,
                trend_strength=0,
                volatility_state="unknown",
                recommended_strategy="wait",
                risk_adjustment=0.5,
                timestamp=datetime.now()
            )
        
        # Calcular indicadores
        atr = self.calculate_atr(data)
        adx = self.calculate_adx(data)
        bb_width = self.calculate_bollinger_width(data)
        hurst = self.calculate_hurst(data)
        
        # Valores atuais
        current_atr = atr.iloc[-1]
        current_adx = adx.iloc[-1] if not np.isnan(adx.iloc[-1]) else 0
        current_bb_width = bb_width.iloc[-1]
        
        # Percentil do ATR
        atr_values = atr.dropna().values[-self.lookback:]
        atr_percentile = (np.sum(atr_values < current_atr) / len(atr_values)) * 100
        
        # Direção da tendência
        close = data['close']
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else sma_50
        current_price = close.iloc[-1]
        
        trend_up = current_price > sma_50 > sma_200
        trend_down = current_price < sma_50 < sma_200
        
        # Classificar regime
        confidence = 0
        regime = MarketRegime.UNKNOWN
        
        # 1. Verificar tendência forte
        if current_adx > self.ADX_STRONG_TREND:
            if trend_up:
                regime = MarketRegime.TRENDING_UP
                confidence = min(1.0, current_adx / 50)
            elif trend_down:
                regime = MarketRegime.TRENDING_DOWN
                confidence = min(1.0, current_adx / 50)
            else:
                regime = MarketRegime.VOLATILE
                confidence = 0.7
        
        # 2. Verificar tendência moderada
        elif current_adx > self.ADX_TRENDING:
            if trend_up:
                regime = MarketRegime.TRENDING_UP
                confidence = 0.6
            elif trend_down:
                regime = MarketRegime.TRENDING_DOWN
                confidence = 0.6
            else:
                regime = MarketRegime.RANGING
                confidence = 0.5
        
        # 3. Mercado sem tendência clara
        else:
            # Verificar volatilidade
            if atr_percentile > self.ATR_HIGH_PERCENTILE:
                regime = MarketRegime.VOLATILE
                confidence = atr_percentile / 100
            elif atr_percentile < self.ATR_LOW_PERCENTILE:
                # Verificar squeeze (potencial breakout)
                if current_bb_width < self.BB_WIDTH_SQUEEZE:
                    regime = MarketRegime.BREAKOUT  # Preparando para breakout
                    confidence = 0.7
                else:
                    regime = MarketRegime.QUIET
                    confidence = 0.6
            else:
                regime = MarketRegime.RANGING
                confidence = 0.5
        
        # Ajustar confiança com Hurst
        if hurst > 0.6 and regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            confidence = min(1.0, confidence * 1.2)
        elif hurst < 0.4 and regime == MarketRegime.RANGING:
            confidence = min(1.0, confidence * 1.2)
        
        # Obter parâmetros recomendados
        regime_params = self.REGIME_PARAMS.get(regime, self.REGIME_PARAMS[MarketRegime.RANGING])
        
        # Criar resultado
        result = RegimeInfo(
            regime=regime,
            confidence=confidence,
            strength=current_adx / 50 if current_adx else 0,
            atr_percentile=atr_percentile,
            trend_strength=current_adx if not np.isnan(current_adx) else 0,
            volatility_state=self.classify_volatility(atr_percentile),
            recommended_strategy=regime_params['strategy'],
            risk_adjustment=regime_params['risk_mult'],
            timestamp=datetime.now()
        )
        
        # Adicionar ao histórico
        self._regime_history.append(result)
        if len(self._regime_history) > 1000:
            self._regime_history = self._regime_history[-500:]
        
        return result
    
    def get_regime_parameters(self, regime: MarketRegime) -> Dict[str, float]:
        """Retorna parâmetros recomendados para o regime"""
        return self.REGIME_PARAMS.get(regime, self.REGIME_PARAMS[MarketRegime.RANGING])
    
    def get_regime_statistics(self, lookback: int = 100) -> Dict[str, Any]:
        """
        Retorna estatísticas dos regimes recentes
        
        Returns:
            Dict com distribuição de regimes
        """
        if not self._regime_history:
            return {}
        
        recent = self._regime_history[-lookback:]
        
        regime_counts = {}
        for info in recent:
            regime = info.regime.value
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        total = len(recent)
        regime_pcts = {k: v/total*100 for k, v in regime_counts.items()}
        
        avg_confidence = sum(i.confidence for i in recent) / total
        avg_atr_pct = sum(i.atr_percentile for i in recent) / total
        
        return {
            'regime_distribution': regime_pcts,
            'regime_counts': regime_counts,
            'avg_confidence': round(avg_confidence, 2),
            'avg_atr_percentile': round(avg_atr_pct, 2),
            'dominant_regime': max(regime_counts, key=regime_counts.get) if regime_counts else None,
            'samples': total
        }
    
    def is_regime_change(self, threshold: int = 3) -> bool:
        """
        Verifica se houve mudança recente de regime
        
        Args:
            threshold: Número de barras para confirmar mudança
            
        Returns:
            True se houve mudança confirmada
        """
        if len(self._regime_history) < threshold + 1:
            return False
        
        current_regime = self._regime_history[-1].regime
        previous_regimes = [r.regime for r in self._regime_history[-(threshold+1):-1]]
        
        # Mudança se regime atual é diferente de todos os anteriores
        return all(r != current_regime for r in previous_regimes)
    
    def get_adaptive_parameters(
        self,
        data: pd.DataFrame,
        base_risk: float = 0.01,
        base_sl_mult: float = 2.0,
        base_tp_mult: float = 3.0
    ) -> Dict[str, float]:
        """
        Retorna parâmetros adaptados ao regime atual
        
        Args:
            data: Dados de mercado
            base_risk: Risco base por trade
            base_sl_mult: Multiplicador SL base
            base_tp_mult: Multiplicador TP base
            
        Returns:
            Dict com parâmetros ajustados
        """
        regime_info = self.detect_regime(data)
        params = self.get_regime_parameters(regime_info.regime)
        
        return {
            'regime': regime_info.regime.value,
            'confidence': regime_info.confidence,
            'risk_per_trade': base_risk * params['risk_mult'],
            'sl_multiplier': base_sl_mult * params['sl_mult'] / 2.0,  # Normalizar
            'tp_multiplier': base_tp_mult * params['tp_mult'] / 3.0,  # Normalizar
            'recommended_strategy': params['strategy'],
            'volatility_state': regime_info.volatility_state
        }


# Singleton
_regime_detector: Optional[MarketRegimeDetector] = None


def get_regime_detector(**kwargs) -> MarketRegimeDetector:
    """Obtém instância singleton do Market Regime Detector"""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = MarketRegimeDetector(**kwargs)
    return _regime_detector


# Exemplo de uso:
"""
from analysis.market_regime import get_regime_detector, MarketRegime
import pandas as pd

detector = get_regime_detector()

# Detectar regime
regime_info = detector.detect_regime(data)
print(f"Regime: {regime_info.regime.value}")
print(f"Confiança: {regime_info.confidence:.2f}")
print(f"Estratégia recomendada: {regime_info.recommended_strategy}")

# Parâmetros adaptativos
params = detector.get_adaptive_parameters(data)
print(f"Risco ajustado: {params['risk_per_trade']:.3f}")

# Estatísticas
stats = detector.get_regime_statistics()
print(f"Regime dominante: {stats['dominant_regime']}")
"""
