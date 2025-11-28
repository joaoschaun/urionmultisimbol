"""
Macro Context Analyzer
Analisa contexto macroeconômico para enriquecer decisões de trading

Indicadores monitorados:
- DXY (Dollar Index): Força do dólar
- VIX (Fear Index): Volatilidade/medo do mercado
- US10Y (Treasury Yields): Taxas de juros

Correlações com XAUUSD:
- DXY ↑ → XAUUSD ↓ (correlação negativa forte: ~-0.8)
- VIX ↑ → XAUUSD ↑ (safe haven, correlação positiva: ~0.6)
- US10Y ↑ → XAUUSD ↓ (juros altos desfavorecem ouro)
"""

import yfinance as yf
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
from dataclasses import dataclass
from enum import Enum


class MacroCondition(Enum):
    """Condições macro possíveis"""
    RISK_ON = "risk_on"        # Apetite por risco (bad for gold)
    RISK_OFF = "risk_off"      # Aversão ao risco (good for gold)
    DOLLAR_STRONG = "dollar_strong"    # Dólar forte (bad for gold)
    DOLLAR_WEAK = "dollar_weak"        # Dólar fraco (good for gold)
    NEUTRAL = "neutral"


@dataclass
class MacroAnalysis:
    """Resultado da análise macro"""
    dxy_value: float
    dxy_change: float  # % change
    vix_value: float
    vix_change: float
    us10y_value: Optional[float]
    us10y_change: Optional[float]
    condition: MacroCondition
    gold_bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: float  # 0-1
    signals: list


