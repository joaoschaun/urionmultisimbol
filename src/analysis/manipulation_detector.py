# -*- coding: utf-8 -*-
"""
Market Manipulation Detector
============================
Detecta padroes de manipulacao de mercado comum em Forex:
- Stop Hunting
- Fake Breakouts
- Volume Spikes anormais
- Spread Manipulation
- Liquidity Grabs
- Smart Money vs Dumb Money divergence
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
from collections import deque
import threading

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class ManipulationType(Enum):
    """Tipos de manipulacao detectados"""
    STOP_HUNT = "stop_hunt"
    FAKE_BREAKOUT = "fake_breakout"
    VOLUME_SPIKE = "volume_spike"
    SPREAD_MANIPULATION = "spread_manipulation"
    LIQUIDITY_GRAB = "liquidity_grab"
    INSTITUTIONAL_ACCUMULATION = "institutional_accumulation"
    INSTITUTIONAL_DISTRIBUTION = "institutional_distribution"
    WYCKOFF_SPRING = "wyckoff_spring"
    WYCKOFF_UPTHRUST = "wyckoff_upthrust"


class ManipulationSeverity(Enum):
    """Severidade da manipulacao"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ManipulationEvent:
    """Evento de manipulacao detectado"""
    timestamp: datetime
    type: ManipulationType
    severity: ManipulationSeverity
    price: float
    description: str
    confidence: float  # 0-1
    recommended_action: str
    details: Dict = field(default_factory=dict)


@dataclass
class RetailSentiment:
    """Sentimento do varejo"""
    long_percentage: float
    short_percentage: float
    source: str
    timestamp: datetime


