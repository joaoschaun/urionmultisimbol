"""
Market Condition Analyzer - Identifica condições de mercado para seleção inteligente de estratégias

Condições detectadas:
- TRENDING (tendência forte) → trend_following, breakout
- RANGING (lateralização) → range_trading, scalping  
- VOLATILE (alta volatilidade) → breakout, news_trading
- QUIET (baixo volume/volatilidade) → scalping
- NEWS (notícias importantes) → news_trading, mean_reversion
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
import MetaTrader5 as mt5
from loguru import logger

# 🌍 NOVO: Importar analisador macro
try:
    from src.analysis.macro_context_analyzer import MacroContextAnalyzer, MacroAnalysis
    MACRO_AVAILABLE = True
except ImportError:
    MACRO_AVAILABLE = False
    logger.warning("MacroContextAnalyzer não disponível")


class MarketCondition(Enum):
    """Condições de mercado possíveis"""
    TRENDING_UP = "trending_up"       # Tendência de alta forte
    TRENDING_DOWN = "trending_down"   # Tendência de baixa forte
    RANGING = "ranging"               # Lateralização
    VOLATILE = "volatile"             # Alta volatilidade
    QUIET = "quiet"                   # Baixa volatilidade/volume
    NEWS_IMPACT = "news_impact"       # Impacto de notícias


@dataclass
class MarketAnalysis:
    """Resultado da análise de mercado"""
    condition: MarketCondition
    strength: float  # 0.0 a 1.0 - força da condição
    volatility: float  # ATR normalizado
    volume: float  # Volume relativo
    trend_strength: float  # -1.0 a 1.0 (negativo = bearish, positivo = bullish)
    recommended_strategies: List[str]
    avoid_strategies: List[str]
    confidence: float  # Confiança na análise
    # 🌍 NOVO: Contexto macro
    macro_bias: Optional[str] = None  # "BULLISH", "BEARISH", "NEUTRAL"
    macro_confidence: Optional[float] = None  # 0-1
    macro_signals: Optional[List[str]] = None  # Sinais macro detectados


class MarketConditionAnalyzer:
    """Analisa condições de mercado e recomenda estratégias"""
    
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        
        # 🌍 NOVO: Inicializar analisador macro
        self.macro_analyzer = MacroContextAnalyzer() if MACRO_AVAILABLE else None
        
        # Mapeamento: Condição → (Estratégias Recomendadas, Estratégias a Evitar)
        self.strategy_map = {
            MarketCondition.TRENDING_UP: (
                ['trend_following', 'breakout'],
                ['range_trading', 'mean_reversion']
            ),
            MarketCondition.TRENDING_DOWN: (
                ['trend_following', 'breakout'],
                ['range_trading', 'mean_reversion']
            ),
            MarketCondition.RANGING: (
                ['range_trading', 'scalping', 'mean_reversion'],
                ['trend_following', 'breakout']
            ),
            MarketCondition.VOLATILE: (
                ['breakout', 'news_trading', 'scalping'],
                ['mean_reversion']
            ),
            MarketCondition.QUIET: (
                ['scalping', 'range_trading'],
                ['breakout', 'news_trading']
            ),
            MarketCondition.NEWS_IMPACT: (
                ['news_trading', 'breakout'],
                ['scalping', 'range_trading']
            ),
        }
    
    def analyze(self) -> Optional[MarketAnalysis]:
        """
        Analisa condições atuais do mercado com validação multi-timeframe
        
        Returns:
            MarketAnalysis com condições detectadas e recomendações
        """
        try:
            # 1. Coletar dados de múltiplos timeframes para confirmação
            rates_h1 = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 100)
            rates_m30 = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M30, 0, 100)
            rates_m15 = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M15, 0, 100)
            
            if rates_h1 is None or rates_m30 is None or rates_m15 is None:
                logger.warning("Dados insuficientes para análise de mercado")
                return None
            
            if len(rates_h1) < 50 or len(rates_m30) < 50 or len(rates_m15) < 50:
                logger.warning("Histórico insuficiente para análise multi-timeframe")
                return None
            
            # 2. Calcular indicadores
            volatility = self._calculate_volatility(rates_h1)
            volume_ratio = self._calculate_volume_ratio(rates_m15)
            trend_strength = self._calculate_trend_strength(rates_h1)
            range_factor = self._calculate_range_factor(rates_h1)
            
            # 3. 🔥 NOVO: Validação cruzada de tendência em múltiplos timeframes
            trend_h1 = self._calculate_trend_strength(rates_h1)
            trend_m30 = self._calculate_trend_strength(rates_m30)
            trend_m15 = self._calculate_trend_strength(rates_m15)
            
            # Verificar alinhamento de tendências (confirma ou reduz confiança)
            trend_alignment = self._calculate_trend_alignment(trend_h1, trend_m30, trend_m15)
            
            # 4. Detectar condição primária
            condition, strength, base_confidence = self._detect_condition(
                volatility, volume_ratio, trend_strength, range_factor
            )
            
            # 5. 🔥 NOVO: Ajustar confiança baseado no alinhamento
            adjusted_confidence = base_confidence * trend_alignment
            
            # 6. 🌍 NOVO: Integrar análise macro
            macro_analysis = None
            macro_bias = None
            macro_confidence = None
            macro_signals = None
            
            if self.macro_analyzer:
                try:
                    macro_analysis = self.macro_analyzer.analyze()
                    if macro_analysis:
                        macro_bias = macro_analysis.gold_bias
                        macro_confidence = macro_analysis.confidence
                        macro_signals = macro_analysis.signals
                        
                        # Ajustar confiança baseado em conflito macro
                        if macro_bias == "BEARISH" and trend_strength > 0.3:
                            # Macro bearish mas mercado bullish técnico
                            adjusted_confidence *= 0.8
                            logger.warning(f"⚠️ Conflito: Macro BEARISH mas técnica BULLISH")
                        elif macro_bias == "BULLISH" and trend_strength < -0.3:
                            # Macro bullish mas mercado bearish técnico
                            adjusted_confidence *= 0.8
                            logger.warning(f"⚠️ Conflito: Macro BULLISH mas técnica BEARISH")
                        
                except Exception as e:
                    logger.debug(f"Erro na análise macro: {e}")
            
            # 7. Obter recomendações
            recommended, avoid = self.strategy_map.get(condition, ([], []))
            
            analysis = MarketAnalysis(
                condition=condition,
                strength=strength,
                volatility=volatility,
                volume=volume_ratio,
                trend_strength=trend_strength,
                recommended_strategies=list(recommended),
                avoid_strategies=list(avoid),
                confidence=adjusted_confidence,  # ✅ Confiança ajustada
                macro_bias=macro_bias,  # 🌍 NOVO
                macro_confidence=macro_confidence,  # 🌍 NOVO
                macro_signals=macro_signals  # 🌍 NOVO
            )
            
            # Log com info macro
            macro_info = f" | Macro: {macro_bias} ({macro_confidence*100:.0f}%)" if macro_bias else ""
            logger.info(f"📊 Condição: {condition.value} | Força: {strength:.2f} | "
                       f"Confiança: {adjusted_confidence*100:.0f}%{macro_info} | "
                       f"Rec: {recommended} | Evitar: {avoid}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erro na análise de mercado: {e}")
            return None
    
    def _calculate_trend_alignment(self, trend_h1: float, trend_m30: float, trend_m15: float) -> float:
        """
        🔥 NOVO: Calcula alinhamento de tendências entre timeframes
        
        Se todos apontam na mesma direção → confiança 100%
        Se divergem → confiança reduzida (70-90%)
        
        Args:
            trend_h1: Tendência em H1
            trend_m30: Tendência em M30
            trend_m15: Tendência em M15
            
        Returns:
            float 0.7-1.0 (multiplicador de confiança)
        """
        trends = [trend_h1, trend_m30, trend_m15]
        
        # Verificar se todos têm o mesmo sinal (todos positivos ou todos negativos)
        all_bullish = all(t > 0.1 for t in trends)
        all_bearish = all(t < -0.1 for t in trends)
        
        if all_bullish or all_bearish:
            # ✅ Alinhamento perfeito = 100% confiança
            return 1.0
        
        # Contar quantos concordam
        bullish_count = sum(1 for t in trends if t > 0.1)
        bearish_count = sum(1 for t in trends if t < -0.1)
        neutral_count = sum(1 for t in trends if abs(t) <= 0.1)
        
        # Se 2 de 3 concordam = 90% confiança
        if bullish_count == 2 or bearish_count == 2:
            return 0.90
        
        # Se há divergência (1 bull, 1 bear, 1 neutral) = 80% confiança
        if neutral_count >= 1:
            return 0.85
        
        # Divergência forte (1 bull, 2 bear ou vice-versa) = 70% confiança
        return 0.70
    
    def _calculate_volatility(self, rates) -> float:
        """
        Calcula volatilidade normalizada (ATR)
        
        Returns:
            float 0.0-1.0 (0=baixa, 1=alta)
        """
        try:
            # ATR simplificado: média do range H-L
            ranges = rates['high'][-20:] - rates['low'][-20:]
            atr = ranges.mean()
            
            # Normalizar pelo preço atual
            current_price = rates['close'][-1]
            normalized = (atr / current_price) * 1000  # Para XAUUSD
            
            # Mapear para 0-1 (ATR típico: 5-30 para XAUUSD)
            return min(max(normalized / 30, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"Erro ao calcular volatilidade: {e}")
            return 0.5
    
    def _calculate_volume_ratio(self, rates) -> float:
        """
        Calcula volume relativo (volume atual vs média)
        
        Returns:
            float 0.0-2.0+ (1.0=normal, >1.5=alto, <0.5=baixo)
        """
        try:
            volumes = rates['tick_volume']
            current_vol = volumes[-1]
            avg_vol = volumes[-50:].mean()
            
            if avg_vol == 0:
                return 1.0
            
            ratio = current_vol / avg_vol
            return min(ratio, 2.0)
            
        except Exception as e:
            logger.error(f"Erro ao calcular volume: {e}")
            return 1.0
    
    def _calculate_trend_strength(self, rates) -> float:
        """
        Calcula força da tendência usando médias móveis
        
        Returns:
            float -1.0 a 1.0 (negativo=bearish, positivo=bullish, 0=sem tendência)
        """
        try:
            closes = rates['close']
            
            # Médias móveis
            ma20 = closes[-20:].mean()
            ma50 = closes[-50:].mean()
            current = closes[-1]
            
            # Distância das médias (normalizado)
            dist_20 = (current - ma20) / ma20
            dist_50 = (current - ma50) / ma50
            
            # Alinhamento das médias
            ma_alignment = 1.0 if ma20 > ma50 else -1.0
            
            # Força da tendência
            strength = ((dist_20 * 0.6) + (dist_50 * 0.4)) * ma_alignment * 100
            
            return max(min(strength, 1.0), -1.0)
            
        except Exception as e:
            logger.error(f"Erro ao calcular tendência: {e}")
            return 0.0
    
    def _calculate_range_factor(self, rates) -> float:
        """
        Calcula se mercado está lateralizado
        
        Returns:
            float 0.0-1.0 (0=trending, 1=ranging)
        """
        try:
            closes = rates['close'][-50:]
            
            # Desvio padrão vs range total
            std_dev = closes.std()
            price_range = closes.max() - closes.min()
            
            if price_range == 0:
                return 1.0
            
            # Quanto menor o desvio relativo ao range, mais lateral
            ratio = std_dev / price_range
            
            # Inverter: quanto menor ratio, mais ranging
            return 1.0 - min(ratio * 2, 1.0)
            
        except Exception as e:
            logger.error(f"Erro ao calcular range factor: {e}")
            return 0.5
    
    def _detect_condition(self, volatility: float, volume: float, 
                         trend_strength: float, range_factor: float) -> tuple:
        """
        Detecta condição primária de mercado com thresholds calibrados
        
        Returns:
            (MarketCondition, strength, confidence)
        """
        scores = {}
        
        # 1. Trending Up (🔧 AJUSTADO: threshold 0.25→0.3 para mais seletivo)
        if trend_strength > 0.3 and range_factor < 0.35:
            scores[MarketCondition.TRENDING_UP] = trend_strength * (1 - range_factor)
        
        # 2. Trending Down (🔧 AJUSTADO: threshold -0.25→-0.3)
        if trend_strength < -0.3 and range_factor < 0.35:
            scores[MarketCondition.TRENDING_DOWN] = abs(trend_strength) * (1 - range_factor)
        
        # 3. Ranging (🔧 AJUSTADO: range_factor 0.5→0.6 para detectar apenas ranges claros)
        if range_factor > 0.6 and abs(trend_strength) < 0.25:
            scores[MarketCondition.RANGING] = range_factor * (1 - abs(trend_strength))
        
        # 4. Volatile (🔧 AJUSTADO: volatility threshold 0.6→0.7 mais restritivo)
        if volatility > 0.7:
            scores[MarketCondition.VOLATILE] = volatility
        
        # 5. Quiet (🔧 AJUSTADO: volume threshold 0.5→0.7 para detectar melhor)
        if volatility < 0.3 and volume < 0.7:
            scores[MarketCondition.QUIET] = (1 - volatility) * (1 - volume)
        
        # 6. News Impact (🔧 AJUSTADO: volume 1.5→1.3 para detectar mais cedo)
        if volatility > 0.6 and volume > 1.3:
            scores[MarketCondition.NEWS_IMPACT] = (volatility + (volume - 1)) / 2
        
        # Selecionar condição com maior score
        if not scores:
            # Default: ranging se não detectou nada
            return MarketCondition.RANGING, 0.5, 0.5
        
        condition = max(scores, key=scores.get)
        strength = scores[condition]
        
        # Confiança baseada na diferença entre 1º e 2º lugar
        sorted_scores = sorted(scores.values(), reverse=True)
        confidence = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0)
        confidence = min(confidence + 0.5, 1.0)  # Normalizar
        
        return condition, strength, confidence
    
    def get_strategy_priority(self, analysis: Optional[MarketAnalysis]) -> Dict[str, float]:
        """
        Retorna prioridade de cada estratégia (0.0-1.0)
        
        Args:
            analysis: Resultado da análise de mercado
            
        Returns:
            Dict com strategy_name → priority (1.0=máxima, 0.0=desabilitar)
        """
        if analysis is None:
            # Sem análise, todas iguais
            return {
                'trend_following': 0.7,
                'range_trading': 0.7,
                'scalping': 0.7,
                'mean_reversion': 0.7,
                'breakout': 0.7,
                'news_trading': 0.7,
            }
        
        priorities = {}
        
        # Recomendadas: prioridade baseada em strength e confidence
        for strategy in analysis.recommended_strategies:
            priorities[strategy] = min(analysis.strength * analysis.confidence, 1.0)
        
        # Evitar: prioridade muito baixa (mas não zero, para emergências)
        for strategy in analysis.avoid_strategies:
            priorities[strategy] = 0.2
        
        # Estratégias não mencionadas: prioridade média
        all_strategies = ['trend_following', 'range_trading', 'scalping', 
                         'mean_reversion', 'breakout', 'news_trading']
        for strategy in all_strategies:
            if strategy not in priorities:
                priorities[strategy] = 0.5
        
        return priorities
    
    def is_strategy_allowed(self, strategy_name: str, analysis: Optional[MarketAnalysis], strict_mode: bool = True) -> bool:
        """
        🚫 BLOQUEIO INTELIGENTE: Decide se estratégia pode operar
        
        Args:
            strategy_name: Nome da estratégia
            analysis: Análise de mercado atual
            strict_mode: Se True, bloqueia rigorosamente. Se False, apenas adverte
            
        Returns:
            True se estratégia pode operar, False se bloqueada
        """
        if analysis is None:
            return True  # Sem análise, permite tudo
        
        # 🔥 NOVO: Modo suave quando confiança < 70%
        soft_mode = analysis.confidence < 0.70
        
        if soft_mode:
            logger.info(
                f"[{strategy_name}] 🟡 MODO SUAVE | "
                f"Confiança da análise: {analysis.confidence*100:.0f}% | "
                f"Bloqueio relaxado"
            )
            # Em modo suave, permitir todas estratégias com aviso
            if strategy_name in analysis.avoid_strategies:
                logger.warning(
                    f"[{strategy_name}] ⚠️ CUIDADO | "
                    f"Não recomendada para {analysis.condition.value} "
                    f"(mas permitida devido à baixa confiança)"
                )
            return True  # Permite tudo em modo suave
        
        # Modo strict: BLOQUEIA estratégias em avoid_strategies
        if strict_mode:
            if strategy_name in analysis.avoid_strategies:
                logger.warning(
                    f"[{strategy_name}] 🚫 BLOQUEADA pelo MarketAnalyzer | "
                    f"Condição: {analysis.condition.value} ({analysis.strength*100:.1f}% força) | "
                    f"Confiança: {analysis.confidence*100:.0f}%"
                )
                return False
        
        # Verificar prioridade mínima (threshold)
        priorities = self.get_strategy_priority(analysis)
        priority = priorities.get(strategy_name, 0.5)
        
        min_threshold = 0.3  # Threshold padrão: 30%
        
        if priority < min_threshold:
            logger.warning(
                f"[{strategy_name}] ⚠️ Prioridade BAIXA ({priority*100:.1f}%) | "
                f"Condição: {analysis.condition.value} | Recomendadas: {analysis.recommended_strategies}"
            )
            if strict_mode:
                return False
        
        return True
    
    def get_trading_context(self, analysis: Optional[MarketAnalysis]) -> Dict:
        """
        Retorna contexto completo de trading com recomendações
        
        Args:
            analysis: Análise de mercado
            
        Returns:
            Dict com contexto detalhado
        """
        if analysis is None:
            return {
                'condition': 'unknown',
                'allowed_strategies': ['all'],
                'blocked_strategies': [],
                'warnings': ['Sem análise de mercado disponível'],
            }
        
        priorities = self.get_strategy_priority(analysis)
        
        # Estratégias permitidas (prioridade >= 30%)
        allowed = [s for s, p in priorities.items() if p >= 0.3]
        
        # Estratégias bloqueadas (prioridade < 30%)
        blocked = [s for s, p in priorities.items() if p < 0.3]
        
        return {
            'condition': analysis.condition.value,
            'strength': analysis.strength,
            'confidence': analysis.confidence,
            'volatility': analysis.volatility,
            'volume': analysis.volume,
            'trend_strength': analysis.trend_strength,
            'allowed_strategies': allowed,
            'blocked_strategies': blocked,
            'priorities': priorities,
            'warnings': self._generate_warnings(analysis),
        }
    
    def _generate_warnings(self, analysis: MarketAnalysis) -> List[str]:
        """
        Gera alertas baseado nas condições de mercado
        
        Args:
            analysis: Análise de mercado
            
        Returns:
            Lista de avisos
        """
        warnings = []
        
        # Volatilidade muito alta
        if analysis.volatility > 0.7:
            warnings.append(f"⚠️ Volatilidade ALTA ({analysis.volatility*100:.1f}%) - Risco aumentado")
        
        # Volume muito baixo
        if analysis.volume < 0.3:
            warnings.append(f"⚠️ Volume BAIXO ({analysis.volume:.2f}x) - Liquidez reduzida")
        
        # Tendência muito forte
        if abs(analysis.trend_strength) > 0.8:
            direction = "ALTA" if analysis.trend_strength > 0 else "BAIXA"
            warnings.append(f"📈 Tendência {direction} FORTE ({abs(analysis.trend_strength)*100:.1f}%)")
        
        # Condição NEWS_IMPACT
        if analysis.condition == MarketCondition.NEWS_IMPACT:
            warnings.append("📰 IMPACTO DE NOTÍCIAS detectado - Volatilidade esperada")
        
        # Confiança baixa
        if analysis.confidence < 0.6:
            warnings.append(f"⚠️ Confiança BAIXA ({analysis.confidence*100:.1f}%) na análise")
        
        return warnings
        
        return priorities
