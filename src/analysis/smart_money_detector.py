"""
Smart Money Detector
Detecta atividade institucional (baleias, bancos, fundos) no mercado

Padrões detectados:
1. ABSORÇÃO: Volume alto + movimento de preço pequeno = instituições acumulando
2. STOP HUNTING: Spike rápido seguido de reversão = busca de liquidez
3. DIVERGÊNCIA DE VOLUME: Preço sobe mas volume cai = movimento fraco (retail)
4. DISTRIBUIÇÃO: Preço em topo + volume aumentando = instituições vendendo
5. ACUMULAÇÃO: Preço em fundo + volume aumentando = instituições comprando
"""

import MetaTrader5 as mt5
import numpy as np
from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class SmartMoneySignal(Enum):
    """Tipos de sinais de Smart Money"""
    ABSORPTION = "absorption"              # Absorção de volume
    STOP_HUNT = "stop_hunt"               # Stop hunting
    VOLUME_DIVERGENCE = "volume_divergence"  # Divergência de volume
    DISTRIBUTION = "distribution"          # Distribuição (topo)
    ACCUMULATION = "accumulation"          # Acumulação (fundo)
    NONE = "none"


@dataclass
class SmartMoneyAnalysis:
    """Resultado da análise de Smart Money"""
    signal: SmartMoneySignal
    confidence: float  # 0-1
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    price_action: str  # Descrição do movimento
    volume_action: str  # Descrição do volume
    recommendation: str  # O que fazer


