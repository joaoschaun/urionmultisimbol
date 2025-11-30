# -*- coding: utf-8 -*-
"""
FEATURE ENGINEERING AVANÇADO - URION 2.0
=========================================
Geração de 50+ features para modelos de Machine Learning

Categorias de Features:
1. Price Action (10+ features)
2. Technical Indicators (15+ features)
3. Volume Analysis (5+ features)
4. Volatility (5+ features)
5. Time/Session (5+ features)
6. Market Structure (5+ features)
7. Momentum (5+ features)
8. Macro Context (5+ features)

Autor: Urion Trading Bot
Versão: 2.0
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib não disponível - usando cálculos manuais")


@dataclass
class FeatureSet:
    """Conjunto de features para um ponto no tempo"""
    timestamp: datetime
    symbol: str
    features: Dict[str, float]
    feature_names: List[str]
    target: Optional[float] = None  # Para treinamento
    
    def to_array(self) -> np.ndarray:
        """Converte para array numpy"""
        return np.array([self.features.get(name, 0.0) for name in self.feature_names])
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'features': self.features,
            'target': self.target
        }


class FeatureCategory(Enum):
    """Categorias de features"""
    PRICE_ACTION = "price_action"
    TECHNICAL = "technical"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    TIME = "time"
    STRUCTURE = "structure"
    MOMENTUM = "momentum"
    MACRO = "macro"


class AdvancedFeatureEngineer:
    """
    Engenheiro de Features Avançado
    
    Gera 50+ features para alimentar modelos de ML:
    - XGBoost Signal Predictor
    - LSTM Price Predictor
    - Reinforcement Learning Agent
    
    Features são normalizadas e prontas para uso em modelos.
    """
    
    # Lista completa de features
    FEATURE_NAMES = [
        # === PRICE ACTION (10) ===
        'returns_1bar',           # Retorno 1 barra
        'returns_5bar',           # Retorno 5 barras
        'returns_10bar',          # Retorno 10 barras
        'returns_20bar',          # Retorno 20 barras
        'high_low_range',         # Range High-Low normalizado
        'body_size',              # Tamanho do corpo da vela
        'upper_wick',             # Pavio superior
        'lower_wick',             # Pavio inferior
        'close_position',         # Posição do close no range
        'gap_size',               # Gap de abertura
        
        # === TECHNICAL INDICATORS (15) ===
        'rsi_14',                 # RSI 14 períodos
        'rsi_7',                  # RSI 7 períodos
        'macd_line',              # MACD linha
        'macd_signal',            # MACD sinal
        'macd_histogram',         # MACD histograma
        'ema_9_dist',             # Distância do preço para EMA9
        'ema_21_dist',            # Distância do preço para EMA21
        'ema_50_dist',            # Distância do preço para EMA50
        'ema_200_dist',           # Distância do preço para EMA200
        'bb_position',            # Posição nas Bollinger Bands (-1 a 1)
        'bb_width',               # Largura das Bollinger Bands
        'stoch_k',                # Stochastic %K
        'stoch_d',                # Stochastic %D
        'adx',                    # ADX
        'cci',                    # CCI
        
        # === VOLUME (5) ===
        'volume_ratio',           # Volume / Média 20
        'volume_trend',           # Tendência de volume
        'obv_change',             # Mudança OBV
        'mfi',                    # Money Flow Index
        'vwap_dist',              # Distância do VWAP
        
        # === VOLATILITY (5) ===
        'atr_14',                 # ATR 14 normalizado
        'atr_change',             # Mudança no ATR
        'historical_vol',         # Volatilidade histórica
        'bb_squeeze',             # Bollinger Band squeeze
        'volatility_regime',      # Regime de volatilidade (0=baixa, 1=normal, 2=alta)
        
        # === TIME/SESSION (5) ===
        'hour_sin',               # Hora (seno para ciclicidade)
        'hour_cos',               # Hora (cosseno)
        'day_of_week',            # Dia da semana (0-4)
        'session_quality',        # Qualidade da sessão (0-1)
        'time_to_close',          # Tempo até fechamento do mercado
        
        # === MARKET STRUCTURE (5) ===
        'support_distance',       # Distância do suporte
        'resistance_distance',    # Distância da resistência
        'trend_strength',         # Força da tendência (-1 a 1)
        'higher_highs',           # Contagem de Higher Highs
        'lower_lows',             # Contagem de Lower Lows
        
        # === MOMENTUM (5) ===
        'momentum_10',            # Momentum 10 períodos
        'roc_10',                 # Rate of Change
        'williams_r',             # Williams %R
        'tsi',                    # True Strength Index
        'ao',                     # Awesome Oscillator
        
        # === MACRO CONTEXT (5) ===
        'dxy_trend',              # Tendência DXY (-1 a 1)
        'vix_level',              # Nível VIX normalizado
        'macro_bias',             # Viés macro para o símbolo
        'risk_sentiment',         # Sentimento de risco (0-1)
        'correlation_factor',     # Fator de correlação
    ]
    
    def __init__(self, config: dict = None):
        """
        Args:
            config: Configurações do feature engineer
        """
        self.config = config or {}
        
        # Períodos padrão
        self.rsi_period = self.config.get('rsi_period', 14)
        self.atr_period = self.config.get('atr_period', 14)
        self.bb_period = self.config.get('bb_period', 20)
        self.bb_std = self.config.get('bb_std', 2.0)
        
        # Cache de dados
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._feature_cache: Dict[str, FeatureSet] = {}
        
        logger.info(f"📊 FeatureEngineer inicializado com {len(self.FEATURE_NAMES)} features")
    
    async def generate_features(
        self,
        df: pd.DataFrame,
        symbol: str,
        macro_context: dict = None
    ) -> FeatureSet:
        """
        Gera todas as features para os dados fornecidos
        
        Args:
            df: DataFrame com OHLCV (open, high, low, close, volume)
            symbol: Símbolo sendo analisado
            macro_context: Contexto macroeconômico opcional
            
        Returns:
            FeatureSet com todas as features
        """
        if len(df) < 200:
            logger.warning(f"DataFrame muito curto ({len(df)} barras) - algumas features podem ser incompletas")
        
        # Garantir que temos as colunas necessárias
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                # Tentar encontrar variações de case
                for c in df.columns:
                    if c.lower() == col:
                        df = df.rename(columns={c: col})
                        break
                else:
                    raise ValueError(f"Coluna {col} não encontrada no DataFrame")
        
        # Volume opcional
        has_volume = 'volume' in df.columns or 'tick_volume' in df.columns
        if 'tick_volume' in df.columns and 'volume' not in df.columns:
            df['volume'] = df['tick_volume']
        
        features = {}
        
        try:
            # === PRICE ACTION ===
            price_features = self._generate_price_action_features(df)
            features.update(price_features)
            
            # === TECHNICAL INDICATORS ===
            tech_features = self._generate_technical_features(df)
            features.update(tech_features)
            
            # === VOLUME ===
            if has_volume:
                volume_features = self._generate_volume_features(df)
                features.update(volume_features)
            else:
                # Preencher com zeros se não tiver volume
                for name in self.FEATURE_NAMES:
                    if name.startswith(('volume_', 'obv_', 'mfi', 'vwap_')):
                        features[name] = 0.0
            
            # === VOLATILITY ===
            vol_features = self._generate_volatility_features(df)
            features.update(vol_features)
            
            # === TIME/SESSION ===
            time_features = self._generate_time_features(df, symbol)
            features.update(time_features)
            
            # === MARKET STRUCTURE ===
            struct_features = self._generate_structure_features(df)
            features.update(struct_features)
            
            # === MOMENTUM ===
            momentum_features = self._generate_momentum_features(df)
            features.update(momentum_features)
            
            # === MACRO CONTEXT ===
            macro_features = self._generate_macro_features(symbol, macro_context)
            features.update(macro_features)
            
        except Exception as e:
            logger.error(f"Erro gerando features: {e}")
            # Preencher features faltantes com zeros
            for name in self.FEATURE_NAMES:
                if name not in features:
                    features[name] = 0.0
        
        # Normalizar features
        features = self._normalize_features(features)
        
        # Criar FeatureSet
        timestamp = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        
        return FeatureSet(
            timestamp=timestamp,
            symbol=symbol,
            features=features,
            feature_names=self.FEATURE_NAMES
        )
    
    def _generate_price_action_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Features de Price Action
        
        - Retornos de diferentes períodos
        - Características das velas
        - Gaps
        """
        features = {}
        
        close = df['close'].values
        open_ = df['open'].values
        high = df['high'].values
        low = df['low'].values
        
        # Retornos
        if len(close) >= 2:
            features['returns_1bar'] = (close[-1] - close[-2]) / close[-2] if close[-2] != 0 else 0
        else:
            features['returns_1bar'] = 0
            
        if len(close) >= 6:
            features['returns_5bar'] = (close[-1] - close[-6]) / close[-6] if close[-6] != 0 else 0
        else:
            features['returns_5bar'] = 0
            
        if len(close) >= 11:
            features['returns_10bar'] = (close[-1] - close[-11]) / close[-11] if close[-11] != 0 else 0
        else:
            features['returns_10bar'] = 0
            
        if len(close) >= 21:
            features['returns_20bar'] = (close[-1] - close[-21]) / close[-21] if close[-21] != 0 else 0
        else:
            features['returns_20bar'] = 0
        
        # Características da vela atual
        current_high = high[-1]
        current_low = low[-1]
        current_open = open_[-1]
        current_close = close[-1]
        
        range_hl = current_high - current_low
        if range_hl > 0:
            features['high_low_range'] = range_hl / close[-1]  # Normalizado pelo preço
            features['body_size'] = abs(current_close - current_open) / range_hl
            features['upper_wick'] = (current_high - max(current_open, current_close)) / range_hl
            features['lower_wick'] = (min(current_open, current_close) - current_low) / range_hl
            features['close_position'] = (current_close - current_low) / range_hl
        else:
            features['high_low_range'] = 0
            features['body_size'] = 0
            features['upper_wick'] = 0
            features['lower_wick'] = 0
            features['close_position'] = 0.5
        
        # Gap
        if len(close) >= 2:
            prev_close = close[-2]
            features['gap_size'] = (current_open - prev_close) / prev_close if prev_close != 0 else 0
        else:
            features['gap_size'] = 0
        
        return features
    
    def _generate_technical_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Features de Indicadores Técnicos
        
        - RSI
        - MACD
        - EMAs
        - Bollinger Bands
        - Stochastic
        - ADX
        - CCI
        """
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # RSI
        if TALIB_AVAILABLE:
            features['rsi_14'] = talib.RSI(close, timeperiod=14)[-1] / 100 if len(close) >= 15 else 0.5
            features['rsi_7'] = talib.RSI(close, timeperiod=7)[-1] / 100 if len(close) >= 8 else 0.5
        else:
            features['rsi_14'] = self._calculate_rsi(close, 14) / 100
            features['rsi_7'] = self._calculate_rsi(close, 7) / 100
        
        # MACD
        if TALIB_AVAILABLE and len(close) >= 35:
            macd, signal, hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            features['macd_line'] = macd[-1] / close[-1] if close[-1] != 0 else 0
            features['macd_signal'] = signal[-1] / close[-1] if close[-1] != 0 else 0
            features['macd_histogram'] = hist[-1] / close[-1] if close[-1] != 0 else 0
        else:
            macd_result = self._calculate_macd(close)
            features['macd_line'] = macd_result['macd'] / close[-1] if close[-1] != 0 else 0
            features['macd_signal'] = macd_result['signal'] / close[-1] if close[-1] != 0 else 0
            features['macd_histogram'] = macd_result['histogram'] / close[-1] if close[-1] != 0 else 0
        
        # EMAs e distâncias
        ema_periods = [9, 21, 50, 200]
        ema_names = ['ema_9_dist', 'ema_21_dist', 'ema_50_dist', 'ema_200_dist']
        
        for period, name in zip(ema_periods, ema_names):
            if len(close) >= period:
                if TALIB_AVAILABLE:
                    ema = talib.EMA(close, timeperiod=period)[-1]
                else:
                    ema = self._calculate_ema(close, period)
                features[name] = (close[-1] - ema) / close[-1] if close[-1] != 0 else 0
            else:
                features[name] = 0
        
        # Bollinger Bands
        if len(close) >= self.bb_period:
            sma = np.mean(close[-self.bb_period:])
            std = np.std(close[-self.bb_period:])
            upper = sma + self.bb_std * std
            lower = sma - self.bb_std * std
            
            bb_range = upper - lower
            if bb_range > 0:
                features['bb_position'] = (close[-1] - lower) / bb_range * 2 - 1  # -1 a 1
                features['bb_width'] = bb_range / sma if sma != 0 else 0
            else:
                features['bb_position'] = 0
                features['bb_width'] = 0
        else:
            features['bb_position'] = 0
            features['bb_width'] = 0
        
        # Stochastic
        if TALIB_AVAILABLE and len(close) >= 14:
            k, d = talib.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3)
            features['stoch_k'] = k[-1] / 100 if not np.isnan(k[-1]) else 0.5
            features['stoch_d'] = d[-1] / 100 if not np.isnan(d[-1]) else 0.5
        else:
            stoch = self._calculate_stochastic(high, low, close)
            features['stoch_k'] = stoch['k'] / 100
            features['stoch_d'] = stoch['d'] / 100
        
        # ADX
        if TALIB_AVAILABLE and len(close) >= 14:
            features['adx'] = talib.ADX(high, low, close, timeperiod=14)[-1] / 100 if len(close) >= 28 else 0
        else:
            features['adx'] = self._calculate_adx(high, low, close) / 100
        
        # CCI
        if TALIB_AVAILABLE and len(close) >= 20:
            cci = talib.CCI(high, low, close, timeperiod=20)[-1]
            features['cci'] = np.clip(cci / 200, -1, 1)  # Normalizar para -1 a 1
        else:
            features['cci'] = 0
        
        return features
    
    def _generate_volume_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Features de Volume
        
        - Ratio vs média
        - Tendência
        - OBV
        - MFI
        - VWAP
        """
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values if 'volume' in df.columns else np.ones(len(close))
        
        # Volume ratio
        if len(volume) >= 20:
            vol_mean = np.mean(volume[-20:])
            features['volume_ratio'] = volume[-1] / vol_mean if vol_mean > 0 else 1.0
            
            # Volume trend (slope of volume over last 10 bars)
            if len(volume) >= 10:
                vol_10 = volume[-10:]
                x = np.arange(10)
                if np.std(vol_10) > 0:
                    slope = np.polyfit(x, vol_10, 1)[0]
                    features['volume_trend'] = slope / vol_mean if vol_mean > 0 else 0
                else:
                    features['volume_trend'] = 0
            else:
                features['volume_trend'] = 0
        else:
            features['volume_ratio'] = 1.0
            features['volume_trend'] = 0
        
        # OBV
        if len(close) >= 2:
            obv = self._calculate_obv(close, volume)
            obv_change = (obv[-1] - obv[-2]) / abs(obv[-2]) if obv[-2] != 0 else 0
            features['obv_change'] = np.clip(obv_change, -1, 1)
        else:
            features['obv_change'] = 0
        
        # MFI
        if TALIB_AVAILABLE and len(close) >= 14:
            features['mfi'] = talib.MFI(high, low, close, volume, timeperiod=14)[-1] / 100
        else:
            features['mfi'] = self._calculate_mfi(high, low, close, volume) / 100
        
        # VWAP distance
        if len(close) >= 20:
            vwap = self._calculate_vwap(close, high, low, volume)
            features['vwap_dist'] = (close[-1] - vwap) / close[-1] if close[-1] != 0 else 0
        else:
            features['vwap_dist'] = 0
        
        return features
    
    def _generate_volatility_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Features de Volatilidade
        
        - ATR
        - Volatilidade histórica
        - BB Squeeze
        - Regime de volatilidade
        """
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # ATR normalizado
        if TALIB_AVAILABLE and len(close) >= 14:
            atr = talib.ATR(high, low, close, timeperiod=14)[-1]
            features['atr_14'] = atr / close[-1] if close[-1] != 0 else 0
            
            # ATR change
            if len(close) >= 15:
                atr_prev = talib.ATR(high, low, close, timeperiod=14)[-2]
                features['atr_change'] = (atr - atr_prev) / atr_prev if atr_prev != 0 else 0
            else:
                features['atr_change'] = 0
        else:
            atr = self._calculate_atr(high, low, close)
            features['atr_14'] = atr / close[-1] if close[-1] != 0 else 0
            features['atr_change'] = 0
        
        # Historical volatility (20-day)
        if len(close) >= 21:
            returns = np.diff(np.log(close[-21:]))
            features['historical_vol'] = np.std(returns) * np.sqrt(252)  # Anualizada
        else:
            features['historical_vol'] = 0
        
        # BB Squeeze
        if len(close) >= 20:
            # BB width
            sma = np.mean(close[-20:])
            std = np.std(close[-20:])
            bb_width = (4 * std) / sma if sma != 0 else 0
            
            # Keltner width (using ATR)
            atr = features.get('atr_14', 0) * close[-1]
            kc_width = (4 * atr) / sma if sma != 0 else 0
            
            # Squeeze = BB inside KC
            features['bb_squeeze'] = 1.0 if bb_width < kc_width else 0.0
        else:
            features['bb_squeeze'] = 0.0
        
        # Volatility regime
        if len(close) >= 100:
            current_vol = features.get('historical_vol', 0)
            vol_history = []
            for i in range(80, 0, -20):
                if len(close) >= i + 21:
                    returns = np.diff(np.log(close[-(i+21):-(i+1)]))
                    vol_history.append(np.std(returns) * np.sqrt(252))
            
            if vol_history:
                vol_mean = np.mean(vol_history)
                vol_std = np.std(vol_history)
                
                if vol_std > 0:
                    z_score = (current_vol - vol_mean) / vol_std
                    if z_score < -0.5:
                        features['volatility_regime'] = 0  # Baixa
                    elif z_score > 0.5:
                        features['volatility_regime'] = 2  # Alta
                    else:
                        features['volatility_regime'] = 1  # Normal
                else:
                    features['volatility_regime'] = 1
            else:
                features['volatility_regime'] = 1
        else:
            features['volatility_regime'] = 1
        
        # Normalizar regime para 0-1
        features['volatility_regime'] = features['volatility_regime'] / 2.0
        
        return features
    
    def _generate_time_features(self, df: pd.DataFrame, symbol: str) -> Dict[str, float]:
        """
        Features de Tempo/Sessão
        
        - Hora (cíclica)
        - Dia da semana
        - Qualidade da sessão
        """
        features = {}
        
        # Obter timestamp
        if isinstance(df.index, pd.DatetimeIndex):
            ts = df.index[-1]
        else:
            ts = datetime.now()
        
        # Hora (encoding cíclico para capturar natureza circular)
        hour = ts.hour
        features['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        features['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        
        # Dia da semana (0 = Monday, 4 = Friday)
        features['day_of_week'] = ts.weekday() / 4  # Normalizado 0-1
        
        # Qualidade da sessão
        # Mapeamento simples baseado em horário UTC
        hour_utc = hour  # Assumindo UTC
        
        # Sobreposição London-NY (12:00-16:00 UTC) = melhor
        # London (07:00-16:00 UTC) e NY (12:00-21:00 UTC) = bom
        # Tokyo (00:00-09:00 UTC) = moderado
        # Sydney (21:00-06:00 UTC) = fraco
        
        if 12 <= hour_utc < 16:  # Overlap London-NY
            session_quality = 1.0
        elif 7 <= hour_utc < 21:  # London ou NY
            session_quality = 0.8
        elif 0 <= hour_utc < 9:  # Tokyo
            session_quality = 0.5
        else:  # Sydney ou fora de sessão
            session_quality = 0.3
        
        features['session_quality'] = session_quality
        
        # Tempo até fechamento (simplificado - considera NY close às 21:00 UTC)
        ny_close = 21  # 21:00 UTC
        hours_to_close = (ny_close - hour_utc) % 24
        features['time_to_close'] = hours_to_close / 24
        
        return features
    
    def _generate_structure_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Features de Estrutura de Mercado
        
        - Suporte/Resistência
        - Força da tendência
        - Higher Highs / Lower Lows
        """
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Suporte e Resistência (pivots dos últimos 50 bars)
        lookback = min(50, len(close) - 1)
        if lookback >= 10:
            recent_high = np.max(high[-lookback:])
            recent_low = np.min(low[-lookback:])
            
            current_price = close[-1]
            price_range = recent_high - recent_low
            
            if price_range > 0:
                features['resistance_distance'] = (recent_high - current_price) / price_range
                features['support_distance'] = (current_price - recent_low) / price_range
            else:
                features['resistance_distance'] = 0.5
                features['support_distance'] = 0.5
        else:
            features['resistance_distance'] = 0.5
            features['support_distance'] = 0.5
        
        # Trend strength baseado em EMAs
        if len(close) >= 50:
            ema_9 = self._calculate_ema(close, 9)
            ema_21 = self._calculate_ema(close, 21)
            ema_50 = self._calculate_ema(close, 50)
            
            # Score de tendência
            trend_score = 0
            if close[-1] > ema_9:
                trend_score += 0.33
            if ema_9 > ema_21:
                trend_score += 0.33
            if ema_21 > ema_50:
                trend_score += 0.34
            
            # Converter para -1 a 1 (considerando tendência de baixa)
            if close[-1] < ema_9 and ema_9 < ema_21 and ema_21 < ema_50:
                features['trend_strength'] = -1.0
            elif trend_score > 0.5:
                features['trend_strength'] = trend_score
            elif trend_score < 0.5:
                features['trend_strength'] = trend_score - 1.0
            else:
                features['trend_strength'] = 0.0
        else:
            features['trend_strength'] = 0.0
        
        # Higher Highs / Lower Lows
        if len(high) >= 20:
            # Contar quantos highs consecutivos são maiores que o anterior
            hh_count = 0
            ll_count = 0
            
            for i in range(-20, -1):
                if high[i] > high[i-1]:
                    hh_count += 1
                if low[i] < low[i-1]:
                    ll_count += 1
            
            features['higher_highs'] = hh_count / 19  # Normalizado
            features['lower_lows'] = ll_count / 19
        else:
            features['higher_highs'] = 0.5
            features['lower_lows'] = 0.5
        
        return features
    
    def _generate_momentum_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Features de Momentum
        
        - Momentum
        - Rate of Change
        - Williams %R
        - TSI
        - Awesome Oscillator
        """
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Momentum
        if len(close) >= 11:
            features['momentum_10'] = (close[-1] - close[-11]) / close[-11] if close[-11] != 0 else 0
        else:
            features['momentum_10'] = 0
        
        # Rate of Change
        if TALIB_AVAILABLE and len(close) >= 11:
            features['roc_10'] = talib.ROC(close, timeperiod=10)[-1] / 100
        else:
            features['roc_10'] = features['momentum_10']
        
        # Williams %R
        if TALIB_AVAILABLE and len(close) >= 14:
            willr = talib.WILLR(high, low, close, timeperiod=14)[-1]
            features['williams_r'] = (willr + 100) / 100  # Normalizar de 0 a 1
        else:
            if len(close) >= 14:
                highest_high = np.max(high[-14:])
                lowest_low = np.min(low[-14:])
                if highest_high != lowest_low:
                    willr = (highest_high - close[-1]) / (highest_high - lowest_low) * -100
                    features['williams_r'] = (willr + 100) / 100
                else:
                    features['williams_r'] = 0.5
            else:
                features['williams_r'] = 0.5
        
        # TSI (True Strength Index) - simplificado
        if len(close) >= 26:
            price_change = np.diff(close)
            
            # Double smoothed momentum
            ema1 = self._calculate_ema(price_change[-25:], 25)
            abs_ema1 = self._calculate_ema(np.abs(price_change[-25:]), 25)
            
            if abs_ema1 != 0:
                features['tsi'] = ema1 / abs_ema1
            else:
                features['tsi'] = 0
        else:
            features['tsi'] = 0
        
        # Awesome Oscillator
        if len(close) >= 34:
            mid = (high + low) / 2
            sma5 = np.mean(mid[-5:])
            sma34 = np.mean(mid[-34:])
            
            ao = sma5 - sma34
            features['ao'] = ao / close[-1] if close[-1] != 0 else 0
        else:
            features['ao'] = 0
        
        return features
    
    def _generate_macro_features(
        self,
        symbol: str,
        macro_context: dict = None
    ) -> Dict[str, float]:
        """
        Features de Contexto Macroeconômico
        
        - DXY trend
        - VIX level
        - Symbol bias
        - Risk sentiment
        - Correlation factor
        """
        features = {}
        
        if macro_context:
            # DXY trend (-1 a 1)
            dxy_trends = {
                'strong_bullish': 1.0,
                'bullish': 0.5,
                'neutral': 0.0,
                'bearish': -0.5,
                'strong_bearish': -1.0
            }
            features['dxy_trend'] = dxy_trends.get(
                macro_context.get('dxy_trend', 'neutral'), 0.0
            )
            
            # VIX level (normalizado)
            vix_levels = {
                'complacent': 0.0,
                'low': 0.2,
                'normal': 0.4,
                'elevated': 0.6,
                'high': 0.8,
                'extreme': 1.0
            }
            features['vix_level'] = vix_levels.get(
                macro_context.get('vix_level', 'normal'), 0.4
            )
            
            # Bias específico do símbolo
            biases = macro_context.get('biases', {})
            features['macro_bias'] = biases.get(symbol.upper(), 0.0)
            
            # Risk sentiment
            sentiments = {
                'extreme_fear': 0.0,
                'fear': 0.25,
                'neutral': 0.5,
                'greed': 0.75,
                'extreme_greed': 1.0
            }
            features['risk_sentiment'] = sentiments.get(
                macro_context.get('market_sentiment', 'neutral'), 0.5
            )
            
            # Correlation factor (risk multiplier)
            features['correlation_factor'] = macro_context.get('risk_multiplier', 1.0)
            
        else:
            # Valores default neutros
            features['dxy_trend'] = 0.0
            features['vix_level'] = 0.4
            features['macro_bias'] = 0.0
            features['risk_sentiment'] = 0.5
            features['correlation_factor'] = 1.0
        
        return features
    
    def _normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        Normaliza features para range adequado
        
        Maioria já está em range -1 a 1 ou 0 a 1
        Esta função trata outliers e valores extremos
        """
        normalized = {}
        
        for name, value in features.items():
            if value is None or np.isnan(value) or np.isinf(value):
                normalized[name] = 0.0
            else:
                # Clipar valores extremos
                normalized[name] = float(np.clip(value, -10.0, 10.0))
        
        return normalized
    
    # ============================================
    # FUNÇÕES AUXILIARES DE CÁLCULO
    # ============================================
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calcula RSI manualmente"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calcula EMA manualmente"""
        if len(prices) < period:
            return prices[-1] if len(prices) > 0 else 0
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_macd(self, prices: np.ndarray) -> dict:
        """Calcula MACD manualmente"""
        if len(prices) < 26:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        macd_line = ema_12 - ema_26
        
        # Para signal, precisamos do histórico do MACD
        # Simplificação: usar valor atual
        signal = macd_line * 0.9  # Aproximação
        histogram = macd_line - signal
        
        return {
            'macd': macd_line,
            'signal': signal,
            'histogram': histogram
        }
    
    def _calculate_stochastic(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> dict:
        """Calcula Stochastic manualmente"""
        if len(close) < period:
            return {'k': 50, 'd': 50}
        
        highest_high = np.max(high[-period:])
        lowest_low = np.min(low[-period:])
        
        if highest_high == lowest_low:
            return {'k': 50, 'd': 50}
        
        k = (close[-1] - lowest_low) / (highest_high - lowest_low) * 100
        d = k  # Simplificação
        
        return {'k': k, 'd': d}
    
    def _calculate_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> float:
        """Calcula ATR manualmente"""
        if len(close) < 2:
            return 0
        
        tr_list = []
        for i in range(1, min(period + 1, len(close))):
            tr = max(
                high[-i] - low[-i],
                abs(high[-i] - close[-i-1]),
                abs(low[-i] - close[-i-1])
            )
            tr_list.append(tr)
        
        return np.mean(tr_list) if tr_list else 0
    
    def _calculate_adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> float:
        """Calcula ADX manualmente (simplificado)"""
        if len(close) < period:
            return 25  # Valor neutro
        
        # Simplificação baseada em range
        avg_range = np.mean(high[-period:] - low[-period:])
        avg_price = np.mean(close[-period:])
        
        if avg_price == 0:
            return 25
        
        # ADX aproximado pelo range relativo
        return min(100, (avg_range / avg_price) * 1000)
    
    def _calculate_obv(self, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """Calcula OBV"""
        obv = np.zeros(len(close))
        obv[0] = volume[0]
        
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        
        return obv
    
    def _calculate_mfi(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        period: int = 14
    ) -> float:
        """Calcula MFI manualmente"""
        if len(close) < period + 1:
            return 50
        
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        
        pos_flow = 0
        neg_flow = 0
        
        for i in range(-period, 0):
            if typical_price[i] > typical_price[i-1]:
                pos_flow += money_flow[i]
            else:
                neg_flow += money_flow[i]
        
        if neg_flow == 0:
            return 100
        
        mfi_ratio = pos_flow / neg_flow
        return 100 - (100 / (1 + mfi_ratio))
    
    def _calculate_vwap(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        period: int = 20
    ) -> float:
        """Calcula VWAP"""
        if len(close) < period:
            return close[-1] if len(close) > 0 else 0
        
        typical_price = (high[-period:] + low[-period:] + close[-period:]) / 3
        vol = volume[-period:]
        
        if np.sum(vol) == 0:
            return close[-1]
        
        return np.sum(typical_price * vol) / np.sum(vol)
    
    def get_feature_importance_template(self) -> Dict[str, float]:
        """
        Retorna template de importância de features
        Pode ser usado para inicializar modelos ou análise
        """
        # Importâncias estimadas baseadas em experiência de trading
        importance = {
            # Price action - geralmente muito importante
            'returns_1bar': 0.8,
            'returns_5bar': 0.7,
            'body_size': 0.6,
            'close_position': 0.5,
            
            # Technical - importantes para timing
            'rsi_14': 0.9,
            'macd_histogram': 0.85,
            'bb_position': 0.8,
            'adx': 0.75,
            
            # Volume - moderadamente importante
            'volume_ratio': 0.7,
            'mfi': 0.65,
            
            # Volatility - importante para sizing
            'atr_14': 0.8,
            'bb_squeeze': 0.7,
            
            # Time - pode ser crucial
            'session_quality': 0.85,
            'hour_sin': 0.6,
            
            # Structure - muito importante para direção
            'trend_strength': 0.9,
            'support_distance': 0.75,
            
            # Momentum
            'momentum_10': 0.7,
            'tsi': 0.65,
            
            # Macro
            'macro_bias': 0.8,
            'vix_level': 0.7
        }
        
        # Preencher features faltantes com importância média
        for name in self.FEATURE_NAMES:
            if name not in importance:
                importance[name] = 0.5
        
        return importance


# =======================
# EXEMPLO DE USO
# =======================

async def example_usage():
    """Exemplo de uso do FeatureEngineer"""
    
    # Criar dados de exemplo
    np.random.seed(42)
    n = 300
    
    dates = pd.date_range(end=datetime.now(), periods=n, freq='H')
    
    # Gerar OHLCV sintético
    close = 2000 + np.cumsum(np.random.randn(n) * 5)
    high = close + np.random.rand(n) * 10
    low = close - np.random.rand(n) * 10
    open_ = close + np.random.randn(n) * 3
    volume = np.random.randint(1000, 10000, n)
    
    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    
    # Criar feature engineer
    engineer = AdvancedFeatureEngineer()
    
    # Gerar features
    feature_set = await engineer.generate_features(
        df=df,
        symbol='XAUUSD',
        macro_context={
            'dxy_trend': 'bearish',
            'vix_level': 'elevated',
            'biases': {'XAUUSD': 0.3},
            'market_sentiment': 'fear',
            'risk_multiplier': 0.8
        }
    )
    
    print(f"📊 Features geradas: {len(feature_set.feature_names)}")
    print(f"\n🔢 Amostra de features:")
    
    for name in feature_set.feature_names[:10]:
        value = feature_set.features.get(name, 0)
        print(f"   {name}: {value:.4f}")
    
    print(f"\n📈 Array shape: {feature_set.to_array().shape}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