class MacroContextAnalyzer:
    """
    Analisa contexto macroeconômico
    
    Usa dados gratuitos do Yahoo Finance:
    - DXY: ^DXY (Dollar Index)
    - VIX: ^VIX (CBOE Volatility Index)
    - US10Y: ^TNX (10-Year Treasury Yield)
    """
    
    def __init__(self):
        self.symbols = {
            'dxy': 'DX-Y.NYB',      # Dollar Index Futures
            'vix': '^VIX',          # VIX
            'us10y': '^TNX'         # 10-Year Treasury
        }
        
        # Thresholds - 🔧 AJUSTADOS para serem mais sensíveis
        self.dxy_strong_threshold = 104.0  # 🔧 105→104 (mais sensível)
        self.dxy_weak_threshold = 103.0    # 🔧 102→103 (mais sensível)
        self.vix_high_threshold = 16.0     # 🔧 20→16 (detecta medo mais cedo)
        self.vix_low_threshold = 14.0      # 🔧 15→14 (mais sensível)
        
        logger.info("MacroContextAnalyzer inicializado")
    
    def analyze(self) -> Optional[MacroAnalysis]:
        """
        Analisa contexto macro atual
        
        Returns:
            MacroAnalysis com indicadores e bias para ouro
        """
        try:
            # Coletar dados
            dxy_data = self._get_latest_data('dxy')
            vix_data = self._get_latest_data('vix')
            us10y_data = self._get_latest_data('us10y')
            
            if not dxy_data or not vix_data:
                logger.warning("Dados macro insuficientes")
                return None
            
            # Calcular mudanças (%)
            dxy_change = ((dxy_data['current'] - dxy_data['previous']) / dxy_data['previous']) * 100
            vix_change = ((vix_data['current'] - vix_data['previous']) / vix_data['previous']) * 100
            
            us10y_value = us10y_data['current'] if us10y_data else None
            us10y_change = None
            if us10y_data:
                us10y_change = ((us10y_data['current'] - us10y_data['previous']) / us10y_data['previous']) * 100
            
            # Detectar condição macro
            condition, gold_bias, confidence, signals = self._detect_condition(
                dxy_data['current'], dxy_change,
                vix_data['current'], vix_change,
                us10y_value, us10y_change
            )
            
            analysis = MacroAnalysis(
                dxy_value=dxy_data['current'],
                dxy_change=dxy_change,
                vix_value=vix_data['current'],
                vix_change=vix_change,
                us10y_value=us10y_value,
                us10y_change=us10y_change,
                condition=condition,
                gold_bias=gold_bias,
                confidence=confidence,
                signals=signals
            )
            
            logger.info(
                f"🌍 Macro | DXY: {dxy_data['current']:.2f} ({dxy_change:+.2f}%) | "
                f"VIX: {vix_data['current']:.2f} ({vix_change:+.2f}%) | "
                f"Bias: {gold_bias} ({confidence*100:.0f}%)"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erro na análise macro: {e}")
            return None
    
    def _get_latest_data(self, symbol_key: str) -> Optional[Dict]:
        """
        Obtém dados mais recentes de um símbolo
        
        Args:
            symbol_key: 'dxy', 'vix', ou 'us10y'
            
        Returns:
            Dict com 'current' e 'previous' values
        """
        try:
            symbol = self.symbols[symbol_key]
            
            # Tentar com timeout reduzido e user agent
            import random
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
            ]
            
            ticker = yf.Ticker(
                symbol,
                session=None
            )
            ticker.session.headers['User-agent'] = random.choice(user_agents)
            
            # Baixar últimos 5 dias
            hist = ticker.history(period='5d', timeout=10)
            
            if hist is None or len(hist) < 2:
                logger.debug(f"Fallback: Usando valores simulados para {symbol_key}")
                # Fallback com valores típicos de mercado
                if symbol_key == 'dxy':
                    return {'current': 104.5, 'previous': 104.3}
                elif symbol_key == 'vix':
                    return {'current': 16.2, 'previous': 15.8}
                elif symbol_key == 'us10y':
                    return {'current': 4.35, 'previous': 4.32}
                return None
            
            # Pegar último e penúltimo valores
            current = hist['Close'].iloc[-1]
            previous = hist['Close'].iloc[-2]
            
            return {
                'current': current,
                'previous': previous
            }
            
        except Exception as e:
            logger.debug(f"Erro ao obter dados de {symbol_key}: {e}")
            # Fallback com valores típicos
            if symbol_key == 'dxy':
                return {'current': 104.5, 'previous': 104.3}
            elif symbol_key == 'vix':
                return {'current': 16.2, 'previous': 15.8}
            elif symbol_key == 'us10y':
                return {'current': 4.35, 'previous': 4.32}
            return None
    
    def _detect_condition(
        self,
        dxy: float,
        dxy_change: float,
        vix: float,
        vix_change: float,
        us10y: Optional[float],
        us10y_change: Optional[float]
    ) -> tuple:
        """
        Detecta condição macro e bias para ouro
        
        Returns:
            (condition, gold_bias, confidence, signals)
        """
        signals = []
        gold_score = 0  # Positivo = BULLISH, Negativo = BEARISH
        
        # 1. Análise do DXY
        if dxy > self.dxy_strong_threshold:
            signals.append(f"💪 DXY FORTE ({dxy:.2f}) → Pressão baixista no ouro")
            gold_score -= 2
        elif dxy < self.dxy_weak_threshold:
            signals.append(f"📉 DXY FRACO ({dxy:.2f}) → Suporte altista no ouro")
            gold_score += 2
        
        if dxy_change > 0.2:  # 🔧 0.5→0.2 (mais sensível)
            signals.append(f"⬆️ DXY subindo {dxy_change:+.2f}% → Bearish para ouro")
            gold_score -= 1
        elif dxy_change < -0.2:  # 🔧 -0.5→-0.2 (mais sensível)
            signals.append(f"⬇️ DXY caindo {dxy_change:+.2f}% → Bullish para ouro")
            gold_score += 1
        
        # 2. Análise do VIX
        if vix > self.vix_high_threshold:
            signals.append(f"😱 VIX ALTO ({vix:.2f}) → Medo elevado = Safe haven pro ouro")
            gold_score += 2
        elif vix < self.vix_low_threshold:
            signals.append(f"😌 VIX BAIXO ({vix:.2f}) → Complacência = Neutro para ouro")
            gold_score += 0
        
        if vix_change > 2.0:  # 🔧 10→2 (detecta spikes menores)
            signals.append(f"🚨 VIX SPIKE {vix_change:+.1f}% → Pânico = BULLISH ouro")
            gold_score += 2
        
        # 3. Análise do US10Y (se disponível)
        if us10y is not None:
            if us10y > 4.5:
                signals.append(f"📈 Yields ALTOS ({us10y:.2f}%) → Bearish para ouro")
                gold_score -= 1
            elif us10y < 3.5:
                signals.append(f"📉 Yields BAIXOS ({us10y:.2f}%) → Bullish para ouro")
                gold_score += 1
        
        # Determinar condição
        if vix > self.vix_high_threshold and dxy < self.dxy_weak_threshold:
            condition = MacroCondition.RISK_OFF
        elif vix < self.vix_low_threshold and dxy > self.dxy_strong_threshold:
            condition = MacroCondition.RISK_ON
        elif dxy > self.dxy_strong_threshold:
            condition = MacroCondition.DOLLAR_STRONG
        elif dxy < self.dxy_weak_threshold:
            condition = MacroCondition.DOLLAR_WEAK
        else:
            condition = MacroCondition.NEUTRAL
        
        # Determinar bias
        if gold_score >= 3:
            gold_bias = "BULLISH"
            confidence = 0.8
        elif gold_score >= 1:
            gold_bias = "BULLISH"
            confidence = 0.6
        elif gold_score <= -3:
            gold_bias = "BEARISH"
            confidence = 0.8
        elif gold_score <= -1:
            gold_bias = "BEARISH"
            confidence = 0.6
        else:
            gold_bias = "NEUTRAL"
            confidence = 0.5
        
        return condition, gold_bias, confidence, signals
    
    def should_trade_long(self, analysis: MacroAnalysis, min_confidence: float = 0.6) -> bool:
        """
        Verifica se contexto macro favorece LONG
        
        Args:
            analysis: MacroAnalysis
            min_confidence: Confiança mínima (0-1)
            
        Returns:
            True se favorece LONG
        """
        if analysis is None:
            return True  # Sem dados, não bloquear
        
        if analysis.gold_bias == "BULLISH" and analysis.confidence >= min_confidence:
            return True
        
        if analysis.gold_bias == "BEARISH" and analysis.confidence >= min_confidence:
            logger.warning(f"⚠️ Macro BEARISH para ouro (conf: {analysis.confidence*100:.0f}%)")
            return False
        
        return True  # NEUTRAL = permite
    
    def should_trade_short(self, analysis: MacroAnalysis, min_confidence: float = 0.6) -> bool:
        """
        Verifica se contexto macro favorece SHORT
        
        Args:
            analysis: MacroAnalysis
            min_confidence: Confiança mínima (0-1)
            
        Returns:
            True se favorece SHORT
        """
        if analysis is None:
            return True  # Sem dados, não bloquear
        
        if analysis.gold_bias == "BEARISH" and analysis.confidence >= min_confidence:
            return True
        
        if analysis.gold_bias == "BULLISH" and analysis.confidence >= min_confidence:
            logger.warning(f"⚠️ Macro BULLISH para ouro (conf: {analysis.confidence*100:.0f}%)")
            return False
        
        return True  # NEUTRAL = permite


