"""
BACKTEST URION COMPLETO - 5 ANOS
Usa as estratégias REAIS do sistema URION

Estratégias incluídas:
1. TrendFollowing - Segue tendências fortes (H1/H4)
2. MeanReversion - Reversão à média em extremos
3. Breakout - Captura rompimentos
4. Scalping - Operações rápidas em M5
5. RangeTrading - Opera lateralizações
6. NewsTrading - (desabilitado no backtest - sem dados de news)

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
SPREAD_PIPS = 2.5  # Spread médio XAUUSD
COMMISSION_PER_LOT = 7.0  # Comissão por lote
SLIPPAGE_PIPS = 0.5

# =============================================================================
# ESTRUTURAS DE DADOS
# =============================================================================
@dataclass
class Trade:
    """Representa um trade"""
    id: int
    strategy: str
    direction: str  # BUY or SELL
    entry_time: datetime
    entry_price: float
    sl: float
    tp: float
    size: float  # Em lotes
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    profit: Optional[float] = None
    exit_reason: Optional[str] = None


# =============================================================================
# INDICADORES TÉCNICOS
# =============================================================================
class TechnicalIndicators:
    """Calcula todos os indicadores técnicos"""
    
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
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {'macd': macd_line, 'signal': signal_line, 'histogram': histogram}
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
        """Calcula ADX com DI+ e DI-"""
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
    def bollinger(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        middle = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return {'upper': upper, 'middle': middle, 'lower': lower}
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                   k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low + 0.0001)
        d = k.rolling(window=d_period).mean()
        return {'k': k, 'd': d}


# =============================================================================
# ESTRATÉGIAS DO URION
# =============================================================================
class UrionStrategy:
    """Base class para estratégias"""
    
    def __init__(self, name: str, min_confidence: float = 0.6):
        self.name = name
        self.min_confidence = min_confidence
        self.trades_count = 0
        self.wins = 0
        self.losses = 0
    
    def analyze(self, data: Dict, idx: int) -> Optional[Dict]:
        """Analisa e retorna sinal ou None"""
        raise NotImplementedError


class TrendFollowingStrategy(UrionStrategy):
    """
    Estratégia TrendFollowing do URION
    - ADX > 25 para tendência forte
    - EMAs alinhadas (9 > 21 > 50 para alta)
    - MACD confirmando
    - RSI não em extremos
    """
    
    def __init__(self):
        super().__init__('TrendFollowing', min_confidence=0.55)
        self.adx_threshold = 25
        self.rsi_overbought = 70
        self.rsi_oversold = 30
    
    def analyze(self, data: Dict, idx: int) -> Optional[Dict]:
        try:
            # Extrair indicadores
            adx = data['adx'].iloc[idx]
            di_plus = data['di_plus'].iloc[idx]
            di_minus = data['di_minus'].iloc[idx]
            ema_9 = data['ema_9'].iloc[idx]
            ema_21 = data['ema_21'].iloc[idx]
            ema_50 = data['ema_50'].iloc[idx]
            rsi = data['rsi'].iloc[idx]
            macd_hist = data['macd_hist'].iloc[idx]
            price = data['close'].iloc[idx]
            atr = data['atr'].iloc[idx]
            
            if pd.isna(adx) or pd.isna(ema_50):
                return None
            
            # Condições BULLISH
            bullish_score = 0
            if adx > self.adx_threshold:
                bullish_score += 2
            if di_plus > di_minus:
                bullish_score += 1
            if ema_9 > ema_21 > ema_50:
                bullish_score += 2
            if price > ema_9:
                bullish_score += 1
            if macd_hist > 0:
                bullish_score += 1
            if self.rsi_oversold < rsi < self.rsi_overbought:
                bullish_score += 1
            if 40 < rsi < 65:
                bullish_score += 1
            
            # Condições BEARISH
            bearish_score = 0
            if adx > self.adx_threshold:
                bearish_score += 2
            if di_minus > di_plus:
                bearish_score += 1
            if ema_9 < ema_21 < ema_50:
                bearish_score += 2
            if price < ema_9:
                bearish_score += 1
            if macd_hist < 0:
                bearish_score += 1
            if self.rsi_oversold < rsi < self.rsi_overbought:
                bearish_score += 1
            if 35 < rsi < 60:
                bearish_score += 1
            
            max_score = 9
            
            if bullish_score > bearish_score and bullish_score >= 5:
                confidence = bullish_score / max_score
                sl_pips = atr * 2.5 / 0.1  # ATR-based
                tp_pips = atr * 5.0 / 0.1
                return {
                    'action': 'BUY',
                    'confidence': confidence,
                    'sl_pips': max(30, min(sl_pips, 80)),
                    'tp_pips': max(60, min(tp_pips, 160))
                }
            
            elif bearish_score > bullish_score and bearish_score >= 5:
                confidence = bearish_score / max_score
                sl_pips = atr * 2.5 / 0.1
                tp_pips = atr * 5.0 / 0.1
                return {
                    'action': 'SELL',
                    'confidence': confidence,
                    'sl_pips': max(30, min(sl_pips, 80)),
                    'tp_pips': max(60, min(tp_pips, 160))
                }
            
            return None
            
        except Exception as e:
            return None


class MeanReversionStrategy(UrionStrategy):
    """
    Estratégia MeanReversion do URION
    - RSI em extremos (< 30 ou > 70)
    - Preço fora das Bollinger Bands
    - Reversão para a média
    """
    
    def __init__(self):
        super().__init__('MeanReversion', min_confidence=0.55)
        self.rsi_oversold = 30
        self.rsi_overbought = 70
    
    def analyze(self, data: Dict, idx: int) -> Optional[Dict]:
        try:
            rsi = data['rsi'].iloc[idx]
            price = data['close'].iloc[idx]
            bb_upper = data['bb_upper'].iloc[idx]
            bb_lower = data['bb_lower'].iloc[idx]
            bb_middle = data['bb_middle'].iloc[idx]
            stoch_k = data['stoch_k'].iloc[idx]
            stoch_d = data['stoch_d'].iloc[idx]
            macd_hist = data['macd_hist'].iloc[idx]
            atr = data['atr'].iloc[idx]
            
            if pd.isna(rsi) or pd.isna(bb_upper):
                return None
            
            # Condições de OVERSOLD (compra na reversão)
            oversold_score = 0
            if rsi < self.rsi_oversold:
                oversold_score += 2
            if rsi < 25:
                oversold_score += 1
            if price < bb_lower:
                oversold_score += 2
            if stoch_k < 20:
                oversold_score += 1
            if stoch_k > stoch_d:  # Cruzamento bullish
                oversold_score += 1
            if macd_hist > data['macd_hist'].iloc[idx-1]:  # Histograma subindo
                oversold_score += 1
            
            # Condições de OVERBOUGHT (venda na reversão)
            overbought_score = 0
            if rsi > self.rsi_overbought:
                overbought_score += 2
            if rsi > 75:
                overbought_score += 1
            if price > bb_upper:
                overbought_score += 2
            if stoch_k > 80:
                overbought_score += 1
            if stoch_k < stoch_d:  # Cruzamento bearish
                overbought_score += 1
            if macd_hist < data['macd_hist'].iloc[idx-1]:  # Histograma caindo
                overbought_score += 1
            
            max_score = 8
            
            if oversold_score >= 4:
                confidence = oversold_score / max_score
                # Mean reversion tem SL/TP menores
                sl_pips = atr * 1.5 / 0.1
                tp_pips = atr * 3.0 / 0.1
                return {
                    'action': 'BUY',
                    'confidence': confidence,
                    'sl_pips': max(20, min(sl_pips, 50)),
                    'tp_pips': max(40, min(tp_pips, 100))
                }
            
            elif overbought_score >= 4:
                confidence = overbought_score / max_score
                sl_pips = atr * 1.5 / 0.1
                tp_pips = atr * 3.0 / 0.1
                return {
                    'action': 'SELL',
                    'confidence': confidence,
                    'sl_pips': max(20, min(sl_pips, 50)),
                    'tp_pips': max(40, min(tp_pips, 100))
                }
            
            return None
            
        except Exception as e:
            return None


class BreakoutStrategy(UrionStrategy):
    """
    Estratégia Breakout do URION
    - Rompimento de níveis de suporte/resistência
    - Volume confirmando
    - ATR para volatilidade adequada
    """
    
    def __init__(self):
        super().__init__('Breakout', min_confidence=0.55)
        self.lookback = 20
    
    def analyze(self, data: Dict, idx: int) -> Optional[Dict]:
        try:
            if idx < self.lookback + 5:
                return None
            
            price = data['close'].iloc[idx]
            high = data['high'].iloc[idx]
            low = data['low'].iloc[idx]
            atr = data['atr'].iloc[idx]
            volume = data['volume'].iloc[idx]
            
            # Calcular níveis de S/R
            recent_highs = data['high'].iloc[idx-self.lookback:idx]
            recent_lows = data['low'].iloc[idx-self.lookback:idx]
            
            resistance = recent_highs.max()
            support = recent_lows.min()
            
            # Volume médio
            avg_volume = data['volume'].iloc[idx-self.lookback:idx].mean()
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1
            
            # ADX para confirmar tendência
            adx = data['adx'].iloc[idx]
            macd_hist = data['macd_hist'].iloc[idx]
            
            if pd.isna(atr) or pd.isna(adx):
                return None
            
            # Breakout BULLISH
            bullish_score = 0
            if high > resistance:
                bullish_score += 3
            if price > resistance:
                bullish_score += 2
            if volume_ratio > 1.3:
                bullish_score += 2
            if adx > 20:
                bullish_score += 1
            if macd_hist > 0:
                bullish_score += 1
            
            # Breakout BEARISH
            bearish_score = 0
            if low < support:
                bearish_score += 3
            if price < support:
                bearish_score += 2
            if volume_ratio > 1.3:
                bearish_score += 2
            if adx > 20:
                bearish_score += 1
            if macd_hist < 0:
                bearish_score += 1
            
            max_score = 9
            
            if bullish_score >= 5:
                confidence = bullish_score / max_score
                sl_pips = atr * 2.0 / 0.1
                tp_pips = atr * 4.0 / 0.1
                return {
                    'action': 'BUY',
                    'confidence': confidence,
                    'sl_pips': max(25, min(sl_pips, 60)),
                    'tp_pips': max(50, min(tp_pips, 120))
                }
            
            elif bearish_score >= 5:
                confidence = bearish_score / max_score
                sl_pips = atr * 2.0 / 0.1
                tp_pips = atr * 4.0 / 0.1
                return {
                    'action': 'SELL',
                    'confidence': confidence,
                    'sl_pips': max(25, min(sl_pips, 60)),
                    'tp_pips': max(50, min(tp_pips, 120))
                }
            
            return None
            
        except Exception as e:
            return None


class ScalpingStrategy(UrionStrategy):
    """
    Estratégia Scalping do URION (M5/M15)
    - RSI entre 35-65
    - Bollinger Bands para reversão rápida
    - MACD + Stochastic confirmando
    - Spread baixo essencial
    """
    
    def __init__(self):
        super().__init__('Scalping', min_confidence=0.50)
        self.rsi_min = 35
        self.rsi_max = 65
    
    def analyze(self, data: Dict, idx: int) -> Optional[Dict]:
        try:
            rsi = data['rsi'].iloc[idx]
            price = data['close'].iloc[idx]
            bb_upper = data['bb_upper'].iloc[idx]
            bb_lower = data['bb_lower'].iloc[idx]
            bb_middle = data['bb_middle'].iloc[idx]
            macd_hist = data['macd_hist'].iloc[idx]
            macd_line = data['macd_line'].iloc[idx]
            macd_signal = data['macd_signal'].iloc[idx]
            stoch_k = data['stoch_k'].iloc[idx]
            stoch_d = data['stoch_d'].iloc[idx]
            ema_9 = data['ema_9'].iloc[idx]
            ema_21 = data['ema_21'].iloc[idx]
            atr = data['atr'].iloc[idx]
            
            if pd.isna(rsi) or pd.isna(bb_upper):
                return None
            
            # RSI deve estar no range
            if rsi < self.rsi_min or rsi > self.rsi_max:
                return None
            
            # ATR em pips (XAUUSD: 1 pip = 0.1)
            atr_pips = atr / 0.1
            if atr_pips < 3 or atr_pips > 20:
                return None  # Volatilidade inadequada
            
            # BB position
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                bb_position = (price - bb_lower) / bb_range
            else:
                return None
            
            # Score BULLISH
            bullish_score = 0
            if macd_hist > 0 and macd_line > macd_signal:
                bullish_score += 1
                if bb_position < 0.25:
                    bullish_score += 2  # MACD bullish + BB oversold
            if stoch_k > stoch_d and stoch_k < 80:
                bullish_score += 1
            if stoch_k < 25:
                bullish_score += 1
            if price > ema_9 > ema_21:
                bullish_score += 1
            
            # Score BEARISH
            bearish_score = 0
            if macd_hist < 0 and macd_line < macd_signal:
                bearish_score += 1
                if bb_position > 0.75:
                    bearish_score += 2  # MACD bearish + BB overbought
            if stoch_k < stoch_d and stoch_k > 20:
                bearish_score += 1
            if stoch_k > 75:
                bearish_score += 1
            if price < ema_9 < ema_21:
                bearish_score += 1
            
            max_score = 6
            
            if bullish_score >= 3:
                confidence = bullish_score / max_score
                sl_pips = max(5, atr_pips * 1.0)
                tp_pips = max(10, atr_pips * 1.5)
                return {
                    'action': 'BUY',
                    'confidence': confidence,
                    'sl_pips': min(sl_pips, 15),
                    'tp_pips': min(tp_pips, 25)
                }
            
            elif bearish_score >= 3:
                confidence = bearish_score / max_score
                sl_pips = max(5, atr_pips * 1.0)
                tp_pips = max(10, atr_pips * 1.5)
                return {
                    'action': 'SELL',
                    'confidence': confidence,
                    'sl_pips': min(sl_pips, 15),
                    'tp_pips': min(tp_pips, 25)
                }
            
            return None
            
        except Exception as e:
            return None


class RangeTradingStrategy(UrionStrategy):
    """
    Estratégia RangeTrading do URION
    - ADX baixo (< 25) indica lateralização
    - Opera nas bordas do range
    - Bollinger Bands como referência
    """
    
    def __init__(self):
        super().__init__('RangeTrading', min_confidence=0.55)
        self.adx_max = 25
        self.lookback = 30
    
    def analyze(self, data: Dict, idx: int) -> Optional[Dict]:
        try:
            if idx < self.lookback + 5:
                return None
            
            adx = data['adx'].iloc[idx]
            price = data['close'].iloc[idx]
            rsi = data['rsi'].iloc[idx]
            bb_upper = data['bb_upper'].iloc[idx]
            bb_lower = data['bb_lower'].iloc[idx]
            stoch_k = data['stoch_k'].iloc[idx]
            atr = data['atr'].iloc[idx]
            
            if pd.isna(adx):
                return None
            
            # Só opera se ADX indica lateralização
            if adx > self.adx_max:
                return None
            
            # Range dinâmico
            recent_highs = data['high'].iloc[idx-self.lookback:idx]
            recent_lows = data['low'].iloc[idx-self.lookback:idx]
            range_high = recent_highs.max()
            range_low = recent_lows.min()
            
            range_size = range_high - range_low
            if range_size < atr * 3:  # Range muito pequeno
                return None
            
            # Posição no range
            range_position = (price - range_low) / range_size if range_size > 0 else 0.5
            
            # Compra no fundo do range
            if range_position < 0.25 and price < bb_lower:
                score = 0
                if rsi < 35:
                    score += 2
                if stoch_k < 25:
                    score += 1
                if price <= range_low + (range_size * 0.1):
                    score += 2
                
                if score >= 3:
                    sl_pips = atr * 1.5 / 0.1
                    tp_pips = (range_high - price) / 0.1 * 0.7  # 70% do range
                    return {
                        'action': 'BUY',
                        'confidence': score / 5,
                        'sl_pips': max(15, min(sl_pips, 40)),
                        'tp_pips': max(30, min(tp_pips, 80))
                    }
            
            # Venda no topo do range
            elif range_position > 0.75 and price > bb_upper:
                score = 0
                if rsi > 65:
                    score += 2
                if stoch_k > 75:
                    score += 1
                if price >= range_high - (range_size * 0.1):
                    score += 2
                
                if score >= 3:
                    sl_pips = atr * 1.5 / 0.1
                    tp_pips = (price - range_low) / 0.1 * 0.7
                    return {
                        'action': 'SELL',
                        'confidence': score / 5,
                        'sl_pips': max(15, min(sl_pips, 40)),
                        'tp_pips': max(30, min(tp_pips, 80))
                    }
            
            return None
            
        except Exception as e:
            return None


# =============================================================================
# BACKTEST ENGINE
# =============================================================================
class UrionBacktester:
    """Engine de backtest para o URION"""
    
    def __init__(self, initial_capital: float = 10000, risk_per_trade: float = 0.02):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade
        
        # Estratégias
        self.strategies = [
            TrendFollowingStrategy(),
            MeanReversionStrategy(),
            BreakoutStrategy(),
            ScalpingStrategy(),
            RangeTradingStrategy()
        ]
        
        # Tracking
        self.trades: List[Trade] = []
        self.open_positions: List[Trade] = []
        self.equity_curve: List[float] = []
        self.trade_id = 0
        
        # Estatísticas por estratégia
        self.strategy_stats = {s.name: {'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0} 
                               for s in self.strategies}
    
    def prepare_data(self, df: pd.DataFrame) -> Dict:
        """Calcula todos os indicadores"""
        print("   Calculando indicadores técnicos...")
        
        data = {
            'open': df['Open'],
            'high': df['High'],
            'low': df['Low'],
            'close': df['Close'],
            'volume': df['Volume']
        }
        
        # EMAs
        data['ema_9'] = TechnicalIndicators.ema(df['Close'], 9)
        data['ema_21'] = TechnicalIndicators.ema(df['Close'], 21)
        data['ema_50'] = TechnicalIndicators.ema(df['Close'], 50)
        data['ema_200'] = TechnicalIndicators.ema(df['Close'], 200)
        
        # RSI
        data['rsi'] = TechnicalIndicators.rsi(df['Close'], 14)
        
        # MACD
        macd = TechnicalIndicators.macd(df['Close'])
        data['macd_line'] = macd['macd']
        data['macd_signal'] = macd['signal']
        data['macd_hist'] = macd['histogram']
        
        # ADX
        adx = TechnicalIndicators.adx(df['High'], df['Low'], df['Close'])
        data['adx'] = adx['adx']
        data['di_plus'] = adx['di_plus']
        data['di_minus'] = adx['di_minus']
        
        # ATR
        data['atr'] = TechnicalIndicators.atr(df['High'], df['Low'], df['Close'])
        
        # Bollinger Bands
        bb = TechnicalIndicators.bollinger(df['Close'])
        data['bb_upper'] = bb['upper']
        data['bb_middle'] = bb['middle']
        data['bb_lower'] = bb['lower']
        
        # Stochastic
        stoch = TechnicalIndicators.stochastic(df['High'], df['Low'], df['Close'])
        data['stoch_k'] = stoch['k']
        data['stoch_d'] = stoch['d']
        
        print("   ✅ Indicadores calculados")
        return data
    
    def calculate_position_size(self, sl_pips: float) -> float:
        """Calcula tamanho da posição baseado no risco"""
        risk_amount = self.capital * self.risk_per_trade
        pip_value = 10  # XAUUSD: $10 por pip para 1 lote
        
        if sl_pips <= 0:
            sl_pips = 20  # Default
        
        lot_size = risk_amount / (sl_pips * pip_value)
        
        # Limites
        lot_size = max(0.01, min(lot_size, 2.0))
        
        return round(lot_size, 2)
    
    def open_trade(self, signal: Dict, strategy_name: str, 
                   price: float, timestamp: datetime) -> Optional[Trade]:
        """Abre um novo trade"""
        
        # Verificar limite de posições
        if len(self.open_positions) >= MAX_POSITIONS:
            return None
        
        # Verificar se já tem posição na mesma direção
        for pos in self.open_positions:
            if pos.direction == signal['action'] and pos.strategy == strategy_name:
                return None
        
        self.trade_id += 1
        
        sl_pips = signal['sl_pips']
        tp_pips = signal['tp_pips']
        
        # Calcular SL/TP
        pip_size = 0.1  # XAUUSD
        
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
        """Atualiza posições abertas e fecha as que atingiram SL/TP"""
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
            else:  # SELL
                if high >= trade.sl:
                    exit_price = trade.sl
                    exit_reason = 'stop_loss'
                elif low <= trade.tp:
                    exit_price = trade.tp
                    exit_reason = 'take_profit'
            
            if exit_price:
                # Calcular profit
                pip_size = 0.1
                pip_value = 10 * trade.size  # $10 por pip por lote
                
                if trade.direction == 'BUY':
                    pips = (exit_price - trade.entry_price) / pip_size
                else:
                    pips = (trade.entry_price - exit_price) / pip_size
                
                profit = pips * pip_value
                profit -= COMMISSION_PER_LOT * trade.size  # Comissão
                
                trade.exit_time = timestamp
                trade.exit_price = exit_price
                trade.profit = profit
                trade.exit_reason = exit_reason
                
                self.capital += profit
                self.trades.append(trade)
                self.open_positions.remove(trade)
                closed_trades.append(trade)
                
                # Atualizar stats
                self.strategy_stats[trade.strategy]['trades'] += 1
                self.strategy_stats[trade.strategy]['pnl'] += profit
                if profit > 0:
                    self.strategy_stats[trade.strategy]['wins'] += 1
                else:
                    self.strategy_stats[trade.strategy]['losses'] += 1
        
        return closed_trades
    
    def run(self, df: pd.DataFrame) -> Dict:
        """Executa o backtest"""
        
        # Preparar dados
        data = self.prepare_data(df)
        
        # Warmup period (para indicadores)
        warmup = 200
        
        print(f"   Executando backtest em {len(df) - warmup:,} candles...")
        
        # Loop principal
        for i in range(warmup, len(df)):
            timestamp = df.index[i]
            current_price = data['close'].iloc[i]
            high = data['high'].iloc[i]
            low = data['low'].iloc[i]
            
            # 1. Atualizar posições abertas
            self.update_positions(high, low, current_price, timestamp)
            
            # 2. Verificar sinais de cada estratégia
            for strategy in self.strategies:
                signal = strategy.analyze(data, i)
                
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
            trade.exit_time = df.index[-1]
            trade.exit_price = data['close'].iloc[-1]
            
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
        """Calcula métricas de performance"""
        
        if not self.trades:
            return {'error': 'Nenhum trade executado'}
        
        profits = [t.profit for t in self.trades]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p <= 0]
        
        # Métricas básicas
        total_trades = len(self.trades)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float('inf')
        
        # Drawdown
        equity = np.array(self.equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown) * 100
        
        # Sharpe Ratio (aproximado)
        returns = np.diff(equity) / equity[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24) if np.std(returns) > 0 else 0
        
        # Calmar Ratio
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
def download_data():
    """Baixa dados de múltiplas fontes"""
    
    # Primeiro tentar dados salvos do MT5
    mt5_file = 'data/xauusd_5years_d1.csv'
    if os.path.exists(mt5_file):
        print(f"   Carregando dados reais do MT5...")
        df = pd.read_csv(mt5_file)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'tick_volume': 'Volume'
        }, inplace=True)
        return df, "MT5_real"
    
    # Tentar baixar do MT5 diretamente
    try:
        import MetaTrader5 as mt5
        
        if mt5.initialize():
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5*365)
            
            rates = mt5.copy_rates_range('XAUUSD', mt5.TIMEFRAME_D1, start_date, end_date)
            mt5.shutdown()
            
            if rates is not None and len(rates) > 500:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)
                df.rename(columns={
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close',
                    'tick_volume': 'Volume'
                }, inplace=True)
                
                # Salvar para uso futuro
                df.to_csv(mt5_file)
                return df, "MT5_direct"
    except Exception as e:
        print(f"   ⚠️ MT5 não disponível: {e}")
    
    # Tentar yfinance como fallback
    try:
        import yfinance as yf
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5*365)
        
        tickers = ['GC=F', 'GOLD', 'IAU', 'GLD']
        
        for ticker_symbol in tickers:
            try:
                print(f"   Tentando {ticker_symbol}...")
                df = yf.download(ticker_symbol, start=start_date, end=end_date, 
                                interval="1d", progress=False)
                
                if not df.empty and len(df) > 500:
                    print(f"   ✅ Dados obtidos de {ticker_symbol}")
                    return df, ticker_symbol
            except Exception as e:
                continue
        
        return None, None
        
    except Exception as e:
        print(f"   ⚠️ yfinance falhou: {e}")
        return None, None


def generate_synthetic_data(years: int = 5):
    """Gera dados sintéticos realistas baseados em características do XAUUSD"""
    
    print("   Gerando dados sintéticos baseados em características reais do XAUUSD...")
    
    # Parâmetros baseados em dados reais do XAUUSD
    initial_price = 1800  # Preço inicial aproximado de 5 anos atrás
    final_price = 2650    # Preço atual aproximado
    
    # Gerar série temporal
    n_days = years * 252  # Dias de trading
    
    # Retorno médio diário para ir de 1800 a 2650 em 5 anos
    total_return = final_price / initial_price
    daily_return = (total_return ** (1/n_days)) - 1
    
    # Volatilidade diária do XAUUSD (~1.2% ao dia)
    daily_volatility = 0.012
    
    # Gerar retornos com regime switching
    np.random.seed(42)
    
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq='B')
    
    # Simular diferentes regimes de mercado
    prices = [initial_price]
    current_regime = 'normal'  # normal, bull, bear, volatile
    regime_duration = 0
    
    for i in range(1, n_days):
        # Mudar regime periodicamente
        regime_duration += 1
        if regime_duration > np.random.randint(20, 60):
            current_regime = np.random.choice(['normal', 'bull', 'bear', 'volatile'], 
                                               p=[0.4, 0.25, 0.2, 0.15])
            regime_duration = 0
        
        # Ajustar parâmetros por regime
        if current_regime == 'bull':
            regime_return = daily_return * 1.5
            regime_vol = daily_volatility * 0.8
        elif current_regime == 'bear':
            regime_return = daily_return * -0.5
            regime_vol = daily_volatility * 1.2
        elif current_regime == 'volatile':
            regime_return = daily_return
            regime_vol = daily_volatility * 2.0
        else:
            regime_return = daily_return
            regime_vol = daily_volatility
        
        # Gerar retorno
        ret = np.random.normal(regime_return, regime_vol)
        new_price = prices[-1] * (1 + ret)
        prices.append(new_price)
    
    # Criar OHLC a partir dos closes
    closes = np.array(prices)
    
    # Gerar High/Low realistas
    intraday_range = closes * np.random.uniform(0.008, 0.018, len(closes))
    highs = closes + intraday_range * np.random.uniform(0.3, 0.7, len(closes))
    lows = closes - intraday_range * np.random.uniform(0.3, 0.7, len(closes))
    
    # Open = close anterior + gap
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    opens = opens + np.random.normal(0, closes * 0.002)
    
    # Garantir High >= max(Open, Close) e Low <= min(Open, Close)
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows = np.minimum(lows, np.minimum(opens, closes))
    
    # Volume sintético
    base_volume = 100000
    volumes = base_volume * np.random.lognormal(0, 0.5, len(closes))
    
    df = pd.DataFrame({
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes,
        'Volume': volumes
    }, index=dates)
    
    return df


def main():
    print("\n" + "=" * 70)
    print("🤖 URION TRADING BOT - BACKTEST COMPLETO 5 ANOS")
    print("   Usando TODAS as estratégias reais do sistema")
    print("=" * 70)
    
    # Baixar dados
    print("\n📊 Obtendo 5 anos de dados para XAUUSD...")
    
    df_daily, source = download_data()
    
    if df_daily is None or df_daily.empty:
        print("   ⚠️ Não foi possível baixar dados reais, usando dados sintéticos...")
        df_daily = generate_synthetic_data(5)
        source = "synthetic"
    else:
        # Normalizar colunas (yfinance pode retornar com/sem MultiIndex)
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)
        
        # Converter para escala XAUUSD se necessário
        if df_daily['Close'].mean() < 500:  # Provavelmente é GLD ou IAU
            factor = 2650 / df_daily['Close'].iloc[-1]  # Ajustar para preço atual
            df_daily['Open'] = df_daily['Open'] * factor
            df_daily['High'] = df_daily['High'] * factor
            df_daily['Low'] = df_daily['Low'] * factor
            df_daily['Close'] = df_daily['Close'] * factor
    
    print(f"   ✅ {len(df_daily):,} candles diários ({source})")
    print(f"   📅 De: {df_daily.index[0].strftime('%Y-%m-%d')}")
    print(f"   📅 Até: {df_daily.index[-1].strftime('%Y-%m-%d')}")
    print(f"   💰 Preço inicial: ${df_daily['Close'].iloc[0]:.2f}")
    print(f"   💰 Preço final: ${df_daily['Close'].iloc[-1]:.2f}")
    
    # Executar backtest
    print("\n🚀 Iniciando backtest com estratégias URION...")
    print(f"   Capital inicial: ${INITIAL_CAPITAL:,.2f}")
    print(f"   Risco por trade: {RISK_PER_TRADE*100:.1f}%")
    print(f"   Estratégias: TrendFollowing, MeanReversion, Breakout, Scalping, RangeTrading")
    
    backtester = UrionBacktester(
        initial_capital=INITIAL_CAPITAL,
        risk_per_trade=RISK_PER_TRADE
    )
    
    results = backtester.run(df_daily)
    
    # Exibir resultados
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DO BACKTEST - 5 ANOS (ESTRATÉGIAS URION)")
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
        ('Win Rate > 50%', results['win_rate'] > 50, f"{results['win_rate']:.1f}"),
        ('Profit Factor > 1.3', results['profit_factor'] > 1.3, f"{results['profit_factor']:.2f}"),
        ('Max Drawdown < 20%', results['max_drawdown'] < 20, f"{results['max_drawdown']:.1f}"),
        ('Sharpe Ratio > 1.0', results['sharpe_ratio'] > 1.0, f"{results['sharpe_ratio']:.2f}"),
        ('Total Trades > 100', results['total_trades'] > 100, f"{results['total_trades']}")
    ]
    
    passed = 0
    for name, check, value in checks:
        status = "✅ PASS" if check else "❌ FAIL"
        print(f"   {status} {name}: {value}")
        if check:
            passed += 1
    
    print(f"\n   Score: {passed}/{len(checks)} ({passed/len(checks)*100:.0f}%)")
    
    if passed >= 4:
        print("\n   ✅ APROVADO - Sistema pronto para próxima fase")
    else:
        print("\n   ⚠️ NECESSITA OTIMIZAÇÃO - Revisar parâmetros das estratégias")
    
    print("=" * 70)
    
    # Salvar resultados
    os.makedirs('data/backtest_results', exist_ok=True)
    
    output_file = f"data/backtest_results/urion_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'period': '5 years',
            'strategies': ['TrendFollowing', 'MeanReversion', 'Breakout', 'Scalping', 'RangeTrading'],
            'results': {k: v for k, v in results.items() if k != 'strategy_stats'},
            'strategy_stats': results['strategy_stats'],
            'config': {
                'initial_capital': INITIAL_CAPITAL,
                'risk_per_trade': RISK_PER_TRADE,
                'max_positions': MAX_POSITIONS,
                'spread_pips': SPREAD_PIPS
            }
        }, f, indent=2, default=str)
    
    print(f"\n💾 Resultados salvos em: {output_file}")
    
    return results


if __name__ == '__main__':
    main()
