# -*- coding: utf-8 -*-
"""
Harmonic Patterns Analyzer - Detector de Padrões Harmônicos Avançados

Detecta padrões harmônicos como Gartley, Butterfly, Bat, Crab, Shark, Cypher
com base em ratios de Fibonacci precisos.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Tipos de padrões harmônicos"""
    GARTLEY = "gartley"
    BUTTERFLY = "butterfly"
    BAT = "bat"
    CRAB = "crab"
    SHARK = "shark"
    CYPHER = "cypher"
    AB_CD = "ab_cd"
    THREE_DRIVE = "three_drive"


class PatternDirection(Enum):
    """Direção do padrão"""
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class SwingPoint:
    """Ponto de swing (pivot)"""
    index: int
    price: float
    timestamp: Optional[datetime] = None
    is_high: bool = True


@dataclass
class HarmonicPattern:
    """Resultado de detecção de padrão harmônico"""
    pattern_type: PatternType
    direction: PatternDirection
    x: SwingPoint
    a: SwingPoint
    b: SwingPoint
    c: SwingPoint
    d: SwingPoint
    
    # Ratios calculados
    xab_ratio: float = 0.0  # AB/XA
    abc_ratio: float = 0.0  # BC/AB
    bcd_ratio: float = 0.0  # CD/BC
    xad_ratio: float = 0.0  # AD/XA
    
    # Qualidade e confiança
    pattern_score: float = 0.0  # 0-100
    ratio_accuracy: float = 0.0  # Precisão dos ratios vs ideal
    is_complete: bool = False
    
    # Níveis de trading
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0  # 38.2% retracement
    take_profit_2: float = 0.0  # 61.8% retracement
    take_profit_3: float = 0.0  # 100% retracement
    
    # Meta
    detected_at: datetime = field(default_factory=datetime.now)
    symbol: str = ""