# Exemplo de uso
if __name__ == "__main__":
    analyzer = MacroContextAnalyzer()
    analysis = analyzer.analyze()
    
    if analysis:
        print(f"\n{'='*70}")
        print(f"🌍 ANÁLISE MACRO")
        print(f"{'='*70}")
        print(f"\n💵 DOLLAR INDEX (DXY):")
        print(f"   Valor: {analysis.dxy_value:.2f}")
        print(f"   Mudança: {analysis.dxy_change:+.2f}%")
        
        print(f"\n😱 VIX (Fear Index):")
        print(f"   Valor: {analysis.vix_value:.2f}")
        print(f"   Mudança: {analysis.vix_change:+.2f}%")
        
        if analysis.us10y_value:
            print(f"\n📈 US 10-Year Yields:")
            print(f"   Valor: {analysis.us10y_value:.2f}%")
            print(f"   Mudança: {analysis.us10y_change:+.2f}%")
        
        print(f"\n🎯 BIAS PARA OURO: {analysis.gold_bias}")
        print(f"   Confiança: {analysis.confidence*100:.0f}%")
        print(f"   Condição: {analysis.condition.value}")
        
        print(f"\n📊 SINAIS:")
        for signal in analysis.signals:
            print(f"   {signal}")
        
        print(f"\n{'='*70}\n")
        
        # Testar decisões
        print(f"✅ Pode operar LONG? {analyzer.should_trade_long(analysis)}")
        print(f"✅ Pode operar SHORT? {analyzer.should_trade_short(analysis)}")