class ManipulationDetector:
    """
    Detector de Manipulacao de Mercado
    Identifica padroes comuns usados por instituicoes
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.manipulation_config = config.get('manipulation_detector', {})
        
        # Thresholds
        self.volume_spike_threshold = self.manipulation_config.get('volume_spike_threshold', 3.0)
        self.spread_spike_threshold = self.manipulation_config.get('spread_spike_threshold', 2.0)
        self.stop_hunt_atr_multiplier = self.manipulation_config.get('stop_hunt_atr', 1.5)
        self.fake_breakout_candles = self.manipulation_config.get('fake_breakout_candles', 3)
        
        # Historico de eventos
        self._events: Dict[str, deque] = {}
        self._price_history: Dict[str, deque] = {}
        self._spread_history: Dict[str, deque] = {}
        self._volume_history: Dict[str, deque] = {}
        
        # Retail sentiment cache
        self._retail_sentiment: Dict[str, RetailSentiment] = {}
        
        # Lock
        self._lock = threading.Lock()
        
        logger.info("ManipulationDetector inicializado")
    
    def initialize_symbol(self, symbol: str):
        """Inicializa buffers para um simbolo"""
        with self._lock:
            if symbol not in self._events:
                self._events[symbol] = deque(maxlen=100)
                self._price_history[symbol] = deque(maxlen=1000)
                self._spread_history[symbol] = deque(maxlen=1000)
                self._volume_history[symbol] = deque(maxlen=1000)
    
    def update_tick(self, symbol: str, bid: float, ask: float, volume: int):
        """Atualiza com novo tick para analise"""
        self.initialize_symbol(symbol)
        
        with self._lock:
            spread = ask - bid
            self._price_history[symbol].append((datetime.now(), (bid + ask) / 2))
            self._spread_history[symbol].append((datetime.now(), spread))
            self._volume_history[symbol].append((datetime.now(), volume))
    
    def detect_stop_hunt(self, symbol: str, df: pd.DataFrame) -> Optional[ManipulationEvent]:
        """
        Detecta Stop Hunt - preco move rapidamente para tirar stops
        e depois reverte
        """
        if df is None or len(df) < 20:
            return None
        
        # Calcular ATR
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        tr = np.maximum(high[1:] - low[1:], 
                       np.abs(high[1:] - close[:-1]),
                       np.abs(low[1:] - close[:-1]))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)
        
        # Verificar padrao de stop hunt
        # Candle com wick longo que excede niveis anteriores e fecha dentro
        last_candle = df.iloc[-1]
        prev_high = df['high'].iloc[-20:-1].max()
        prev_low = df['low'].iloc[-20:-1].min()
        
        # Stop hunt para cima
        if last_candle['high'] > prev_high + atr * self.stop_hunt_atr_multiplier:
            if last_candle['close'] < prev_high:
                # Wick para cima, fechou abaixo - stop hunt de comprados
                return ManipulationEvent(
                    timestamp=datetime.now(),
                    type=ManipulationType.STOP_HUNT,
                    severity=ManipulationSeverity.HIGH,
                    price=last_candle['high'],
                    description="Stop Hunt detectado acima de resistencia - stops de comprados foram acionados",
                    confidence=0.8,
                    recommended_action="SELL ou aguardar confirmacao de reversao",
                    details={
                        'direction': 'up',
                        'high_reached': last_candle['high'],
                        'prev_high': prev_high,
                        'close': last_candle['close'],
                        'atr': atr
                    }
                )
        
        # Stop hunt para baixo
        if last_candle['low'] < prev_low - atr * self.stop_hunt_atr_multiplier:
            if last_candle['close'] > prev_low:
                # Wick para baixo, fechou acima - stop hunt de vendidos
                return ManipulationEvent(
                    timestamp=datetime.now(),
                    type=ManipulationType.STOP_HUNT,
                    severity=ManipulationSeverity.HIGH,
                    price=last_candle['low'],
                    description="Stop Hunt detectado abaixo de suporte - stops de vendidos foram acionados",
                    confidence=0.8,
                    recommended_action="BUY ou aguardar confirmacao de reversao",
                    details={
                        'direction': 'down',
                        'low_reached': last_candle['low'],
                        'prev_low': prev_low,
                        'close': last_candle['close'],
                        'atr': atr
                    }
                )
        
        return None
    
    def detect_fake_breakout(self, symbol: str, df: pd.DataFrame) -> Optional[ManipulationEvent]:
        """
        Detecta Fake Breakout - rompimento que falha rapidamente
        """
        if df is None or len(df) < 30:
            return None
        
        # Identificar niveis de suporte/resistencia
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        # Resistencia - maior high dos ultimos 20 candles (exceto ultimos 3)
        resistance = highs[-23:-3].max()
        support = lows[-23:-3].min()
        
        # Verificar fake breakout para cima
        last_candles = df.iloc[-self.fake_breakout_candles:]
        
        broke_up = any(last_candles['high'] > resistance)
        closed_below = last_candles.iloc[-1]['close'] < resistance
        
        if broke_up and closed_below:
            return ManipulationEvent(
                timestamp=datetime.now(),
                type=ManipulationType.FAKE_BREAKOUT,
                severity=ManipulationSeverity.MEDIUM,
                price=resistance,
                description=f"Fake Breakout de resistencia em {resistance:.2f} - preco voltou para dentro do range",
                confidence=0.75,
                recommended_action="SELL com stop acima do falso rompimento",
                details={
                    'direction': 'up',
                    'resistance': resistance,
                    'max_reached': last_candles['high'].max(),
                    'current_close': last_candles.iloc[-1]['close']
                }
            )
        
        # Verificar fake breakout para baixo
        broke_down = any(last_candles['low'] < support)
        closed_above = last_candles.iloc[-1]['close'] > support
        
        if broke_down and closed_above:
            return ManipulationEvent(
                timestamp=datetime.now(),
                type=ManipulationType.FAKE_BREAKOUT,
                severity=ManipulationSeverity.MEDIUM,
                price=support,
                description=f"Fake Breakout de suporte em {support:.2f} - preco voltou para dentro do range",
                confidence=0.75,
                recommended_action="BUY com stop abaixo do falso rompimento",
                details={
                    'direction': 'down',
                    'support': support,
                    'min_reached': last_candles['low'].min(),
                    'current_close': last_candles.iloc[-1]['close']
                }
            )
        
        return None
    
    def detect_volume_spike(self, symbol: str, df: pd.DataFrame) -> Optional[ManipulationEvent]:
        """
        Detecta spikes anormais de volume
        """
        if df is None or len(df) < 20:
            return None
        
        if 'tick_volume' not in df.columns:
            return None
        
        volumes = df['tick_volume'].values
        avg_volume = np.mean(volumes[-20:-1])
        std_volume = np.std(volumes[-20:-1])
        last_volume = volumes[-1]
        
        if avg_volume == 0:
            return None
        
        volume_ratio = last_volume / avg_volume
        z_score = (last_volume - avg_volume) / std_volume if std_volume > 0 else 0
        
        if volume_ratio >= self.volume_spike_threshold or z_score > 3:
            # Analisar direcao do movimento
            price_change = df.iloc[-1]['close'] - df.iloc[-2]['close']
            
            severity = ManipulationSeverity.MEDIUM
            if volume_ratio > 5 or z_score > 4:
                severity = ManipulationSeverity.HIGH
            
            return ManipulationEvent(
                timestamp=datetime.now(),
                type=ManipulationType.VOLUME_SPIKE,
                severity=severity,
                price=df.iloc[-1]['close'],
                description=f"Volume spike detectado: {volume_ratio:.1f}x a media (Z-score: {z_score:.1f})",
                confidence=min(0.9, 0.5 + z_score / 10),
                recommended_action="Cautela - possivel movimento institucional. Aguardar confirmacao.",
                details={
                    'volume_ratio': volume_ratio,
                    'z_score': z_score,
                    'current_volume': int(last_volume),
                    'avg_volume': int(avg_volume),
                    'price_change': price_change
                }
            )
        
        return None
    
    def detect_spread_manipulation(self, symbol: str) -> Optional[ManipulationEvent]:
        """
        Detecta spreads anormalmente altos
        """
        with self._lock:
            if symbol not in self._spread_history:
                return None
            
            spreads = [s[1] for s in self._spread_history[symbol]]
            
            if len(spreads) < 100:
                return None
            
            avg_spread = np.mean(spreads[:-1])
            current_spread = spreads[-1]
            
            if avg_spread == 0:
                return None
            
            spread_ratio = current_spread / avg_spread
            
            if spread_ratio >= self.spread_spike_threshold:
                return ManipulationEvent(
                    timestamp=datetime.now(),
                    type=ManipulationType.SPREAD_MANIPULATION,
                    severity=ManipulationSeverity.MEDIUM if spread_ratio < 3 else ManipulationSeverity.HIGH,
                    price=0,
                    description=f"Spread anormalmente alto: {spread_ratio:.1f}x a media",
                    confidence=0.7,
                    recommended_action="Evitar entradas - spread elevado aumenta custos",
                    details={
                        'current_spread': current_spread,
                        'avg_spread': avg_spread,
                        'ratio': spread_ratio
                    }
                )
        
        return None
    
    def detect_liquidity_grab(self, symbol: str, df: pd.DataFrame) -> Optional[ManipulationEvent]:
        """
        Detecta Liquidity Grab - movimento rapido para pegar liquidez
        """
        if df is None or len(df) < 10:
            return None
        
        # Verificar se houve movimento brusco seguido de reversao rapida
        last_3 = df.iloc[-3:]
        
        # Calcular range das ultimas 3 velas
        total_range = last_3['high'].max() - last_3['low'].min()
        avg_range = (df['high'] - df['low']).iloc[-20:-3].mean()
        
        if avg_range == 0:
            return None
        
        range_ratio = total_range / avg_range
        
        # Se o range foi muito maior que o normal e voltou
        if range_ratio > 2.5:
            # Verificar reversao
            first_candle = last_3.iloc[0]
            last_candle = last_3.iloc[-1]
            
            # Liquidity grab para baixo (spring)
            if last_3['low'].min() == last_3.iloc[1]['low']:  # Low no meio
                if last_candle['close'] > first_candle['open']:
                    return ManipulationEvent(
                        timestamp=datetime.now(),
                        type=ManipulationType.WYCKOFF_SPRING,
                        severity=ManipulationSeverity.HIGH,
                        price=last_3['low'].min(),
                        description="Spring (Wyckoff) detectado - liquidez foi capturada abaixo do suporte",
                        confidence=0.8,
                        recommended_action="BUY - padrao de reversao de alta confirmado",
                        details={
                            'spring_low': last_3['low'].min(),
                            'recovery_close': last_candle['close'],
                            'range_ratio': range_ratio
                        }
                    )
            
            # Liquidity grab para cima (upthrust)
            if last_3['high'].max() == last_3.iloc[1]['high']:  # High no meio
                if last_candle['close'] < first_candle['open']:
                    return ManipulationEvent(
                        timestamp=datetime.now(),
                        type=ManipulationType.WYCKOFF_UPTHRUST,
                        severity=ManipulationSeverity.HIGH,
                        price=last_3['high'].max(),
                        description="Upthrust (Wyckoff) detectado - liquidez foi capturada acima da resistencia",
                        confidence=0.8,
                        recommended_action="SELL - padrao de reversao de baixa confirmado",
                        details={
                            'upthrust_high': last_3['high'].max(),
                            'recovery_close': last_candle['close'],
                            'range_ratio': range_ratio
                        }
                    )
        
        return None
    
    def detect_institutional_activity(self, symbol: str, df: pd.DataFrame, 
                                      retail_sentiment: Optional[RetailSentiment] = None) -> Optional[ManipulationEvent]:
        """
        Detecta atividade institucional vs varejo
        """
        if df is None or len(df) < 20:
            return None
        
        # Analisar divergencia entre preco e volume
        closes = df['close'].values
        volumes = df['tick_volume'].values if 'tick_volume' in df.columns else None
        
        if volumes is None:
            return None
        
        # Tendencia de preco
        price_trend = closes[-1] - closes[-10]
        
        # Tendencia de volume
        recent_vol = np.mean(volumes[-5:])
        older_vol = np.mean(volumes[-15:-5])
        volume_trend = recent_vol - older_vol
        
        # Divergencia: preco sobe mas volume cai = distribuicao
        if price_trend > 0 and volume_trend < 0:
            return ManipulationEvent(
                timestamp=datetime.now(),
                type=ManipulationType.INSTITUTIONAL_DISTRIBUTION,
                severity=ManipulationSeverity.MEDIUM,
                price=closes[-1],
                description="Possivel distribuicao institucional - preco sobe com volume decrescente",
                confidence=0.6,
                recommended_action="Cautela com posicoes compradas - smart money pode estar vendendo",
                details={
                    'price_change': price_trend,
                    'volume_change': volume_trend,
                    'recent_vol': recent_vol,
                    'older_vol': older_vol
                }
            )
        
        # Divergencia: preco cai mas volume cai = acumulacao
        if price_trend < 0 and volume_trend < 0:
            return ManipulationEvent(
                timestamp=datetime.now(),
                type=ManipulationType.INSTITUTIONAL_ACCUMULATION,
                severity=ManipulationSeverity.MEDIUM,
                price=closes[-1],
                description="Possivel acumulacao institucional - preco cai com volume decrescente",
                confidence=0.6,
                recommended_action="Cautela com posicoes vendidas - smart money pode estar comprando",
                details={
                    'price_change': price_trend,
                    'volume_change': volume_trend,
                    'recent_vol': recent_vol,
                    'older_vol': older_vol
                }
            )
        
        # Se temos sentiment do varejo, verificar divergencia
        if retail_sentiment:
            # Se varejo esta muito long e preco esta caindo = armadilha
            if retail_sentiment.long_percentage > 70 and price_trend < 0:
                return ManipulationEvent(
                    timestamp=datetime.now(),
                    type=ManipulationType.INSTITUTIONAL_DISTRIBUTION,
                    severity=ManipulationSeverity.HIGH,
                    price=closes[-1],
                    description=f"Varejo {retail_sentiment.long_percentage:.0f}% long mas preco caindo - smart money vendendo",
                    confidence=0.75,
                    recommended_action="SELL - varejo esta do lado errado",
                    details={
                        'retail_long': retail_sentiment.long_percentage,
                        'price_trend': price_trend
                    }
                )
            
            # Se varejo esta muito short e preco esta subindo = armadilha
            if retail_sentiment.short_percentage > 70 and price_trend > 0:
                return ManipulationEvent(
                    timestamp=datetime.now(),
                    type=ManipulationType.INSTITUTIONAL_ACCUMULATION,
                    severity=ManipulationSeverity.HIGH,
                    price=closes[-1],
                    description=f"Varejo {retail_sentiment.short_percentage:.0f}% short mas preco subindo - smart money comprando",
                    confidence=0.75,
                    recommended_action="BUY - varejo esta do lado errado",
                    details={
                        'retail_short': retail_sentiment.short_percentage,
                        'price_trend': price_trend
                    }
                )
        
        return None
    
    def run_all_detections(self, symbol: str, df: pd.DataFrame, 
                          retail_sentiment: Optional[RetailSentiment] = None) -> List[ManipulationEvent]:
        """
        Executa todas as deteccoes e retorna lista de eventos
        """
        events = []
        
        # Stop Hunt
        event = self.detect_stop_hunt(symbol, df)
        if event:
            events.append(event)
        
        # Fake Breakout
        event = self.detect_fake_breakout(symbol, df)
        if event:
            events.append(event)
        
        # Volume Spike
        event = self.detect_volume_spike(symbol, df)
        if event:
            events.append(event)
        
        # Spread Manipulation
        event = self.detect_spread_manipulation(symbol)
        if event:
            events.append(event)
        
        # Liquidity Grab
        event = self.detect_liquidity_grab(symbol, df)
        if event:
            events.append(event)
        
        # Institutional Activity
        event = self.detect_institutional_activity(symbol, df, retail_sentiment)
        if event:
            events.append(event)
        
        # Armazenar eventos
        with self._lock:
            self.initialize_symbol(symbol)
            for e in events:
                self._events[symbol].append(e)
        
        return events
    
    def get_recent_events(self, symbol: str, hours: int = 24) -> List[ManipulationEvent]:
        """Retorna eventos recentes"""
        with self._lock:
            if symbol not in self._events:
                return []
            
            cutoff = datetime.now() - timedelta(hours=hours)
            return [e for e in self._events[symbol] if e.timestamp > cutoff]
    
    def get_manipulation_score(self, symbol: str, df: pd.DataFrame) -> Dict:
        """
        Retorna um score de manipulacao (0-100)
        Quanto maior, mais sinais de manipulacao detectados
        """
        events = self.run_all_detections(symbol, df)
        
        score = 0
        details = []
        
        for event in events:
            if event.severity == ManipulationSeverity.LOW:
                score += 10
            elif event.severity == ManipulationSeverity.MEDIUM:
                score += 25
            elif event.severity == ManipulationSeverity.HIGH:
                score += 40
            elif event.severity == ManipulationSeverity.CRITICAL:
                score += 60
            
            details.append({
                'type': event.type.value,
                'severity': event.severity.value,
                'description': event.description
            })
        
        score = min(100, score)
        
        interpretation = "Normal"
        if score > 70:
            interpretation = "ALTO RISCO - Multiplos sinais de manipulacao detectados"
        elif score > 40:
            interpretation = "CAUTELA - Alguns sinais de manipulacao presentes"
        elif score > 20:
            interpretation = "Baixo risco - Poucos sinais de manipulacao"
        
        return {
            'symbol': symbol,
            'score': score,
            'interpretation': interpretation,
            'events_count': len(events),
            'events': details,
            'recommendation': 'Evitar trades' if score > 70 else 'Proceder com cautela' if score > 40 else 'Normal'
        }


# Singleton
_manipulation_detector_instance = None

def get_manipulation_detector(config: Dict = None) -> Optional[ManipulationDetector]:
    """Retorna instancia singleton"""
    global _manipulation_detector_instance
    if _manipulation_detector_instance is None and config:
        _manipulation_detector_instance = ManipulationDetector(config)
    return _manipulation_detector_instance
