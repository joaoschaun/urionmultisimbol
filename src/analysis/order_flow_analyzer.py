# -*- coding: utf-8 -*-
"""
Order Flow Intelligence System
==============================
Simula Order Book e analisa fluxo de ordens usando dados do MT5.
Como Forex e OTC, usamos tick data para inferir order flow.

Funcionalidades:
- Volume Delta (compra vs venda)
- Cumulative Delta
- Volume Profile
- Footprint Chart simulation
- DOM (Depth of Market) simulation
- Imbalance Detection
- Liquidity Zones
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from loguru import logger
from enum import Enum
import threading
import time

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class OrderFlowSignal(Enum):
    """Sinais de Order Flow"""
    STRONG_BUYING = "strong_buying"
    MODERATE_BUYING = "moderate_buying"
    NEUTRAL = "neutral"
    MODERATE_SELLING = "moderate_selling"
    STRONG_SELLING = "strong_selling"
    ABSORPTION = "absorption"
    EXHAUSTION = "exhaustion"


@dataclass
class TickData:
    """Dados de um tick"""
    time: datetime
    bid: float
    ask: float
    last: float
    volume: int
    flags: int


@dataclass
class VolumeLevel:
    """Volume em um nivel de preco"""
    price: float
    buy_volume: int
    sell_volume: int
    delta: int
    total_volume: int
    imbalance_ratio: float


@dataclass
class FootprintBar:
    """Barra de Footprint Chart"""
    time: datetime
    open: float
    high: float
    low: float
    close: float
    levels: Dict[float, VolumeLevel]
    total_delta: int
    poc: float  # Point of Control
    value_area_high: float
    value_area_low: float


@dataclass
class LiquidityZone:
    """Zona de liquidez identificada"""
    price_start: float
    price_end: float
    volume: int
    zone_type: str  # 'support', 'resistance', 'neutral'
    strength: float  # 0-1
    touched_count: int
    last_touch: datetime


class OrderFlowAnalyzer:
    """
    Analisador de Order Flow para mercados OTC (Forex)
    Simula DOM e detecta padroes de fluxo institucional
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.order_flow_config = config.get('order_flow', {})
        
        # Configuracoes
        self.tick_buffer_size = self.order_flow_config.get('tick_buffer_size', 10000)
        self.volume_profile_levels = self.order_flow_config.get('volume_profile_levels', 50)
        self.imbalance_threshold = self.order_flow_config.get('imbalance_threshold', 3.0)
        self.delta_threshold = self.order_flow_config.get('delta_threshold', 100)
        
        # Buffers de dados
        self._tick_buffer: Dict[str, deque] = {}
        self._volume_profile: Dict[str, Dict[float, VolumeLevel]] = {}
        self._cumulative_delta: Dict[str, int] = {}
        self._footprint_bars: Dict[str, List[FootprintBar]] = {}
        self._liquidity_zones: Dict[str, List[LiquidityZone]] = {}
        
        # Lock para thread safety
        self._lock = threading.Lock()
        
        # Flags
        self._running = False
        self._collector_thread = None
        
        logger.info("OrderFlowAnalyzer inicializado")
    
    def start(self, symbols: List[str]):
        """Inicia coleta de ticks para os simbolos"""
        if self._running:
            return
        
        self._running = True
        for symbol in symbols:
            self._tick_buffer[symbol] = deque(maxlen=self.tick_buffer_size)
            self._volume_profile[symbol] = {}
            self._cumulative_delta[symbol] = 0
            self._footprint_bars[symbol] = []
            self._liquidity_zones[symbol] = []
        
        self._collector_thread = threading.Thread(target=self._collect_ticks, args=(symbols,))
        self._collector_thread.daemon = True
        self._collector_thread.start()
        
        logger.info(f"Order Flow collection started for: {symbols}")
    
    def stop(self):
        """Para a coleta de ticks"""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=5)
        logger.info("Order Flow collection stopped")
    
    def _collect_ticks(self, symbols: List[str]):
        """Thread que coleta ticks continuamente"""
        if not mt5:
            logger.warning("MT5 nao disponivel para coleta de ticks")
            return
        
        while self._running:
            try:
                for symbol in symbols:
                    # Copiar ultimos ticks
                    ticks = mt5.copy_ticks_from(
                        symbol,
                        datetime.now() - timedelta(seconds=1),
                        100,
                        mt5.COPY_TICKS_ALL
                    )
                    
                    if ticks is not None and len(ticks) > 0:
                        with self._lock:
                            for tick in ticks:
                                tick_data = TickData(
                                    time=datetime.fromtimestamp(tick['time']),
                                    bid=tick['bid'],
                                    ask=tick['ask'],
                                    last=tick['last'] if 'last' in tick.dtype.names else tick['bid'],
                                    volume=int(tick['volume']) if 'volume' in tick.dtype.names else 1,
                                    flags=int(tick['flags']) if 'flags' in tick.dtype.names else 0
                                )
                                self._process_tick(symbol, tick_data)
                
                time.sleep(0.1)  # 100ms entre coletas
                
            except Exception as e:
                logger.error(f"Erro na coleta de ticks: {e}")
                time.sleep(1)
    
    def _process_tick(self, symbol: str, tick: TickData):
        """Processa um tick e atualiza metricas"""
        self._tick_buffer[symbol].append(tick)
        
        # Determinar se e compra ou venda baseado no preco
        # Se last >= ask -> compra agressiva
        # Se last <= bid -> venda agressiva
        mid = (tick.bid + tick.ask) / 2
        
        if tick.last >= mid:
            # Compra
            delta = tick.volume
        else:
            # Venda
            delta = -tick.volume
        
        # Atualizar cumulative delta
        self._cumulative_delta[symbol] += delta
        
        # Atualizar volume profile
        price_level = round(tick.last, 2)  # Arredondar para 2 casas
        
        if price_level not in self._volume_profile[symbol]:
            self._volume_profile[symbol][price_level] = VolumeLevel(
                price=price_level,
                buy_volume=0,
                sell_volume=0,
                delta=0,
                total_volume=0,
                imbalance_ratio=1.0
            )
        
        level = self._volume_profile[symbol][price_level]
        if delta > 0:
            level.buy_volume += abs(delta)
        else:
            level.sell_volume += abs(delta)
        level.delta = level.buy_volume - level.sell_volume
        level.total_volume = level.buy_volume + level.sell_volume
        
        if level.sell_volume > 0:
            level.imbalance_ratio = level.buy_volume / level.sell_volume
        else:
            level.imbalance_ratio = float('inf') if level.buy_volume > 0 else 1.0
    
    def get_current_delta(self, symbol: str) -> int:
        """Retorna o delta atual (ultimos N ticks)"""
        with self._lock:
            if symbol not in self._tick_buffer:
                return 0
            
            ticks = list(self._tick_buffer[symbol])[-100:]  # Ultimos 100 ticks
            delta = 0
            
            for tick in ticks:
                mid = (tick.bid + tick.ask) / 2
                if tick.last >= mid:
                    delta += tick.volume
                else:
                    delta -= tick.volume
            
            return delta
    
    def get_cumulative_delta(self, symbol: str) -> int:
        """Retorna delta cumulativo desde o inicio"""
        with self._lock:
            return self._cumulative_delta.get(symbol, 0)
    
    def get_volume_profile(self, symbol: str, levels: int = 20) -> List[VolumeLevel]:
        """Retorna os niveis de volume mais significativos"""
        with self._lock:
            if symbol not in self._volume_profile:
                return []
            
            all_levels = list(self._volume_profile[symbol].values())
            # Ordenar por volume total
            sorted_levels = sorted(all_levels, key=lambda x: x.total_volume, reverse=True)
            return sorted_levels[:levels]
    
    def get_poc(self, symbol: str) -> Optional[float]:
        """Retorna Point of Control (preco com maior volume)"""
        levels = self.get_volume_profile(symbol, 1)
        if levels:
            return levels[0].price
        return None
    
    def get_value_area(self, symbol: str, percentage: float = 0.70) -> Tuple[float, float]:
        """Retorna Value Area (High e Low)"""
        with self._lock:
            if symbol not in self._volume_profile:
                return (0, 0)
            
            all_levels = list(self._volume_profile[symbol].values())
            if not all_levels:
                return (0, 0)
            
            total_volume = sum(l.total_volume for l in all_levels)
            target_volume = total_volume * percentage
            
            # Ordenar por volume
            sorted_levels = sorted(all_levels, key=lambda x: x.total_volume, reverse=True)
            
            accumulated = 0
            prices = []
            for level in sorted_levels:
                accumulated += level.total_volume
                prices.append(level.price)
                if accumulated >= target_volume:
                    break
            
            if prices:
                return (max(prices), min(prices))
            return (0, 0)
    
    def detect_imbalances(self, symbol: str) -> List[Dict]:
        """Detecta desequilibrios de volume (stacked imbalances)"""
        with self._lock:
            if symbol not in self._volume_profile:
                return []
            
            imbalances = []
            all_levels = sorted(
                self._volume_profile[symbol].values(),
                key=lambda x: x.price
            )
            
            for level in all_levels:
                if level.imbalance_ratio >= self.imbalance_threshold:
                    imbalances.append({
                        'price': level.price,
                        'type': 'buying_imbalance',
                        'ratio': level.imbalance_ratio,
                        'buy_volume': level.buy_volume,
                        'sell_volume': level.sell_volume
                    })
                elif level.imbalance_ratio <= 1/self.imbalance_threshold:
                    imbalances.append({
                        'price': level.price,
                        'type': 'selling_imbalance',
                        'ratio': level.imbalance_ratio,
                        'buy_volume': level.buy_volume,
                        'sell_volume': level.sell_volume
                    })
            
            return imbalances
    
    def detect_liquidity_zones(self, symbol: str, df: pd.DataFrame) -> List[LiquidityZone]:
        """Detecta zonas de liquidez baseado em price action"""
        zones = []
        
        if df is None or len(df) < 20:
            return zones
        
        # Identificar swing highs e lows
        highs = df['high'].values
        lows = df['low'].values
        
        # Swing highs (resistencias)
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                # Calcular volume na zona
                zone_volume = int(df.iloc[i-2:i+3]['tick_volume'].sum()) if 'tick_volume' in df.columns else 100
                
                zones.append(LiquidityZone(
                    price_start=highs[i] - 0.5,
                    price_end=highs[i] + 0.5,
                    volume=zone_volume,
                    zone_type='resistance',
                    strength=0.7,
                    touched_count=1,
                    last_touch=datetime.now()
                ))
        
        # Swing lows (suportes)
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                zone_volume = int(df.iloc[i-2:i+3]['tick_volume'].sum()) if 'tick_volume' in df.columns else 100
                
                zones.append(LiquidityZone(
                    price_start=lows[i] - 0.5,
                    price_end=lows[i] + 0.5,
                    volume=zone_volume,
                    zone_type='support',
                    strength=0.7,
                    touched_count=1,
                    last_touch=datetime.now()
                ))
        
        self._liquidity_zones[symbol] = zones
        return zones
    
    def get_order_flow_signal(self, symbol: str) -> OrderFlowSignal:
        """Retorna sinal baseado no order flow"""
        delta = self.get_current_delta(symbol)
        cum_delta = self.get_cumulative_delta(symbol)
        
        # Analisar delta
        if delta > self.delta_threshold * 2:
            return OrderFlowSignal.STRONG_BUYING
        elif delta > self.delta_threshold:
            return OrderFlowSignal.MODERATE_BUYING
        elif delta < -self.delta_threshold * 2:
            return OrderFlowSignal.STRONG_SELLING
        elif delta < -self.delta_threshold:
            return OrderFlowSignal.MODERATE_SELLING
        
        # Detectar absorcao (grande volume sem movimento)
        volume_profile = self.get_volume_profile(symbol, 5)
        if volume_profile:
            total_vol = sum(l.total_volume for l in volume_profile)
            if total_vol > 1000 and abs(delta) < self.delta_threshold / 2:
                return OrderFlowSignal.ABSORPTION
        
        return OrderFlowSignal.NEUTRAL
    
    def get_analysis(self, symbol: str, df: pd.DataFrame = None) -> Dict:
        """Retorna analise completa de order flow"""
        delta = self.get_current_delta(symbol)
        cum_delta = self.get_cumulative_delta(symbol)
        poc = self.get_poc(symbol)
        vah, val = self.get_value_area(symbol)
        imbalances = self.detect_imbalances(symbol)
        signal = self.get_order_flow_signal(symbol)
        
        # Detectar zonas de liquidez se tiver dados
        liquidity_zones = []
        if df is not None:
            liquidity_zones = self.detect_liquidity_zones(symbol, df)
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'delta': {
                'current': delta,
                'cumulative': cum_delta,
                'signal': signal.value
            },
            'volume_profile': {
                'poc': poc,
                'value_area_high': vah,
                'value_area_low': val,
                'levels': len(self._volume_profile.get(symbol, {}))
            },
            'imbalances': imbalances[:10],  # Top 10
            'liquidity_zones': [
                {
                    'price_start': z.price_start,
                    'price_end': z.price_end,
                    'type': z.zone_type,
                    'strength': z.strength
                }
                for z in liquidity_zones[:10]
            ],
            'interpretation': self._interpret_flow(delta, cum_delta, imbalances)
        }
    
    def _interpret_flow(self, delta: int, cum_delta: int, imbalances: List) -> str:
        """Interpreta o fluxo de ordens"""
        interpretations = []
        
        if delta > self.delta_threshold:
            interpretations.append("Pressao compradora no curto prazo")
        elif delta < -self.delta_threshold:
            interpretations.append("Pressao vendedora no curto prazo")
        
        if cum_delta > 0:
            interpretations.append(f"Acumulacao de compras (+{cum_delta})")
        elif cum_delta < 0:
            interpretations.append(f"Acumulacao de vendas ({cum_delta})")
        
        buying_imb = len([i for i in imbalances if i['type'] == 'buying_imbalance'])
        selling_imb = len([i for i in imbalances if i['type'] == 'selling_imbalance'])
        
        if buying_imb > selling_imb + 2:
            interpretations.append("Multiplos desequilibrios de compra detectados")
        elif selling_imb > buying_imb + 2:
            interpretations.append("Multiplos desequilibrios de venda detectados")
        
        return " | ".join(interpretations) if interpretations else "Fluxo equilibrado"


# Singleton
_order_flow_instance = None

def get_order_flow_analyzer(config: Dict = None) -> Optional[OrderFlowAnalyzer]:
    """Retorna instancia singleton do OrderFlowAnalyzer"""
    global _order_flow_instance
    if _order_flow_instance is None and config:
        _order_flow_instance = OrderFlowAnalyzer(config)
    return _order_flow_instance