class HarmonicPatternsAnalyzer:
    """
    Analisador de Padrões Harmônicos com Fibonacci
    
    Detecta e valida padrões harmônicos usando ratios de Fibonacci:
    - Gartley (222 pattern): XAB 0.618, ABC 0.382-0.886, BCD 1.27-1.618, XAD 0.786
    - Butterfly: XAB 0.786, ABC 0.382-0.886, BCD 1.618-2.618, XAD 1.27-1.618
    - Bat: XAB 0.382-0.5, ABC 0.382-0.886, BCD 1.618-2.618, XAD 0.886
    - Crab: XAB 0.382-0.618, ABC 0.382-0.886, BCD 2.24-3.618, XAD 1.618
    - Shark: XAB 0.886-1.13, ABC 0.886-1.13, BCD 1.618-2.24, XAD 0.886-1.13
    - Cypher: XAB 0.382-0.618, ABC 1.13-1.414, BCD 0.786-0.886
    """
    
    # Definição dos ratios ideais para cada padrão
    PATTERN_RATIOS = {
        PatternType.GARTLEY: {
            'xab': (0.618, 0.618),      # Exatamente 0.618
            'abc': (0.382, 0.886),      # Range
            'bcd': (1.27, 1.618),       # Range
            'xad': (0.786, 0.786),      # Exatamente 0.786
            'tolerance': 0.05           # Tolerância de 5%
        },
        PatternType.BUTTERFLY: {
            'xab': (0.786, 0.786),
            'abc': (0.382, 0.886),
            'bcd': (1.618, 2.618),
            'xad': (1.27, 1.618),
            'tolerance': 0.05
        },
        PatternType.BAT: {
            'xab': (0.382, 0.5),
            'abc': (0.382, 0.886),
            'bcd': (1.618, 2.618),
            'xad': (0.886, 0.886),
            'tolerance': 0.05
        },
        PatternType.CRAB: {
            'xab': (0.382, 0.618),
            'abc': (0.382, 0.886),
            'bcd': (2.24, 3.618),
            'xad': (1.618, 1.618),
            'tolerance': 0.05
        },
        PatternType.SHARK: {
            'xab': (0.886, 1.13),
            'abc': (0.886, 1.13),
            'bcd': (1.618, 2.24),
            'xad': (0.886, 1.13),
            'tolerance': 0.08
        },
        PatternType.CYPHER: {
            'xab': (0.382, 0.618),
            'abc': (1.13, 1.414),
            'bcd': (0.786, 0.886),      # CD retrace de XC
            'xad': (0.786, 0.886),
            'tolerance': 0.05
        }
    }
    
    # Fibonacci levels
    FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0, 1.27, 1.414, 1.618, 2.0, 2.24, 2.618, 3.618]
    
    def __init__(self, swing_lookback: int = 5, min_pattern_bars: int = 10, max_pattern_bars: int = 100):
        """
        Inicializa o analisador de padrões harmônicos
        
        Args:
            swing_lookback: Número de barras para identificar swing highs/lows
            min_pattern_bars: Mínimo de barras para um padrão válido
            max_pattern_bars: Máximo de barras para um padrão válido
        """
        self.swing_lookback = swing_lookback
        self.min_pattern_bars = min_pattern_bars
        self.max_pattern_bars = max_pattern_bars
        
        # Cache de padrões detectados
        self._patterns_cache: Dict[str, List[HarmonicPattern]] = {}
        
        logger.info("HarmonicPatternsAnalyzer inicializado")
    
    def find_swing_points(self, df: pd.DataFrame, use_close: bool = False) -> List[SwingPoint]:
        """
        Identifica swing highs e swing lows no DataFrame
        
        Args:
            df: DataFrame com colunas 'high', 'low', 'close', 'time'
            use_close: Se True, usa close ao invés de high/low
            
        Returns:
            Lista ordenada de SwingPoints
        """
        swing_points = []
        lookback = self.swing_lookback
        
        if len(df) < lookback * 2 + 1:
            logger.warning(f"DataFrame muito pequeno: {len(df)} barras")
            return swing_points
        
        high_col = 'close' if use_close else 'high'
        low_col = 'close' if use_close else 'low'
        
        highs = df[high_col].values
        lows = df[low_col].values
        
        for i in range(lookback, len(df) - lookback):
            # Swing High: maior que todos os vizinhos
            is_swing_high = True
            for j in range(1, lookback + 1):
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                timestamp = df.index[i] if isinstance(df.index[i], datetime) else None
                swing_points.append(SwingPoint(
                    index=i,
                    price=highs[i],
                    timestamp=timestamp,
                    is_high=True
                ))
            
            # Swing Low: menor que todos os vizinhos
            is_swing_low = True
            for j in range(1, lookback + 1):
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                timestamp = df.index[i] if isinstance(df.index[i], datetime) else None
                swing_points.append(SwingPoint(
                    index=i,
                    price=lows[i],
                    timestamp=timestamp,
                    is_high=False
                ))
        
        # Ordena por índice
        swing_points.sort(key=lambda x: x.index)
        
        return swing_points
    
    def _calculate_ratios(self, x: float, a: float, b: float, c: float, d: float) -> Dict[str, float]:
        """Calcula os ratios de Fibonacci para o padrão XABCD"""
        xa = abs(a - x)
        ab = abs(b - a)
        bc = abs(c - b)
        cd = abs(d - c)
        ad = abs(d - a)
        
        # Evita divisão por zero
        xab_ratio = ab / xa if xa != 0 else 0
        abc_ratio = bc / ab if ab != 0 else 0
        bcd_ratio = cd / bc if bc != 0 else 0
        xad_ratio = ad / xa if xa != 0 else 0
        
        return {
            'xab': xab_ratio,
            'abc': abc_ratio,
            'bcd': bcd_ratio,
            'xad': xad_ratio
        }
    
    def _ratio_in_range(self, ratio: float, range_min: float, range_max: float, tolerance: float) -> bool:
        """Verifica se ratio está dentro do range com tolerância"""
        return (range_min - tolerance) <= ratio <= (range_max + tolerance)
    
    def _calculate_ratio_accuracy(self, ratios: Dict[str, float], pattern_type: PatternType) -> float:
        """Calcula a precisão dos ratios em relação ao padrão ideal"""
        ideal = self.PATTERN_RATIOS[pattern_type]
        accuracies = []
        
        for ratio_name in ['xab', 'abc', 'bcd', 'xad']:
            actual = ratios[ratio_name]
            ideal_min, ideal_max = ideal[ratio_name]
            ideal_mid = (ideal_min + ideal_max) / 2
            
            if ideal_min == ideal_max:
                # Ratio exato
                deviation = abs(actual - ideal_mid)
                accuracy = max(0, 1 - deviation)
            else:
                # Range
                if actual < ideal_min:
                    deviation = (ideal_min - actual) / ideal_min
                elif actual > ideal_max:
                    deviation = (actual - ideal_max) / ideal_max
                else:
                    deviation = 0
                accuracy = max(0, 1 - deviation)
            
            accuracies.append(accuracy)
        
        return np.mean(accuracies) * 100
    
    def _validate_pattern(self, ratios: Dict[str, float], pattern_type: PatternType) -> bool:
        """Valida se os ratios correspondem ao padrão"""
        ideal = self.PATTERN_RATIOS[pattern_type]
        tolerance = ideal['tolerance']
        
        for ratio_name in ['xab', 'abc', 'bcd', 'xad']:
            ratio_range = ideal[ratio_name]
            if not self._ratio_in_range(ratios[ratio_name], ratio_range[0], ratio_range[1], tolerance):
                return False
        
        return True
    
    def _identify_pattern_type(self, ratios: Dict[str, float]) -> Optional[PatternType]:
        """Identifica qual padrão harmônico corresponde aos ratios"""
        for pattern_type in PatternType:
            if pattern_type in [PatternType.AB_CD, PatternType.THREE_DRIVE]:
                continue  # Padrões especiais tratados separadamente
            
            if self._validate_pattern(ratios, pattern_type):
                return pattern_type
        
        return None
    
    def _calculate_trading_levels(self, pattern: HarmonicPattern) -> HarmonicPattern:
        """Calcula níveis de entrada, stop loss e take profits"""
        x, a, b, c, d = pattern.x.price, pattern.a.price, pattern.b.price, pattern.c.price, pattern.d.price
        
        if pattern.direction == PatternDirection.BULLISH:
            # Bullish: espera reversão para cima
            pattern.entry_price = d
            pattern.stop_loss = d - (abs(c - d) * 0.5)  # 50% abaixo de D
            
            # Take profits baseados em retracement de CD
            cd_range = abs(c - d)
            pattern.take_profit_1 = d + (cd_range * 0.382)  # 38.2%
            pattern.take_profit_2 = d + (cd_range * 0.618)  # 61.8%
            pattern.take_profit_3 = d + cd_range            # 100%
            
        else:
            # Bearish: espera reversão para baixo
            pattern.entry_price = d
            pattern.stop_loss = d + (abs(c - d) * 0.5)  # 50% acima de D
            
            # Take profits baseados em retracement de CD
            cd_range = abs(c - d)
            pattern.take_profit_1 = d - (cd_range * 0.382)  # 38.2%
            pattern.take_profit_2 = d - (cd_range * 0.618)  # 61.8%
            pattern.take_profit_3 = d - cd_range            # 100%
        
        return pattern
    
    def detect_patterns(
        self, 
        df: pd.DataFrame, 
        symbol: str = "",
        patterns_to_detect: Optional[List[PatternType]] = None
    ) -> List[HarmonicPattern]:
        """
        Detecta padrões harmônicos no DataFrame
        
        Args:
            df: DataFrame com OHLC data
            symbol: Símbolo do ativo
            patterns_to_detect: Lista de padrões específicos para detectar (None = todos)
            
        Returns:
            Lista de padrões detectados
        """
        detected_patterns = []
        
        # Encontra swing points
        swing_points = self.find_swing_points(df)
        
        if len(swing_points) < 5:
            logger.debug(f"Poucos swing points encontrados: {len(swing_points)}")
            return detected_patterns
        
        # Filtra padrões a detectar
        if patterns_to_detect is None:
            patterns_to_detect = [pt for pt in PatternType if pt not in [PatternType.AB_CD, PatternType.THREE_DRIVE]]
        
        # Tenta formar padrões XABCD com combinações de 5 swing points consecutivos
        for i in range(len(swing_points) - 4):
            x, a, b, c, d = swing_points[i:i+5]
            
            # Valida estrutura básica
            bars_span = d.index - x.index
            if bars_span < self.min_pattern_bars or bars_span > self.max_pattern_bars:
                continue
            
            # Determina direção
            if x.is_high and not a.is_high and b.is_high and not c.is_high and d.is_high:
                # Swing sequence: High-Low-High-Low-High (potencial Bearish)
                direction = PatternDirection.BEARISH
            elif not x.is_high and a.is_high and not b.is_high and c.is_high and not d.is_high:
                # Swing sequence: Low-High-Low-High-Low (potencial Bullish)
                direction = PatternDirection.BULLISH
            else:
                continue  # Estrutura inválida
            
            # Calcula ratios
            ratios = self._calculate_ratios(x.price, a.price, b.price, c.price, d.price)
            
            # Identifica tipo de padrão
            pattern_type = self._identify_pattern_type(ratios)
            
            if pattern_type and pattern_type in patterns_to_detect:
                accuracy = self._calculate_ratio_accuracy(ratios, pattern_type)
                
                pattern = HarmonicPattern(
                    pattern_type=pattern_type,
                    direction=direction,
                    x=x, a=a, b=b, c=c, d=d,
                    xab_ratio=ratios['xab'],
                    abc_ratio=ratios['abc'],
                    bcd_ratio=ratios['bcd'],
                    xad_ratio=ratios['xad'],
                    pattern_score=accuracy,
                    ratio_accuracy=accuracy,
                    is_complete=True,
                    symbol=symbol
                )
                
                # Calcula níveis de trading
                pattern = self._calculate_trading_levels(pattern)
                
                detected_patterns.append(pattern)
                
                logger.info(f"Padrão {pattern_type.value} detectado em {symbol} - Score: {accuracy:.1f}%")
        
        return detected_patterns
    
    def detect_potential_patterns(
        self, 
        df: pd.DataFrame, 
        symbol: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Detecta padrões potenciais (ainda não completos) para alertas antecipados
        
        Args:
            df: DataFrame com OHLC data
            symbol: Símbolo do ativo
            
        Returns:
            Lista de padrões potenciais com zona de conclusão
        """
        potential_patterns = []
        swing_points = self.find_swing_points(df)
        
        if len(swing_points) < 4:
            return potential_patterns
        
        # Procura por XAB já formados esperando C
        for i in range(len(swing_points) - 3):
            x, a, b, c = swing_points[i:i+4]
            
            # Valida estrutura parcial
            bars_span = c.index - x.index
            if bars_span < self.min_pattern_bars * 0.5:
                continue
            
            ratios = self._calculate_ratios(x.price, a.price, b.price, c.price, c.price)
            
            # Verifica padrões parciais
            for pattern_type in [PatternType.GARTLEY, PatternType.BUTTERFLY, PatternType.BAT, PatternType.CRAB]:
                ideal = self.PATTERN_RATIOS[pattern_type]
                tolerance = ideal['tolerance']
                
                # Valida XAB e ABC
                xab_valid = self._ratio_in_range(ratios['xab'], ideal['xab'][0], ideal['xab'][1], tolerance)
                abc_valid = self._ratio_in_range(ratios['abc'], ideal['abc'][0], ideal['abc'][1], tolerance)
                
                if xab_valid and abc_valid:
                    # Calcula zona D esperada
                    xa = abs(a.price - x.price)
                    bc = abs(c.price - b.price)
                    
                    # D zone baseado em XAD ratio
                    xad_min, xad_max = ideal['xad']
                    
                    # Determina direção esperada
                    if x.is_high:
                        d_zone_low = a.price - (xa * xad_max)
                        d_zone_high = a.price - (xa * xad_min)
                        direction = PatternDirection.BULLISH
                    else:
                        d_zone_low = a.price + (xa * xad_min)
                        d_zone_high = a.price + (xa * xad_max)
                        direction = PatternDirection.BEARISH
                    
                    potential_patterns.append({
                        'pattern_type': pattern_type.value,
                        'direction': direction.value,
                        'x': x.price,
                        'a': a.price,
                        'b': b.price,
                        'c': c.price,
                        'd_zone': (min(d_zone_low, d_zone_high), max(d_zone_low, d_zone_high)),
                        'xab_ratio': ratios['xab'],
                        'abc_ratio': ratios['abc'],
                        'completion_pct': 80,  # 4 de 5 pontos
                        'symbol': symbol
                    })
        
        return potential_patterns
    
    def detect_abcd_pattern(self, df: pd.DataFrame, symbol: str = "") -> List[HarmonicPattern]:
        """
        Detecta padrão AB=CD simples
        
        Ratios ideais:
        - AB = CD (1:1)
        - BC = 0.618-0.786 de AB
        """
        patterns = []
        swing_points = self.find_swing_points(df)
        
        if len(swing_points) < 4:
            return patterns
        
        for i in range(len(swing_points) - 3):
            a, b, c, d = swing_points[i:i+4]
            
            # Valida alternância
            if a.is_high == b.is_high or b.is_high == c.is_high or c.is_high == d.is_high:
                continue
            
            ab = abs(b.price - a.price)
            bc = abs(c.price - b.price)
            cd = abs(d.price - c.price)
            
            if ab == 0:
                continue
            
            # AB=CD ratio (deve ser próximo de 1)
            abcd_ratio = cd / ab
            bc_ratio = bc / ab
            
            # Valida ratios
            if 0.9 <= abcd_ratio <= 1.1 and 0.5 <= bc_ratio <= 0.886:
                direction = PatternDirection.BULLISH if not d.is_high else PatternDirection.BEARISH
                
                # Score baseado na precisão do ratio 1:1
                score = (1 - abs(1 - abcd_ratio)) * 100
                
                # Cria swing X fictício para manter estrutura
                x = SwingPoint(index=a.index, price=a.price, is_high=a.is_high)
                
                pattern = HarmonicPattern(
                    pattern_type=PatternType.AB_CD,
                    direction=direction,
                    x=x, a=a, b=b, c=c, d=d,
                    xab_ratio=1.0,
                    abc_ratio=bc_ratio,
                    bcd_ratio=abcd_ratio,
                    xad_ratio=1.0,
                    pattern_score=score,
                    ratio_accuracy=score,
                    is_complete=True,
                    symbol=symbol
                )
                
                pattern = self._calculate_trading_levels(pattern)
                patterns.append(pattern)
        
        return patterns
    
    def get_signal(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, Any]:
        """
        Gera sinal de trading baseado em padrões harmônicos
        
        Args:
            df: DataFrame com OHLC data
            symbol: Símbolo do ativo
            
        Returns:
            Dict com sinal, força e detalhes
        """
        patterns = self.detect_patterns(df, symbol)
        abcd_patterns = self.detect_abcd_pattern(df, symbol)
        potential = self.detect_potential_patterns(df, symbol)
        
        all_patterns = patterns + abcd_patterns
        
        if not all_patterns and not potential:
            return {
                'signal': 'neutral',
                'strength': 0,
                'patterns': [],
                'potential_patterns': [],
                'message': 'Nenhum padrão harmônico detectado'
            }
        
        # Encontra padrão mais recente e com maior score
        if all_patterns:
            best_pattern = max(all_patterns, key=lambda p: (p.d.index, p.pattern_score))
            
            signal = 'buy' if best_pattern.direction == PatternDirection.BULLISH else 'sell'
            strength = best_pattern.pattern_score / 100
            
            return {
                'signal': signal,
                'strength': strength,
                'patterns': [self._pattern_to_dict(p) for p in all_patterns],
                'potential_patterns': potential,
                'best_pattern': self._pattern_to_dict(best_pattern),
                'entry_price': best_pattern.entry_price,
                'stop_loss': best_pattern.stop_loss,
                'take_profit_1': best_pattern.take_profit_1,
                'take_profit_2': best_pattern.take_profit_2,
                'take_profit_3': best_pattern.take_profit_3,
                'message': f"Padrão {best_pattern.pattern_type.value} {best_pattern.direction.value} detectado"
            }
        
        # Só padrões potenciais
        return {
            'signal': 'watch',
            'strength': 0.5,
            'patterns': [],
            'potential_patterns': potential,
            'message': f"{len(potential)} padrão(ões) potencial(is) em formação"
        }
    
    def _pattern_to_dict(self, pattern: HarmonicPattern) -> Dict[str, Any]:
        """Converte HarmonicPattern para dicionário"""
        return {
            'type': pattern.pattern_type.value,
            'direction': pattern.direction.value,
            'x': pattern.x.price,
            'a': pattern.a.price,
            'b': pattern.b.price,
            'c': pattern.c.price,
            'd': pattern.d.price,
            'xab_ratio': round(pattern.xab_ratio, 3),
            'abc_ratio': round(pattern.abc_ratio, 3),
            'bcd_ratio': round(pattern.bcd_ratio, 3),
            'xad_ratio': round(pattern.xad_ratio, 3),
            'score': round(pattern.pattern_score, 1),
            'entry': pattern.entry_price,
            'stop_loss': pattern.stop_loss,
            'tp1': pattern.take_profit_1,
            'tp2': pattern.take_profit_2,
            'tp3': pattern.take_profit_3,
            'symbol': pattern.symbol
        }


# Instância global
_harmonic_analyzer: Optional[HarmonicPatternsAnalyzer] = None


def get_harmonic_analyzer() -> HarmonicPatternsAnalyzer:
    """Retorna instância singleton do analisador de padrões harmônicos"""
    global _harmonic_analyzer
    if _harmonic_analyzer is None:
        _harmonic_analyzer = HarmonicPatternsAnalyzer()
    return _harmonic_analyzer


# Exemplo de uso
if __name__ == "__main__":
    # Cria dados de exemplo
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=200, freq='1H')
    
    # Simula movimento de preço com padrão
    prices = [100.0]
    for _ in range(199):
        change = np.random.randn() * 0.5
        prices.append(prices[-1] * (1 + change / 100))
    
    df = pd.DataFrame({
        'open': prices,
        'high': [p * (1 + abs(np.random.randn()) * 0.001) for p in prices],
        'low': [p * (1 - abs(np.random.randn()) * 0.001) for p in prices],
        'close': prices,
        'volume': np.random.randint(1000, 10000, 200)
    }, index=dates)
    
    analyzer = get_harmonic_analyzer()
    
    # Encontra swing points
    swings = analyzer.find_swing_points(df)
    print(f"Swing points encontrados: {len(swings)}")
    
    # Detecta padrões
    patterns = analyzer.detect_patterns(df, "EURUSD")
    print(f"Padrões detectados: {len(patterns)}")
    
    # Gera sinal
    signal = analyzer.get_signal(df, "EURUSD")
    print(f"Sinal: {signal['signal']}, Força: {signal['strength']}")