class SmartMoneyDetector:
    """
    Detecta atividade institucional no mercado
    
    Conceitos:
    - Smart Money = Instituições, bancos, fundos (movem muito dinheiro)
    - Retail = Traders pequenos (nós)
    - Smart Money deixa "pegadas" no volume e price action
    """
    
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        
        # Thresholds
        self.absorption_threshold = 2.0  # Volume 2x acima média
        self.small_move_threshold = 0.3  # Movimento < 0.3% = pequeno
        self.spike_threshold = 0.5  # Spike > 0.5% em 1 candle
        self.reversal_threshold = 0.4  # Reversão > 0.4% após spike
        
        logger.info("SmartMoneyDetector inicializado")
    
    def analyze(self, lookback: int = 50) -> Optional[SmartMoneyAnalysis]:
        """
        Analisa padrões de Smart Money
        
        Args:
            lookback: Número de candles para análise
            
        Returns:
            SmartMoneyAnalysis com sinais detectados
        """
        try:
            # Coletar dados M15 (timeframe ideal para detectar manipulação)
            rates = mt5.copy_rates_from_pos(
                self.symbol, 
                mt5.TIMEFRAME_M15, 
                0, 
                lookback + 20  # +20 para médias
            )
            
            if rates is None or len(rates) < lookback:
                logger.warning("Dados insuficientes para Smart Money detection")
                return None
            
            # Calcular médias de volume
            volumes = np.array([r['tick_volume'] for r in rates])
            avg_volume = np.mean(volumes[-50:])  # Média 50 candles
            
            # Analisar últimos 10 candles para padrões
            recent_rates = rates[-10:]
            
            # 1. Detectar ABSORÇÃO
            absorption = self._detect_absorption(recent_rates, avg_volume)
            if absorption:
                return absorption
            
            # 2. Detectar STOP HUNTING
            stop_hunt = self._detect_stop_hunting(recent_rates, avg_volume)
            if stop_hunt:
                return stop_hunt
            
            # 3. Detectar DIVERGÊNCIA DE VOLUME
            divergence = self._detect_volume_divergence(rates[-20:])
            if divergence:
                return divergence
            
            # 4. Detectar DISTRIBUIÇÃO/ACUMULAÇÃO
            distribution = self._detect_distribution_accumulation(rates[-30:], avg_volume)
            if distribution:
                return distribution
            
            # Nenhum padrão detectado
            return SmartMoneyAnalysis(
                signal=SmartMoneySignal.NONE,
                confidence=0.0,
                direction="NEUTRAL",
                price_action="Normal",
                volume_action="Normal",
                recommendation="Operar normalmente"
            )
            
        except Exception as e:
            logger.error(f"Erro na detecção de Smart Money: {e}")
            return None
    
    def _detect_absorption(
        self, 
        rates: np.ndarray, 
        avg_volume: float
    ) -> Optional[SmartMoneyAnalysis]:
        """
        Detecta ABSORÇÃO
        
        Padrão:
        - Volume muito alto (2x+ média)
        - Mas preço move pouco (<0.3%)
        - Significa: Instituições absorvendo ordens (acumulando/distribuindo)
        
        Exemplo:
        - 1000 contratos comprados, preço sobe só $2 = absorção BEARISH (vendedores fortes)
        - 1000 contratos vendidos, preço cai só $2 = absorção BULLISH (compradores fortes)
        """
        for i in range(len(rates) - 1, max(0, len(rates) - 5), -1):
            candle = rates[i]
            volume = candle['tick_volume']
            
            # Volume alto?
            if volume < avg_volume * self.absorption_threshold:
                continue
            
            # Movimento pequeno?
            price_range = candle['high'] - candle['low']
            price_change_pct = (price_range / candle['close']) * 100
            
            if price_change_pct > self.small_move_threshold:
                continue
            
            # ABSORÇÃO DETECTADA!
            # Determinar direção pela cor do candle
            is_bullish_candle = candle['close'] > candle['open']
            
            if is_bullish_candle:
                # Candle verde + absorção = vendedores fortes (BEARISH)
                return SmartMoneyAnalysis(
                    signal=SmartMoneySignal.ABSORPTION,
                    confidence=0.75,
                    direction="BEARISH",
                    price_action=f"Volume alto ({volume:.0f}) mas preço subiu pouco ({price_change_pct:.2f}%)",
                    volume_action="Instituições vendendo (absorvendo compras)",
                    recommendation="⚠️ CUIDADO com LONGs - Smart Money vendendo"
                )
            else:
                # Candle vermelho + absorção = compradores fortes (BULLISH)
                return SmartMoneyAnalysis(
                    signal=SmartMoneySignal.ABSORPTION,
                    confidence=0.75,
                    direction="BULLISH",
                    price_action=f"Volume alto ({volume:.0f}) mas preço caiu pouco ({price_change_pct:.2f}%)",
                    volume_action="Instituições comprando (absorvendo vendas)",
                    recommendation="✅ FAVORÁVEL para LONGs - Smart Money comprando"
                )
        
        return None
    
    def _detect_stop_hunting(
        self, 
        rates: np.ndarray, 
        avg_volume: float
    ) -> Optional[SmartMoneyAnalysis]:
        """
        Detecta STOP HUNTING
        
        Padrão:
        1. Spike rápido (0.5%+) com volume alto
        2. Reversão imediata (0.4%+) no candle seguinte
        3. Significa: Instituições ativaram stops para pegar liquidez
        
        Exemplo:
        - Ouro sobe $10 rápido → stops de shorts ativados
        - Depois cai $8 → era manipulação para comprar mais barato
        """
        for i in range(len(rates) - 2, max(0, len(rates) - 5), -1):
            candle1 = rates[i]
            candle2 = rates[i + 1]
            
            # Spike forte no candle 1?
            spike_pct = abs(candle1['close'] - candle1['open']) / candle1['open'] * 100
            
            if spike_pct < self.spike_threshold:
                continue
            
            # Volume alto?
            if candle1['tick_volume'] < avg_volume * 1.5:
                continue
            
            # Reversão forte no candle 2?
            reversal_pct = abs(candle2['close'] - candle1['close']) / candle1['close'] * 100
            
            if reversal_pct < self.reversal_threshold:
                continue
            
            # Direção do spike vs direção da reversão
            spike_up = candle1['close'] > candle1['open']
            reversed_down = candle2['close'] < candle1['close']
            
            if spike_up and reversed_down:
                # Spike UP → Reversão DOWN = Stop hunt de shorts, vai cair
                return SmartMoneyAnalysis(
                    signal=SmartMoneySignal.STOP_HUNT,
                    confidence=0.80,
                    direction="BEARISH",
                    price_action=f"Spike UP {spike_pct:.2f}% seguido de reversão DOWN {reversal_pct:.2f}%",
                    volume_action="Stop hunting: Ativaram stops de shorts para vender",
                    recommendation="🎯 OPORTUNIDADE SHORT - Falso breakout para cima"
                )
            
            elif not spike_up and not reversed_down:
                # Spike DOWN → Reversão UP = Stop hunt de longs, vai subir
                return SmartMoneyAnalysis(
                    signal=SmartMoneySignal.STOP_HUNT,
                    confidence=0.80,
                    direction="BULLISH",
                    price_action=f"Spike DOWN {spike_pct:.2f}% seguido de reversão UP {reversal_pct:.2f}%",
                    volume_action="Stop hunting: Ativaram stops de longs para comprar",
                    recommendation="🎯 OPORTUNIDADE LONG - Falso breakout para baixo"
                )
        
        return None
    
    def _detect_volume_divergence(
        self, 
        rates: np.ndarray
    ) -> Optional[SmartMoneyAnalysis]:
        """
        Detecta DIVERGÊNCIA DE VOLUME
        
        Padrão:
        - Preço fazendo topos mais altos
        - Mas volume diminuindo
        - Significa: Movimento fraco, só retail comprando, instituições saindo
        
        Inverso:
        - Preço fazendo fundos mais baixos
        - Mas volume diminuindo
        - Significa: Movimento fraco, só retail vendendo, instituições comprando
        """
        if len(rates) < 10:
            return None
        
        # Dividir em 2 metades
        first_half = rates[:len(rates)//2]
        second_half = rates[len(rates)//2:]
        
        # Preço: comparar médias
        avg_price_first = np.mean([r['close'] for r in first_half])
        avg_price_second = np.mean([r['close'] for r in second_half])
        
        # Volume: comparar médias
        avg_vol_first = np.mean([r['tick_volume'] for r in first_half])
        avg_vol_second = np.mean([r['tick_volume'] for r in second_half])
        
        price_change_pct = ((avg_price_second - avg_price_first) / avg_price_first) * 100
        volume_change_pct = ((avg_vol_second - avg_vol_first) / avg_vol_first) * 100
        
        # Divergência BEARISH: Preço subindo + Volume caindo
        if price_change_pct > 0.2 and volume_change_pct < -15:
            return SmartMoneyAnalysis(
                signal=SmartMoneySignal.VOLUME_DIVERGENCE,
                confidence=0.65,
                direction="BEARISH",
                price_action=f"Preço subindo {price_change_pct:.2f}%",
                volume_action=f"Volume caindo {volume_change_pct:.1f}% = Movimento fraco",
                recommendation="⚠️ CUIDADO - Retail comprando, Smart Money saindo"
            )
        
        # Divergência BULLISH: Preço caindo + Volume caindo
        elif price_change_pct < -0.2 and volume_change_pct < -15:
            return SmartMoneyAnalysis(
                signal=SmartMoneySignal.VOLUME_DIVERGENCE,
                confidence=0.65,
                direction="BULLISH",
                price_action=f"Preço caindo {price_change_pct:.2f}%",
                volume_action=f"Volume caindo {volume_change_pct:.1f}% = Movimento fraco",
                recommendation="✅ OPORTUNIDADE - Retail vendendo, Smart Money comprando"
            )
        
        return None
    
    def _detect_distribution_accumulation(
        self, 
        rates: np.ndarray,
        avg_volume: float
    ) -> Optional[SmartMoneyAnalysis]:
        """
        Detecta DISTRIBUIÇÃO (topo) ou ACUMULAÇÃO (fundo)
        
        DISTRIBUIÇÃO (BEARISH):
        - Preço em região de máximas
        - Volume aumentando
        - Significa: Instituições distribuindo (vendendo) para retail
        
        ACUMULAÇÃO (BULLISH):
        - Preço em região de mínimas
        - Volume aumentando
        - Significa: Instituições acumulando (comprando) do retail
        """
        if len(rates) < 20:
            return None
        
        # Identificar máximas e mínimas dos últimos 30 candles
        prices = np.array([r['close'] for r in rates])
        max_price = np.max(prices)
        min_price = np.min(prices)
        current_price = prices[-1]
        
        # Volume recente vs média
        recent_volume = np.mean([r['tick_volume'] for r in rates[-10:]])
        volume_ratio = recent_volume / avg_volume
        
        # Preço está perto do topo (95%+)?
        price_position = (current_price - min_price) / (max_price - min_price)
        
        if price_position > 0.95 and volume_ratio > 1.3:
            # DISTRIBUIÇÃO
            return SmartMoneyAnalysis(
                signal=SmartMoneySignal.DISTRIBUTION,
                confidence=0.70,
                direction="BEARISH",
                price_action=f"Preço em topo ({price_position*100:.0f}% do range)",
                volume_action=f"Volume aumentando ({volume_ratio:.1f}x média)",
                recommendation="⚠️ DISTRIBUIÇÃO - Instituições vendendo para retail"
            )
        
        elif price_position < 0.05 and volume_ratio > 1.3:
            # ACUMULAÇÃO
            return SmartMoneyAnalysis(
                signal=SmartMoneySignal.ACCUMULATION,
                confidence=0.70,
                direction="BULLISH",
                price_action=f"Preço em fundo ({price_position*100:.0f}% do range)",
                volume_action=f"Volume aumentando ({volume_ratio:.1f}x média)",
                recommendation="✅ ACUMULAÇÃO - Instituições comprando do retail"
            )
        
        return None
    
    def should_avoid_trade(self, analysis: Optional[SmartMoneyAnalysis], order_type: str) -> bool:
        """
        Verifica se deve evitar trade baseado em Smart Money
        
        Args:
            analysis: SmartMoneyAnalysis
            order_type: "BUY" ou "SELL"
            
        Returns:
            True se deve evitar o trade
        """
        if not analysis or analysis.signal == SmartMoneySignal.NONE:
            return False
        
        # Evitar LONG se Smart Money é BEARISH com alta confiança
        if order_type == "BUY" and analysis.direction == "BEARISH" and analysis.confidence > 0.7:
            logger.warning(f"⚠️ Evitando LONG: {analysis.signal.value} detectado")
            return True
        
        # Evitar SHORT se Smart Money é BULLISH com alta confiança
        if order_type == "SELL" and analysis.direction == "BULLISH" and analysis.confidence > 0.7:
            logger.warning(f"⚠️ Evitando SHORT: {analysis.signal.value} detectado")
            return True
        
        return False


# Exemplo de uso
if __name__ == "__main__":
    # Conectar MT5
    if not mt5.initialize():
        print("Erro ao inicializar MT5")
        exit()
    
    detector = SmartMoneyDetector()
    analysis = detector.analyze()
    
    if analysis:
        print(f"\n{'='*70}")
        print(f"🐋 SMART MONEY DETECTION")
        print(f"{'='*70}")
        print(f"\n📊 Sinal: {analysis.signal.value.upper()}")
        print(f"   Confiança: {analysis.confidence*100:.0f}%")
        print(f"   Direção: {analysis.direction}")
        
        print(f"\n📈 Price Action:")
        print(f"   {analysis.price_action}")
        
        print(f"\n📊 Volume:")
        print(f"   {analysis.volume_action}")
        
        print(f"\n💡 Recomendação:")
        print(f"   {analysis.recommendation}")
        print(f"\n{'='*70}\n")
        
        # Testar decisões
        print(f"❌ Evitar LONG? {detector.should_avoid_trade(analysis, 'BUY')}")
        print(f"❌ Evitar SHORT? {detector.should_avoid_trade(analysis, 'SELL')}")
    else:
        print("❌ Análise não disponível")
    
    mt5.shutdown()
