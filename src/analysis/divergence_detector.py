"""
Divergence Detector
Detecta divergências entre preço e indicadores (RSI, MACD, Stochastic)

Tipos de Divergência:
- Regular Bullish: Preço faz lower low, indicador faz higher low → Sinal de compra
- Regular Bearish: Preço faz higher high, indicador faz lower high → Sinal de venda
- Hidden Bullish: Preço faz higher low, indicador faz lower low → Continuação alta
- Hidden Bearish: Preço faz lower high, indicador faz higher high → Continuação baixa
"""
import MetaTrader5 as mt5
import numpy as np
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime
from loguru import logger
from enum import Enum
from dataclasses import dataclass


class DivergenceType(Enum):
    """Tipos de divergência"""
    REGULAR_BULLISH = "regular_bullish"
    REGULAR_BEARISH = "regular_bearish"
    HIDDEN_BULLISH = "hidden_bullish"
    HIDDEN_BEARISH = "hidden_bearish"
    NONE = "none"


class IndicatorType(Enum):
    """Indicadores para detectar divergência"""
    RSI = "rsi"
    MACD = "macd"
    STOCHASTIC = "stochastic"
    OBV = "obv"


@dataclass
class DivergenceSignal:
    """Sinal de divergência detectado"""
    type: DivergenceType
    indicator: IndicatorType
    strength: float  # 0.0 a 1.0
    price_points: Tuple[float, float]  # (preço1, preço2)
    indicator_points: Tuple[float, float]  # (ind1, ind2)
    bar_distance: int  # Distância em barras entre os pontos
    confidence: float  # Confiança geral do sinal
    description: str


