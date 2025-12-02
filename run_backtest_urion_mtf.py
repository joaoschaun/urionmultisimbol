"""
BACKTEST URION MULTI-TIMEFRAME - DADOS REAIS MT5
Simula o comportamento REAL do bot com múltiplos timeframes

Estratégias:
- TrendFollowing: Usa H1 como principal, confirma com H4/D1
- MeanReversion: Usa H1, confirma com D1
- Breakout: Usa H1, confirma com H4
- Scalping: Usa M15, confirma com H1
- RangeTrading: Usa H1, confirma com D1

Autor: URION Bot
Data: 2025-12-01
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import json
import os
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.02  # 2%
MAX_POSITIONS = 3
SPREAD_PIPS = 2.5
COMMISSION_PER_LOT = 7.0
SLIPPAGE_PIPS = 0.5

# =============================================================================
# ESTRUTURAS DE DADOS
# =============================================================================
@dataclass
class Trade:
    id: int
    strategy: str
    direction: str
    entry_time: datetime
    entry_price: float
    sl: float
    tp: float
    size: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    profit: Optional[float] = None
    exit_reason: Optional[str] = None


# =============================================================================
# INDICADORES TÉCNICOS
# =============================================================================
class TechnicalIndicators:
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        return data.rolling(window=period).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {'macd': macd_line, 'signal': signal_line, 'histogram': histogram}
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict:
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        dm_plus = high.diff()
        dm_minus = -low.diff()
        dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0)
        dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0)
        
        di_plus = 100 * (dm_plus.rolling(window=period).mean() / atr)
        di_minus = 100 * (dm_minus.rolling(window=period).mean() / atr)
        
        dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus + 0.0001)
        adx = dx.rolling(window=period).mean()
        
        return {'adx': adx, 'di_plus': di_plus, 'di_minus': di_minus}
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def bollinger(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict:
        middle = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return {'upper': upper, 'middle': middle, 'lower': lower}
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                   k_period: int = 14, d_period: int = 3) -> Dict:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low + 0.0001)
        d = k.rolling(window=d_period).mean()
        return {'k': k, 'd': d}


# =============================================================================
# DATA MANAGER - MULTI-TIMEFRAME
# =============================================================================
class MultiTimeframeData:
    """Gerencia dados de múltiplos timeframes sincronizados"""
    
    def __init__(self):
        self.data = {}
        self.indicators = {}
    
    def load_data(self):
        """Carrega todos os timeframes"""
        files = {
            'M15': 'data/xauusd_5years_m15.csv',
            'H1': 'data/xauusd_5years_h1.csv',
            'H4': 'data/xauusd_5years_h4.csv',
            'D1': 'data/xauusd_5years_d1.csv'
        }
        
        for tf, filepath in files.items():
            if os.path.exists(filepath):
                df = pd.read_csv(filepath)
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                df.rename(columns={
                    'open': 'Open', 'high': 'High',
                    'low': 'Low', 'close': 'Close',
                    'tick_volume': 'Volume'
                }, inplace=True)
                self.data[tf] = df
                print(f"   {tf}: {len(df):,} candles carregados")
            else:
                print(f"   {tf}: ARQUIVO NÃO ENCONTRADO")
    
    def calculate_indicators(self, tf: str) -> Dict:
        """Calcula indicadores para um timeframe"""
        df = self.data[tf]
        
        indicators = {
            'open': df['Open'],
            'high': df['High'],
            'low': df['Low'],
            'close': df['Close'],
            'volume': df['Volume'] if 'Volume' in df else pd.Series(0, index=df.index)
        }
        
        # EMAs
        indicators['ema_9'] = TechnicalIndicators.ema(df['Close'], 9)
        indicators['ema_21'] = TechnicalIndicators.ema(df['Close'], 21)
        indicators['ema_50'] = TechnicalIndicators.ema(df['Close'], 50)
        indicators['ema_200'] = TechnicalIndicators.ema(df['Close'], 200)
        
        # RSI
        indicators['rsi'] = TechnicalIndicators.rsi(df['Close'], 14)
        
        # MACD
        macd = TechnicalIndicators.macd(df['Close'])
        indicators['macd_line'] = macd['macd']
        indicators['macd_signal'] = macd['signal']
        indicators['macd_hist'] = macd['histogram']
        
        # ADX
        adx = TechnicalIndicators.adx(df['High'], df['Low'], df['Close'])
        indicators['adx'] = adx['adx']
        indicators['di_plus'] = adx['di_plus']
        indicators['di_minus'] = adx['di_minus']
        
        # ATR
        indicators['atr'] = TechnicalIndicators.atr(df['High'], df['Low'], df['Close'])
        
        # Bollinger
        bb = TechnicalIndicators.bollinger(df['Close'])
        indicators['bb_upper'] = bb['upper']
        indicators['bb_middle'] = bb['middle']
        indicators['bb_lower'] = bb['lower']
        
        # Stochastic
        stoch = TechnicalIndicators.stochastic(df['High'], df['Low'], df['Close'])
        indicators['stoch_k'] = stoch['k']
        indicators['stoch_d'] = stoch['d']
        
        self.indicators[tf] = indicators
        return indicators
    
    def get_indicator_at_time(self, tf: str, indicator: str, timestamp: datetime):
        """Obtém valor do indicador no timestamp mais próximo"""
        if tf not in self.indicators:
            return None
        
        ind_data = self.indicators[tf][indicator]
        
        # Encontrar o índice mais próximo <= timestamp
        valid_times = ind_data.index[ind_data.index <= timestamp]
        if len(valid_times) == 0:
            return None
        
        closest_time = valid_times[-1]
        return ind_data.loc[closest_time]
    
    def get_all_indicators_at_time(self, tf: str, timestamp: datetime) -> Optional[Dict]:
        """Obtém todos os indicadores para um timestamp"""
        if tf not in self.indicators:
            return None
        
        result = {}
        for name, data in self.indicators[tf].items():
            valid_times = data.index[data.index <= timestamp]
            if len(valid_times) > 0:
                result[name] = data.loc[valid_times[-1]]
            else:
                result[name] = None
        
        return result


# =============================================================================
# ESTRATÉGIAS MULTI-TIMEFRAME
# =============================================================================
class TrendFollowingMTF:
    """TrendFollowing com confirmação multi-timeframe"""
    
    def __init__(self):
        self.name = 'TrendFollowing'
        self.primary_tf = 'H1'
        self.confirm_tf = 'H4'
        self.macro_tf = 'D1'
        self.min_confidence = 0.55
    
    def analyze(self, mtf_data: MultiTimeframeData, timestamp: datetime) -> Optional[Dict]:
        try:
            # Dados do timeframe principal (H1)
            h1 = mtf_data.get_all_indicators_at_time('H1', timestamp)
            if h1 is None or h1.get('adx') is None:
                return None
            
            # Dados de confirmação (H4)
            h4 = mtf_data.get_all_indicators_at_time('H4', timestamp)
            
            # Dados macro (D1)
            d1 = mtf_data.get_all_indicators_at_time('D1', timestamp)
            
            # Extrair indicadores H1
            adx = h1['adx']
            di_plus = h1['di_plus']
            di_minus = h1['di_minus']
            ema_9 = h1['ema_9']
            ema_21 = h1['ema_21']
            ema_50 = h1['ema_50']
            rsi = h1['rsi']
            macd_hist = h1['macd_hist']
            price = h1['close']
            atr = h1['atr']
            
            if pd.isna(adx) or pd.isna(ema_50) or pd.isna(price):
                return None
            
            # Score BULLISH
            bullish_score = 0
            if adx > 25:
                bullish_score += 2
            if di_plus > di_minus:
                bullish_score += 1
            if ema_9 > ema_21 > ema_50:
                bullish_score += 2
            if price > ema_9:
                bullish_score += 1
            if macd_hist > 0:
                bullish_score += 1
            if 35 < rsi < 70:
                bullish_score += 1
            
            # Confirmação H4
            if h4 and h4.get('ema_9') and h4.get('ema_21'):
                if h4['ema_9'] > h4['ema_21']:
                    bullish_score += 1
            
            # Confirmação D1 (tendência macro)
            if d1 and d1.get('ema_21') and d1.get('ema_50'):
                if d1['ema_21'] > d1['ema_50']:
                    bullish_score += 1
            
            # Score BEARISH
            bearish_score = 0
            if adx > 25:
                bearish_score += 2
            if di_minus > di_plus:
                bearish_score += 1
            if ema_9 < ema_21 < ema_50:
                bearish_score += 2
            if price < ema_9:
                bearish_score += 1
            if macd_hist < 0:
                bearish_score += 1
            if 30 < rsi < 65:
                bearish_score += 1
            
            # Confirmação H4
            if h4 and h4.get('ema_9') and h4.get('ema_21'):
                if h4['ema_9'] < h4['ema_21']:
                    bearish_score += 1
            
            # Confirmação D1
            if d1 and d1.get('ema_21') and d1.get('ema_50'):
                if d1['ema_21'] < d1['ema_50']:
                    bearish_score += 1
            
            max_score = 10
            
            if bullish_score > bearish_score and bullish_score >= 6:
                atr_pips = atr / 0.1 if not pd.isna(atr) else 30
                return {
                    'action': 'BUY',
                    'confidence': bullish_score / max_score,
                    'sl_pips': max(30, min(atr_pips * 2.5, 80)),
                    'tp_pips': max(60, min(atr_pips * 5.0, 160))
                }
            
            elif bearish_score > bullish_score and bearish_score >= 6:
                atr_pips = atr / 0.1 if not pd.isna(atr) else 30
                return {
                    'action': 'SELL',
                    'confidence': bearish_score / max_score,
                    'sl_pips': max(30, min(atr_pips * 2.5, 80)),
                    'tp_pips': max(60, min(atr_pips * 5.0, 160))
                }
            
            return None
            
        except Exception as e:
            return None


class MeanReversionMTF:
    """MeanReversion com confirmação multi-timeframe"""
    
    def __init__(self):
        self.name = 'MeanReversion'
        self.primary_tf = 'H1'
        self.confirm_tf = 'D1'
        self.min_confidence = 0.55
    
    def analyze(self, mtf_data: MultiTimeframeData, timestamp: datetime) -> Optional[Dict]:
        try:
            h1 = mtf_data.get_all_indicators_at_time('H1', timestamp)
            d1 = mtf_data.get_all_indicators_at_time('D1', timestamp)
            
            if h1 is None or h1.get('rsi') is None:
                return None
            
            rsi = h1['rsi']
            price = h1['close']
            bb_upper = h1['bb_upper']
            bb_lower = h1['bb_lower']
            stoch_k = h1['stoch_k']
            stoch_d = h1['stoch_d']
            macd_hist = h1['macd_hist']
            atr = h1['atr']
            
            if pd.isna(rsi) or pd.isna(bb_upper):
                return None
            
            # Verificar se D1 está em tendência (evitar reversão contra tendência forte)
            d1_trending = False
            if d1 and d1.get('adx'):
                d1_trending = d1['adx'] > 30
            
            # OVERSOLD (compra na reversão)
            oversold_score = 0
            if rsi < 30:
                oversold_score += 2
            if rsi < 25:
                oversold_score += 1
            if price < bb_lower:
                oversold_score += 2
            if stoch_k < 20:
                oversold_score += 1
            if stoch_k > stoch_d:
                oversold_score += 1
            
            # Penalidade se D1 está em forte tendência de baixa
            if d1_trending and d1 and d1.get('macd_hist') and d1['macd_hist'] < 0:
                oversold_score -= 2
            
            # OVERBOUGHT (venda na reversão)
            overbought_score = 0
            if rsi > 70:
                overbought_score += 2
            if rsi > 75:
                overbought_score += 1
            if price > bb_upper:
                overbought_score += 2
            if stoch_k > 80:
                overbought_score += 1
            if stoch_k < stoch_d:
                overbought_score += 1
            
            # Penalidade se D1 está em forte tendência de alta
            if d1_trending and d1 and d1.get('macd_hist') and d1['macd_hist'] > 0:
                overbought_score -= 2
            
            max_score = 7
            atr_pips = atr / 0.1 if not pd.isna(atr) else 20
            
            if oversold_score >= 4:
                return {
                    'action': 'BUY',
                    'confidence': oversold_score / max_score,
                    'sl_pips': max(15, min(atr_pips * 1.5, 40)),
                    'tp_pips': max(30, min(atr_pips * 3.0, 80))
                }
            
            elif overbought_score >= 4:
                return {
                    'action': 'SELL',
                    'confidence': overbought_score / max_score,
                    'sl_pips': max(15, min(atr_pips * 1.5, 40)),
                    'tp_pips': max(30, min(atr_pips * 3.0, 80))
                }
            
            return None
            
        except Exception as e:
            return None


class BreakoutMTF:
    """Breakout com confirmação multi-timeframe"""
    
    def __init__(self):
        self.name = 'Breakout'
        self.primary_tf = 'H1'
        self.confirm_tf = 'H4'
        self.min_confidence = 0.55
        self.lookback = 20
    
    def analyze(self, mtf_data: MultiTimeframeData, timestamp: datetime) -> Optional[Dict]:
        try:
            h1 = mtf_data.get_all_indicators_at_time('H1', timestamp)
            h4 = mtf_data.get_all_indicators_at_time('H4', timestamp)
            
            if h1 is None:
                return None
            
            price = h1['close']
            high = h1['high']
            low = h1['low']
            atr = h1['atr']
            adx = h1['adx']
            macd_hist = h1['macd_hist']
            
            if pd.isna(price) or pd.isna(atr):
                return None
            
            # Obter dados históricos para S/R
            h1_data = mtf_data.data['H1']
            valid_data = h1_data[h1_data.index <= timestamp].tail(self.lookback + 1)
            
            if len(valid_data) < self.lookback:
                return None
            
            resistance = valid_data['High'].iloc[:-1].max()
            support = valid_data['Low'].iloc[:-1].min()
            avg_volume = valid_data['Volume'].iloc[:-1].mean() if 'Volume' in valid_data else 1
            current_volume = valid_data['Volume'].iloc[-1] if 'Volume' in valid_data else 1
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Breakout BULLISH
            bullish_score = 0
            if high > resistance:
                bullish_score += 3
            if price > resistance:
                bullish_score += 2
            if volume_ratio > 1.2:
                bullish_score += 2
            if adx > 20:
                bullish_score += 1
            if macd_hist > 0:
                bullish_score += 1
            
            # Confirmação H4
            if h4 and h4.get('macd_hist') and h4['macd_hist'] > 0:
                bullish_score += 1
            
            # Breakout BEARISH
            bearish_score = 0
            if low < support:
                bearish_score += 3
            if price < support:
                bearish_score += 2
            if volume_ratio > 1.2:
                bearish_score += 2
            if adx > 20:
                bearish_score += 1
            if macd_hist < 0:
                bearish_score += 1
            
            # Confirmação H4
            if h4 and h4.get('macd_hist') and h4['macd_hist'] < 0:
                bearish_score += 1
            
            max_score = 10
            atr_pips = atr / 0.1 if not pd.isna(atr) else 25
            
            if bullish_score >= 5:
                return {
                    'action': 'BUY',
                    'confidence': bullish_score / max_score,
                    'sl_pips': max(20, min(atr_pips * 2.0, 50)),
                    'tp_pips': max(40, min(atr_pips * 4.0, 100))
                }
            
            elif bearish_score >= 5:
                return {
                    'action': 'SELL',
                    'confidence': bearish_score / max_score,
                    'sl_pips': max(20, min(atr_pips * 2.0, 50)),
                    'tp_pips': max(40, min(atr_pips * 4.0, 100))
                }
            
            return None
            
        except Exception as e:
            return None


class ScalpingMTF:
    """Scalping em M15 com confirmação H1"""
    
    def __init__(self):
        self.name = 'Scalping'
        self.primary_tf = 'M15'
        self.confirm_tf = 'H1'
        self.min_confidence = 0.50
    
    def analyze(self, mtf_data: MultiTimeframeData, timestamp: datetime) -> Optional[Dict]:
        try:
            m15 = mtf_data.get_all_indicators_at_time('M15', timestamp)
            h1 = mtf_data.get_all_indicators_at_time('H1', timestamp)
            
            if m15 is None or m15.get('rsi') is None:
                return None
            
            rsi = m15['rsi']
            price = m15['close']
            bb_upper = m15['bb_upper']
            bb_lower = m15['bb_lower']
            macd_hist = m15['macd_hist']
            macd_line = m15['macd_line']
            macd_signal = m15['macd_signal']
            stoch_k = m15['stoch_k']
            stoch_d = m15['stoch_d']
            ema_9 = m15['ema_9']
            ema_21 = m15['ema_21']
            atr = m15['atr']
            
            if pd.isna(rsi) or pd.isna(bb_upper):
                return None
            
            # RSI no range
            if rsi < 35 or rsi > 65:
                return None
            
            # Volatilidade adequada
            atr_pips = atr / 0.1 if not pd.isna(atr) else 10
            if atr_pips < 2 or atr_pips > 25:
                return None
            
            # BB position
            bb_range = bb_upper - bb_lower
            if bb_range <= 0:
                return None
            bb_position = (price - bb_lower) / bb_range
            
            # Score BULLISH
            bullish_score = 0
            if macd_hist > 0 and macd_line > macd_signal:
                bullish_score += 1
                if bb_position < 0.30:
                    bullish_score += 2
            if stoch_k > stoch_d and stoch_k < 80:
                bullish_score += 1
            if stoch_k < 30:
                bullish_score += 1
            if price > ema_9:
                bullish_score += 1
            
            # Confirmação H1
            if h1 and h1.get('macd_hist') and h1['macd_hist'] > 0:
                bullish_score += 1
            
            # Score BEARISH
            bearish_score = 0
            if macd_hist < 0 and macd_line < macd_signal:
                bearish_score += 1
                if bb_position > 0.70:
                    bearish_score += 2
            if stoch_k < stoch_d and stoch_k > 20:
                bearish_score += 1
            if stoch_k > 70:
                bearish_score += 1
            if price < ema_9:
                bearish_score += 1
            
            # Confirmação H1
            if h1 and h1.get('macd_hist') and h1['macd_hist'] < 0:
                bearish_score += 1
            
            max_score = 7
            
            if bullish_score >= 3:
                return {
                    'action': 'BUY',
                    'confidence': bullish_score / max_score,
                    'sl_pips': max(5, min(atr_pips * 1.0, 15)),
                    'tp_pips': max(8, min(atr_pips * 1.5, 25))
                }
            
            elif bearish_score >= 3:
                return {
                    'action': 'SELL',
                    'confidence': bearish_score / max_score,
                    'sl_pips': max(5, min(atr_pips * 1.0, 15)),
                    'tp_pips': max(8, min(atr_pips * 1.5, 25))
                }
            
            return None
            
        except Exception as e:
            return None


class RangeTradingMTF:
    """RangeTrading com confirmação D1"""
    
    def __init__(self):
        self.name = 'RangeTrading'
        self.primary_tf = 'H1'
        self.confirm_tf = 'D1'
        self.min_confidence = 0.55
        self.lookback = 30
    
    def analyze(self, mtf_data: MultiTimeframeData, timestamp: datetime) -> Optional[Dict]:
        try:
            h1 = mtf_data.get_all_indicators_at_time('H1', timestamp)
            d1 = mtf_data.get_all_indicators_at_time('D1', timestamp)
            
            if h1 is None:
                return None
            
            adx = h1['adx']
            price = h1['close']
            rsi = h1['rsi']
            bb_upper = h1['bb_upper']
            bb_lower = h1['bb_lower']
            stoch_k = h1['stoch_k']
            atr = h1['atr']
            
            if pd.isna(adx) or pd.isna(price):
                return None
            
            # Só opera se ADX indica lateralização
            if adx > 25:
                return None
            
            # D1 também deve estar lateralizado
            if d1 and d1.get('adx') and d1['adx'] > 30:
                return None
            
            # Obter range
            h1_data = mtf_data.data['H1']
            valid_data = h1_data[h1_data.index <= timestamp].tail(self.lookback + 1)
            
            if len(valid_data) < self.lookback:
                return None
            
            range_high = valid_data['High'].iloc[:-1].max()
            range_low = valid_data['Low'].iloc[:-1].min()
            range_size = range_high - range_low
            
            if range_size < atr * 3:
                return None
            
            range_position = (price - range_low) / range_size
            atr_pips = atr / 0.1 if not pd.isna(atr) else 20
            
            # Compra no fundo
            if range_position < 0.25 and price < bb_lower:
                score = 0
                if rsi < 40:
                    score += 2
                if stoch_k < 30:
                    score += 1
                if range_position < 0.15:
                    score += 2
                
                if score >= 3:
                    tp_distance = (range_high - price) * 0.6
                    return {
                        'action': 'BUY',
                        'confidence': score / 5,
                        'sl_pips': max(15, min(atr_pips * 1.5, 35)),
                        'tp_pips': max(30, min(tp_distance / 0.1, 70))
                    }
            
            # Venda no topo
            elif range_position > 0.75 and price > bb_upper:
                score = 0
                if rsi > 60:
                    score += 2
                if stoch_k > 70:
                    score += 1
                if range_position > 0.85:
                    score += 2
                
                if score >= 3:
                    tp_distance = (price - range_low) * 0.6
                    return {
                        'action': 'SELL',
                        'confidence': score / 5,
                        'sl_pips': max(15, min(atr_pips * 1.5, 35)),
                        'tp_pips': max(30, min(tp_distance / 0.1, 70))
                    }
            
            return None
            
        except Exception as e:
            return None


# =============================================================================
# BACKTEST ENGINE - MULTI-TIMEFRAME
# =============================================================================
class UrionMTFBacktester:
    """Engine de backtest multi-timeframe"""
    
    def __init__(self, initial_capital: float = 10000, risk_per_trade: float = 0.02):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade
        
        self.strategies = [
            TrendFollowingMTF(),
            MeanReversionMTF(),
            BreakoutMTF(),
            ScalpingMTF(),
            RangeTradingMTF()
        ]
        
        self.trades: List[Trade] = []
        self.open_positions: List[Trade] = []
        self.equity_curve: List[float] = []
        self.trade_id = 0
        
        self.strategy_stats = {s.name: {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0} 
                               for s in self.strategies}
    
    def calculate_position_size(self, sl_pips: float) -> float:
        risk_amount = self.capital * self.risk_per_trade
        pip_value = 10
        
        if sl_pips <= 0:
            sl_pips = 20
        
        lot_size = risk_amount / (sl_pips * pip_value)
        lot_size = max(0.01, min(lot_size, 2.0))
        
        return round(lot_size, 2)
    
    def open_trade(self, signal: Dict, strategy_name: str, 
                   price: float, timestamp: datetime) -> Optional[Trade]:
        
        if len(self.open_positions) >= MAX_POSITIONS:
            return None
        
        # Não abrir posição duplicada
        for pos in self.open_positions:
            if pos.direction == signal['action'] and pos.strategy == strategy_name:
                return None
        
        self.trade_id += 1
        
        sl_pips = signal['sl_pips']
        tp_pips = signal['tp_pips']
        pip_size = 0.1
        
        if signal['action'] == 'BUY':
            entry_price = price + (SPREAD_PIPS * pip_size) + (SLIPPAGE_PIPS * pip_size)
            sl = entry_price - (sl_pips * pip_size)
            tp = entry_price + (tp_pips * pip_size)
        else:
            entry_price = price - (SLIPPAGE_PIPS * pip_size)
            sl = entry_price + (sl_pips * pip_size)
            tp = entry_price - (tp_pips * pip_size)
        
        size = self.calculate_position_size(sl_pips)
        
        trade = Trade(
            id=self.trade_id,
            strategy=strategy_name,
            direction=signal['action'],
            entry_time=timestamp,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            size=size
        )
        
        self.open_positions.append(trade)
        return trade
    
    def update_positions(self, high: float, low: float, close: float, 
                         timestamp: datetime) -> List[Trade]:
        closed_trades = []
        
        for trade in self.open_positions[:]:
            exit_price = None
            exit_reason = None
            
            if trade.direction == 'BUY':
                if low <= trade.sl:
                    exit_price = trade.sl
                    exit_reason = 'stop_loss'
                elif high >= trade.tp:
                    exit_price = trade.tp
                    exit_reason = 'take_profit'
            else:
                if high >= trade.sl:
                    exit_price = trade.sl
                    exit_reason = 'stop_loss'
                elif low <= trade.tp:
                    exit_price = trade.tp
                    exit_reason = 'take_profit'
            
            if exit_price:
                pip_size = 0.1
                pip_value = 10 * trade.size
                
                if trade.direction == 'BUY':
                    pips = (exit_price - trade.entry_price) / pip_size
                else:
                    pips = (trade.entry_price - exit_price) / pip_size
                
                profit = pips * pip_value
                profit -= COMMISSION_PER_LOT * trade.size
                
                trade.exit_time = timestamp
                trade.exit_price = exit_price
                trade.profit = profit
                trade.exit_reason = exit_reason
                
                self.capital += profit
                self.trades.append(trade)
                self.open_positions.remove(trade)
                closed_trades.append(trade)
                
                self.strategy_stats[trade.strategy]['trades'] += 1
                self.strategy_stats[trade.strategy]['pnl'] += profit
                if profit > 0:
                    self.strategy_stats[trade.strategy]['wins'] += 1
                else:
                    self.strategy_stats[trade.strategy]['losses'] += 1
        
        return closed_trades
    
    def run(self, mtf_data: MultiTimeframeData) -> Dict:
        """Executa o backtest usando H1 como timeframe de execução"""
        
        # Calcular indicadores para todos os timeframes
        print("   Calculando indicadores...")
        for tf in mtf_data.data.keys():
            mtf_data.calculate_indicators(tf)
        print("   ✅ Indicadores calculados para todos os timeframes")
        
        # Usar H1 como base de iteração
        h1_data = mtf_data.data['H1']
        
        # Warmup
        warmup = 200
        
        print(f"   Executando backtest em {len(h1_data) - warmup:,} candles H1...")
        
        for i in range(warmup, len(h1_data)):
            timestamp = h1_data.index[i]
            current_price = h1_data['Close'].iloc[i]
            high = h1_data['High'].iloc[i]
            low = h1_data['Low'].iloc[i]
            
            # 1. Atualizar posições
            self.update_positions(high, low, current_price, timestamp)
            
            # 2. Verificar sinais
            for strategy in self.strategies:
                signal = strategy.analyze(mtf_data, timestamp)
                
                if signal and signal['confidence'] >= strategy.min_confidence:
                    self.open_trade(signal, strategy.name, current_price, timestamp)
            
            # 3. Registrar equity
            open_pnl = 0
            for pos in self.open_positions:
                pip_size = 0.1
                pip_value = 10 * pos.size
                if pos.direction == 'BUY':
                    pips = (current_price - pos.entry_price) / pip_size
                else:
                    pips = (pos.entry_price - current_price) / pip_size
                open_pnl += pips * pip_value
            
            self.equity_curve.append(self.capital + open_pnl)
        
        # Fechar posições restantes
        for trade in self.open_positions[:]:
            trade.exit_time = h1_data.index[-1]
            trade.exit_price = h1_data['Close'].iloc[-1]
            
            pip_size = 0.1
            pip_value = 10 * trade.size
            if trade.direction == 'BUY':
                pips = (trade.exit_price - trade.entry_price) / pip_size
            else:
                pips = (trade.entry_price - trade.exit_price) / pip_size
            
            trade.profit = pips * pip_value - COMMISSION_PER_LOT * trade.size
            trade.exit_reason = 'end_of_backtest'
            
            self.capital += trade.profit
            self.trades.append(trade)
            
            self.strategy_stats[trade.strategy]['trades'] += 1
            self.strategy_stats[trade.strategy]['pnl'] += trade.profit
            if trade.profit > 0:
                self.strategy_stats[trade.strategy]['wins'] += 1
            else:
                self.strategy_stats[trade.strategy]['losses'] += 1
        
        self.open_positions = []
        
        return self.calculate_metrics()
    
    def calculate_metrics(self) -> Dict:
        if not self.trades:
            return {'error': 'Nenhum trade'}
        
        profits = [t.profit for t in self.trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]
        
        total_trades = len(self.trades)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float('inf')
        
        equity = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown) * 100
        
        returns = np.diff(equity) / equity[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0
        
        total_return = (self.capital - self.initial_capital) / self.initial_capital
        calmar = total_return / (max_drawdown / 100) if max_drawdown > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'total_return': total_return * 100,
            'total_profit': self.capital - self.initial_capital,
            'total_trades': total_trades,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'strategy_stats': self.strategy_stats
        }


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("\n" + "=" * 70)
    print("🤖 URION TRADING BOT - BACKTEST MULTI-TIMEFRAME")
    print("   Usando dados REAIS do MT5 em múltiplos timeframes")
    print("=" * 70)
    
    # Carregar dados
    print("\n📊 Carregando dados multi-timeframe...")
    mtf_data = MultiTimeframeData()
    mtf_data.load_data()
    
    if 'H1' not in mtf_data.data:
        print("❌ Dados H1 não encontrados!")
        return
    
    h1 = mtf_data.data['H1']
    print(f"\n   📅 Período: {h1.index[0].strftime('%Y-%m-%d')} a {h1.index[-1].strftime('%Y-%m-%d')}")
    print(f"   💰 Preço inicial: ${h1['Close'].iloc[0]:.2f}")
    print(f"   💰 Preço final: ${h1['Close'].iloc[-1]:.2f}")
    
    # Executar backtest
    print("\n🚀 Iniciando backtest multi-timeframe...")
    print(f"   Capital inicial: ${INITIAL_CAPITAL:,.2f}")
    print(f"   Risco por trade: {RISK_PER_TRADE*100:.1f}%")
    print(f"   Estratégias: TrendFollowing(H1), MeanReversion(H1), Breakout(H1), Scalping(M15), RangeTrading(H1)")
    
    backtester = UrionMTFBacktester(
        initial_capital=INITIAL_CAPITAL,
        risk_per_trade=RISK_PER_TRADE
    )
    
    results = backtester.run(mtf_data)
    
    # Exibir resultados
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DO BACKTEST MULTI-TIMEFRAME")
    print("=" * 70)
    
    print(f"\n🎯 PERFORMANCE GERAL")
    print(f"   Capital Inicial: ${results['initial_capital']:,.2f}")
    print(f"   Capital Final: ${results['final_capital']:,.2f}")
    print(f"   Retorno Total: {results['total_return']:.2f}%")
    print(f"   Lucro Total: ${results['total_profit']:,.2f}")
    
    print(f"\n📈 MÉTRICAS DE TRADING")
    print(f"   Total de Trades: {results['total_trades']}")
    print(f"   Trades Vencedores: {results['wins']}")
    print(f"   Trades Perdedores: {results['losses']}")
    print(f"   Win Rate: {results['win_rate']:.2f}%")
    print(f"   Profit Factor: {results['profit_factor']:.2f}")
    print(f"   Média Ganho: ${results['avg_win']:.2f}")
    print(f"   Média Perda: ${results['avg_loss']:.2f}")
    
    print(f"\n⚠️ MÉTRICAS DE RISCO")
    print(f"   Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"   Calmar Ratio: {results['calmar_ratio']:.2f}")
    
    print(f"\n📊 PERFORMANCE POR ESTRATÉGIA")
    for name, stats in results['strategy_stats'].items():
        if stats['trades'] > 0:
            wr = stats['wins'] / stats['trades'] * 100
            print(f"   {name}:")
            print(f"      Trades: {stats['trades']} | WR: {wr:.1f}% | PnL: ${stats['pnl']:.2f}")
    
    # Avaliação
    print("\n" + "=" * 70)
    print("✅ AVALIAÇÃO PARA PRODUÇÃO")
    print("=" * 70)
    
    checks = [
        ('Win Rate > 45%', results['win_rate'] > 45, f"{results['win_rate']:.1f}"),
        ('Profit Factor > 1.2', results['profit_factor'] > 1.2, f"{results['profit_factor']:.2f}"),
        ('Max Drawdown < 25%', results['max_drawdown'] < 25, f"{results['max_drawdown']:.1f}"),
        ('Sharpe Ratio > 0.5', results['sharpe_ratio'] > 0.5, f"{results['sharpe_ratio']:.2f}"),
        ('Total Trades > 50', results['total_trades'] > 50, f"{results['total_trades']}")
    ]
    
    passed = 0
    for name, check, value in checks:
        status = "✅ PASS" if check else "❌ FAIL"
        print(f"   {status} {name}: {value}")
        if check:
            passed += 1
    
    print(f"\n   Score: {passed}/{len(checks)} ({passed/len(checks)*100:.0f}%)")
    
    if passed >= 4:
        print("\n   ✅ APROVADO - Sistema pronto para paper trading")
    elif passed >= 3:
        print("\n   ⚠️ ACEITÁVEL - Considerar otimizações antes de produção")
    else:
        print("\n   ❌ NECESSITA REVISÃO - Otimizar parâmetros")
    
    print("=" * 70)
    
    # Salvar
    os.makedirs('data/backtest_results', exist_ok=True)
    output_file = f"data/backtest_results/urion_mtf_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'type': 'multi_timeframe',
            'timeframes': ['M15', 'H1', 'H4', 'D1'],
            'results': {k: v for k, v in results.items() if k != 'strategy_stats'},
            'strategy_stats': results['strategy_stats'],
            'config': {
                'initial_capital': INITIAL_CAPITAL,
                'risk_per_trade': RISK_PER_TRADE,
                'max_positions': MAX_POSITIONS
            }
        }, f, indent=2, default=str)
    
    print(f"\n💾 Resultados salvos em: {output_file}")
    
    return results


if __name__ == '__main__':
    main()