class DivergenceDetector:
    """
    Detector de Divergências em Múltiplos Indicadores
    
    Uso:
        detector = DivergenceDetector(mt5_connector)
        signals = detector.detect_all("XAUUSD", mt5.TIMEFRAME_H1)
        
        for signal in signals:
            if signal.type == DivergenceType.REGULAR_BULLISH:
                # Sinal de compra forte
                pass
    """
    
    def __init__(self, mt5_connector, config: Optional[Dict] = None):
        """
        Inicializa o detector
        
        Args:
            mt5_connector: Instância do MT5Connector
            config: Configuração opcional
        """
        self.mt5 = mt5_connector
        self.config = config or {}
        
        # Configurações
        div_config = self.config.get('divergence', {})
        self.lookback_bars = div_config.get('lookback_bars', 50)
        self.min_bar_distance = div_config.get('min_bar_distance', 5)
        self.max_bar_distance = div_config.get('max_bar_distance', 30)
        self.rsi_period = div_config.get('rsi_period', 14)
        self.swing_sensitivity = div_config.get('swing_sensitivity', 2)
        
        logger.info(
            f"🔍 Divergence Detector inicializado | "
            f"Lookback: {self.lookback_bars} bars | "
            f"Distance: {self.min_bar_distance}-{self.max_bar_distance}"
        )
    
    def calculate_rsi(
        self,
        closes: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Calcula RSI"""
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.zeros(len(closes))
        avg_losses = np.zeros(len(closes))
        
        # SMA inicial
        avg_gains[period] = np.mean(gains[:period])
        avg_losses[period] = np.mean(losses[:period])
        
        # EMA para o resto
        for i in range(period + 1, len(closes)):
            avg_gains[i] = (avg_gains[i-1] * (period-1) + gains[i-1]) / period
            avg_losses[i] = (avg_losses[i-1] * (period-1) + losses[i-1]) / period
        
        rs = np.divide(avg_gains, avg_losses, out=np.ones_like(avg_gains), where=avg_losses != 0)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(
        self,
        closes: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Calcula MACD, Signal, Histogram"""
        
        def ema(data: np.ndarray, period: int) -> np.ndarray:
            alpha = 2 / (period + 1)
            result = np.zeros_like(data)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
            return result
        
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        macd_line = ema_fast - ema_slow
        signal_line = ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_stochastic(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        k_period: int = 14,
        d_period: int = 3
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calcula Stochastic %K e %D"""
        stoch_k = np.zeros(len(closes))
        
        for i in range(k_period, len(closes)):
            highest_high = np.max(highs[i-k_period:i])
            lowest_low = np.min(lows[i-k_period:i])
            
            if highest_high - lowest_low > 0:
                stoch_k[i] = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100
            else:
                stoch_k[i] = 50
        
        # %D é SMA de %K
        stoch_d = np.convolve(stoch_k, np.ones(d_period)/d_period, mode='same')
        
        return stoch_k, stoch_d
    
    def find_swing_points(
        self,
        data: np.ndarray,
        sensitivity: int = 2
    ) -> Tuple[List[int], List[int]]:
        """
        Encontra swing highs e lows
        
        Args:
            data: Array de preços ou valores do indicador
            sensitivity: Número de barras para confirmar swing
            
        Returns:
            Tuple de (índices de swing highs, índices de swing lows)
        """
        highs = []
        lows = []
        
        for i in range(sensitivity, len(data) - sensitivity):
            # Swing High
            is_high = True
            for j in range(1, sensitivity + 1):
                if data[i] <= data[i-j] or data[i] <= data[i+j]:
                    is_high = False
                    break
            if is_high:
                highs.append(i)
            
            # Swing Low
            is_low = True
            for j in range(1, sensitivity + 1):
                if data[i] >= data[i-j] or data[i] >= data[i+j]:
                    is_low = False
                    break
            if is_low:
                lows.append(i)
        
        return highs, lows
    
    def detect_divergence(
        self,
        price_data: np.ndarray,
        indicator_data: np.ndarray,
        indicator_type: IndicatorType
    ) -> List[DivergenceSignal]:
        """
        Detecta divergências entre preço e indicador
        
        Args:
            price_data: Array de preços (closes ou highs/lows)
            indicator_data: Array de valores do indicador
            indicator_type: Tipo do indicador
            
        Returns:
            Lista de sinais de divergência
        """
        signals = []
        
        try:
            # Encontrar swing points no preço
            price_highs, price_lows = self.find_swing_points(
                price_data, self.swing_sensitivity
            )
            
            # Encontrar swing points no indicador
            ind_highs, ind_lows = self.find_swing_points(
                indicator_data, self.swing_sensitivity
            )
            
            # Detectar Regular Bullish (price lower low, indicator higher low)
            for i in range(len(price_lows) - 1):
                idx1 = price_lows[i]
                idx2 = price_lows[i + 1]
                
                # Verificar distância
                if idx2 - idx1 < self.min_bar_distance or idx2 - idx1 > self.max_bar_distance:
                    continue
                
                # Preço faz lower low?
                if price_data[idx2] < price_data[idx1]:
                    # Indicador faz higher low?
                    if indicator_data[idx2] > indicator_data[idx1]:
                        strength = abs(indicator_data[idx2] - indicator_data[idx1]) / max(abs(indicator_data[idx1]), 1)
                        
                        signals.append(DivergenceSignal(
                            type=DivergenceType.REGULAR_BULLISH,
                            indicator=indicator_type,
                            strength=min(strength, 1.0),
                            price_points=(price_data[idx1], price_data[idx2]),
                            indicator_points=(indicator_data[idx1], indicator_data[idx2]),
                            bar_distance=idx2 - idx1,
                            confidence=0.7 + (0.3 * min(strength, 1.0)),
                            description=f"Regular Bullish: Price LL, {indicator_type.value.upper()} HL"
                        ))
            
            # Detectar Regular Bearish (price higher high, indicator lower high)
            for i in range(len(price_highs) - 1):
                idx1 = price_highs[i]
                idx2 = price_highs[i + 1]
                
                if idx2 - idx1 < self.min_bar_distance or idx2 - idx1 > self.max_bar_distance:
                    continue
                
                # Preço faz higher high?
                if price_data[idx2] > price_data[idx1]:
                    # Indicador faz lower high?
                    if indicator_data[idx2] < indicator_data[idx1]:
                        strength = abs(indicator_data[idx1] - indicator_data[idx2]) / max(abs(indicator_data[idx1]), 1)
                        
                        signals.append(DivergenceSignal(
                            type=DivergenceType.REGULAR_BEARISH,
                            indicator=indicator_type,
                            strength=min(strength, 1.0),
                            price_points=(price_data[idx1], price_data[idx2]),
                            indicator_points=(indicator_data[idx1], indicator_data[idx2]),
                            bar_distance=idx2 - idx1,
                            confidence=0.7 + (0.3 * min(strength, 1.0)),
                            description=f"Regular Bearish: Price HH, {indicator_type.value.upper()} LH"
                        ))
            
            # Detectar Hidden Bullish (price higher low, indicator lower low)
            for i in range(len(price_lows) - 1):
                idx1 = price_lows[i]
                idx2 = price_lows[i + 1]
                
                if idx2 - idx1 < self.min_bar_distance or idx2 - idx1 > self.max_bar_distance:
                    continue
                
                # Preço faz higher low?
                if price_data[idx2] > price_data[idx1]:
                    # Indicador faz lower low?
                    if indicator_data[idx2] < indicator_data[idx1]:
                        strength = abs(indicator_data[idx1] - indicator_data[idx2]) / max(abs(indicator_data[idx1]), 1)
                        
                        signals.append(DivergenceSignal(
                            type=DivergenceType.HIDDEN_BULLISH,
                            indicator=indicator_type,
                            strength=min(strength, 1.0),
                            price_points=(price_data[idx1], price_data[idx2]),
                            indicator_points=(indicator_data[idx1], indicator_data[idx2]),
                            bar_distance=idx2 - idx1,
                            confidence=0.6 + (0.3 * min(strength, 1.0)),
                            description=f"Hidden Bullish: Price HL, {indicator_type.value.upper()} LL (continuation)"
                        ))
            
            # Detectar Hidden Bearish (price lower high, indicator higher high)
            for i in range(len(price_highs) - 1):
                idx1 = price_highs[i]
                idx2 = price_highs[i + 1]
                
                if idx2 - idx1 < self.min_bar_distance or idx2 - idx1 > self.max_bar_distance:
                    continue
                
                # Preço faz lower high?
                if price_data[idx2] < price_data[idx1]:
                    # Indicador faz higher high?
                    if indicator_data[idx2] > indicator_data[idx1]:
                        strength = abs(indicator_data[idx2] - indicator_data[idx1]) / max(abs(indicator_data[idx1]), 1)
                        
                        signals.append(DivergenceSignal(
                            type=DivergenceType.HIDDEN_BEARISH,
                            indicator=indicator_type,
                            strength=min(strength, 1.0),
                            price_points=(price_data[idx1], price_data[idx2]),
                            indicator_points=(indicator_data[idx1], indicator_data[idx2]),
                            bar_distance=idx2 - idx1,
                            confidence=0.6 + (0.3 * min(strength, 1.0)),
                            description=f"Hidden Bearish: Price LH, {indicator_type.value.upper()} HH (continuation)"
                        ))
            
            return signals
            
        except Exception as e:
            logger.error(f"Erro ao detectar divergência: {e}")
            return []
    
    def detect_all(
        self,
        symbol: str,
        timeframe: int = mt5.TIMEFRAME_H1
    ) -> Dict[str, Any]:
        """
        Detecta divergências em múltiplos indicadores
        
        Args:
            symbol: Símbolo (ex: XAUUSD)
            timeframe: Timeframe MT5
            
        Returns:
            Dict com todas as divergências encontradas
        """
        try:
            # Obter dados
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, self.lookback_bars + 50)
            
            if rates is None or len(rates) < self.lookback_bars:
                logger.warning(f"Dados insuficientes para divergência: {symbol}")
                return {"signals": [], "summary": {}}
            
            # Extrair arrays
            closes = np.array([r['close'] for r in rates])
            highs = np.array([r['high'] for r in rates])
            lows = np.array([r['low'] for r in rates])
            
            # Calcular indicadores
            rsi = self.calculate_rsi(closes, self.rsi_period)
            macd_line, _, macd_hist = self.calculate_macd(closes)
            stoch_k, _ = self.calculate_stochastic(highs, lows, closes)
            
            all_signals = []
            
            # Detectar divergências RSI
            rsi_signals = self.detect_divergence(closes, rsi, IndicatorType.RSI)
            all_signals.extend(rsi_signals)
            
            # Detectar divergências MACD
            macd_signals = self.detect_divergence(closes, macd_hist, IndicatorType.MACD)
            all_signals.extend(macd_signals)
            
            # Detectar divergências Stochastic
            stoch_signals = self.detect_divergence(closes, stoch_k, IndicatorType.STOCHASTIC)
            all_signals.extend(stoch_signals)
            
            # Ordenar por confiança
            all_signals.sort(key=lambda x: x.confidence, reverse=True)
            
            # Filtrar apenas sinais recentes (últimas 10 barras)
            recent_signals = [s for s in all_signals if s.bar_distance <= 10]
            
            # Resumo
            summary = {
                "total_signals": len(all_signals),
                "recent_signals": len(recent_signals),
                "bullish_count": sum(1 for s in recent_signals if "bullish" in s.type.value.lower()),
                "bearish_count": sum(1 for s in recent_signals if "bearish" in s.type.value.lower()),
                "strongest_signal": recent_signals[0] if recent_signals else None,
            }
            
            # Bias geral
            if summary["bullish_count"] > summary["bearish_count"]:
                summary["bias"] = "BULLISH"
                summary["bias_strength"] = summary["bullish_count"] / max(summary["total_signals"], 1)
            elif summary["bearish_count"] > summary["bullish_count"]:
                summary["bias"] = "BEARISH"
                summary["bias_strength"] = summary["bearish_count"] / max(summary["total_signals"], 1)
            else:
                summary["bias"] = "NEUTRAL"
                summary["bias_strength"] = 0.0
            
            # Log de sinais importantes
            for signal in recent_signals[:3]:
                logger.info(
                    f"🔍 Divergência [{symbol}] {signal.type.value} | "
                    f"Indicator: {signal.indicator.value.upper()} | "
                    f"Confidence: {signal.confidence:.2%} | "
                    f"{signal.description}"
                )
            
            return {
                "signals": recent_signals,
                "all_signals": all_signals,
                "summary": summary,
                "indicators": {
                    "rsi_current": rsi[-1],
                    "macd_current": macd_hist[-1],
                    "stoch_current": stoch_k[-1],
                },
            }
            
        except Exception as e:
            logger.error(f"Erro ao detectar divergências: {e}")
            return {"signals": [], "summary": {"error": str(e)}}
    
    def get_trade_signal(
        self,
        symbol: str,
        timeframe: int = mt5.TIMEFRAME_H1,
        min_confidence: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Retorna sinal de trade se houver divergência forte
        
        Args:
            symbol: Símbolo
            timeframe: Timeframe
            min_confidence: Confiança mínima para sinal
            
        Returns:
            Dict com sinal ou None
        """
        result = self.detect_all(symbol, timeframe)
        
        if not result["signals"]:
            return None
        
        # Pegar sinal mais forte
        strongest = result["signals"][0]
        
        if strongest.confidence < min_confidence:
            return None
        
        # Determinar direção
        if "bullish" in strongest.type.value.lower():
            direction = "BUY"
        else:
            direction = "SELL"
        
        return {
            "action": direction,
            "confidence": strongest.confidence,
            "type": strongest.type.value,
            "indicator": strongest.indicator.value,
            "description": strongest.description,
            "bar_distance": strongest.bar_distance,
        }


# Singleton
_detector: Optional[DivergenceDetector] = None


def get_divergence_detector(
    mt5_connector,
    config: Optional[Dict] = None
) -> DivergenceDetector:
    """Obtém instância singleton do detector"""
    global _detector
    if _detector is None:
        _detector = DivergenceDetector(mt5_connector, config)
    return _detector


# Exemplo de uso:
"""
from analysis.divergence_detector import get_divergence_detector, DivergenceType

detector = get_divergence_detector(mt5_connector, config)

# Detectar todas as divergências
result = detector.detect_all("XAUUSD", mt5.TIMEFRAME_H1)

print(f"Total de sinais: {result['summary']['total_signals']}")
print(f"Bias: {result['summary']['bias']}")

# Verificar se há sinal de trade
signal = detector.get_trade_signal("XAUUSD")
if signal:
    print(f"Sinal: {signal['action']} com {signal['confidence']:.2%} confiança")
    print(f"Tipo: {signal['type']} - {signal['description']}")
"""
