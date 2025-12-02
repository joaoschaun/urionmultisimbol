"""
Market Context Analyzer - O CÉREBRO DIRECIONAL DO URION
=========================================================
Este módulo analisa timeframes MAIORES (D1, H4, H1) e define o CONTEXTO DIRECIONAL
que TODAS as estratégias de timeframes menores devem seguir.

HIERARQUIA DE TIMEFRAMES:
- D1: Define a TENDÊNCIA MACRO (semanas/meses)
- H4: Define a TENDÊNCIA INTERMEDIÁRIA (dias)  
- H1: Define a TENDÊNCIA DE CURTO PRAZO (horas)
- M15/M5: Apenas para TIMING de entrada (seguem a direção de H1+)

REGRA DE OURO:
"Estratégias de TF menor SÓ OPERAM na direção confirmada pelo TF maior"

Exemplo:
- Se D1 é BULLISH e H4 é BULLISH → Scalping em M5 só faz BUY
- Se D1 é BEARISH mas H4 é NEUTRAL → Aguardar confirmação
- Se D1 é BULLISH mas H1 é BEARISH → Aguardar alinhamento

MARKET REGIMES:
1. TRENDING_STRONG: ADX > 35, direção clara → TrendFollowing é prioridade
2. TRENDING_WEAK: ADX 25-35, direção indefinida → Cautela
3. RANGING: ADX < 25, preço lateral → MeanReversion/RangeTrading ativado
4. HIGH_VOLATILITY: ATR muito alto → Reduzir exposição
5. LOW_VOLATILITY: ATR muito baixo → Evitar trades
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from loguru import logger
import threading


class MarketDirection(Enum):
    """Direção do mercado"""
    STRONG_BULLISH = 4   # Tendência de alta muito forte
    BULLISH = 3          # Tendência de alta
    WEAK_BULLISH = 2     # Leve viés de alta
    NEUTRAL = 0          # Sem direção clara
    WEAK_BEARISH = -2    # Leve viés de baixa
    BEARISH = -3         # Tendência de baixa
    STRONG_BEARISH = -4  # Tendência de baixa muito forte


class MarketRegime(Enum):
    """Regime de mercado"""
    TRENDING_STRONG = "TRENDING_STRONG"   # ADX > 35: Tendência forte
    TRENDING_WEAK = "TRENDING_WEAK"       # ADX 25-35: Tendência fraca
    RANGING = "RANGING"                   # ADX < 25: Lateral
    HIGH_VOLATILITY = "HIGH_VOLATILITY"   # ATR muito alto
    LOW_VOLATILITY = "LOW_VOLATILITY"     # ATR muito baixo
    BREAKOUT = "BREAKOUT"                 # Potencial rompimento


@dataclass
class TimeframeContext:
    """Contexto de um timeframe específico"""
    timeframe: str
    direction: MarketDirection
    adx: float
    di_plus: float
    di_minus: float
    ema_alignment: str  # 'bullish', 'bearish', 'mixed'
    rsi: float
    macd_histogram: float
    atr_pips: float
    price_vs_ema200: str  # 'above', 'below', 'at'
    confidence: float
    timestamp: datetime


@dataclass  
class MarketContextSnapshot:
    """Snapshot completo do contexto de mercado"""
    symbol: str
    timestamp: datetime
    
    # Contextos por timeframe
    d1_context: Optional[TimeframeContext]
    h4_context: Optional[TimeframeContext]
    h1_context: Optional[TimeframeContext]
    
    # Análise consolidada
    macro_direction: MarketDirection      # D1+H4 combinados
    short_term_direction: MarketDirection # H1
    regime: MarketRegime
    regime_strength: float  # 0-1
    
    # Recomendações para estratégias
    recommended_strategies: List[str]
    allowed_directions: List[str]  # ['BUY'], ['SELL'], ou ['BUY', 'SELL']
    
    # Ajustes de risco
    risk_multiplier: float  # 1.0 normal, <1 reduzir, >1 aumentar
    max_positions: int      # Limite de posições baseado no contexto


class MarketContextAnalyzer:
    """
    Analisador Central de Contexto de Mercado
    
    Este é o CÉREBRO que coordena todas as estratégias.
    Antes de qualquer estratégia operar, ela deve consultar este contexto.
    """
    
    def __init__(self, technical_analyzer, config: Dict, symbol: str = "XAUUSD"):
        """
        Args:
            technical_analyzer: Instância do TechnicalAnalyzer
            config: Configurações do sistema
            symbol: Símbolo a analisar
        """
        self.ta = technical_analyzer
        self.config = config
        self.symbol = symbol
        
        # Cache do contexto (atualizado periodicamente)
        self._context_cache: Dict[str, MarketContextSnapshot] = {}
        self._cache_timeout = timedelta(minutes=5)  # Contexto válido por 5 min
        
        # Lock para thread safety
        self._lock = threading.Lock()
        
        # Configurações
        self.adx_strong_threshold = config.get('market_context', {}).get('adx_strong', 35)
        self.adx_trend_threshold = config.get('market_context', {}).get('adx_trend', 25)
        self.atr_high_multiplier = config.get('market_context', {}).get('atr_high', 2.0)
        self.atr_low_multiplier = config.get('market_context', {}).get('atr_low', 0.5)
        
        logger.info(f"🧠 MarketContextAnalyzer inicializado para {symbol}")
    
    def get_context(self, force_refresh: bool = False) -> Optional[MarketContextSnapshot]:
        """
        Obtém o contexto atual do mercado.
        
        Este método deve ser chamado por TODAS as estratégias antes de operar.
        
        Args:
            force_refresh: Se True, ignora cache e recalcula
            
        Returns:
            MarketContextSnapshot com análise completa
        """
        with self._lock:
            cache_key = self.symbol
            
            # Verificar cache
            if not force_refresh and cache_key in self._context_cache:
                cached = self._context_cache[cache_key]
                age = datetime.now() - cached.timestamp
                if age < self._cache_timeout:
                    return cached
            
            # Calcular novo contexto
            try:
                context = self._analyze_market_context()
                if context:
                    self._context_cache[cache_key] = context
                    logger.info(
                        f"🧠 [{self.symbol}] Contexto atualizado: "
                        f"Macro={context.macro_direction.name}, "
                        f"Regime={context.regime.value}, "
                        f"Allowed={context.allowed_directions}"
                    )
                return context
            except Exception as e:
                logger.error(f"Erro ao analisar contexto: {e}")
                return None
    
    def _analyze_market_context(self) -> Optional[MarketContextSnapshot]:
        """Analisa contexto completo do mercado"""
        
        # Obter análise técnica de cada timeframe
        d1_analysis = self._analyze_timeframe('D1')
        h4_analysis = self._analyze_timeframe('H4')
        h1_analysis = self._analyze_timeframe('H1')
        
        if not h1_analysis:
            logger.warning("H1 não disponível - contexto incompleto")
            return None
        
        # Calcular direção macro (D1 + H4)
        macro_direction = self._calculate_macro_direction(d1_analysis, h4_analysis)
        
        # Direção de curto prazo (H1)
        short_term_direction = h1_analysis.direction if h1_analysis else MarketDirection.NEUTRAL
        
        # Determinar regime de mercado
        regime, regime_strength = self._determine_regime(d1_analysis, h4_analysis, h1_analysis)
        
        # Determinar estratégias recomendadas
        recommended_strategies = self._get_recommended_strategies(regime, macro_direction)
        
        # Determinar direções permitidas
        allowed_directions = self._get_allowed_directions(
            macro_direction, short_term_direction, regime
        )
        
        # Calcular ajustes de risco
        risk_multiplier = self._calculate_risk_multiplier(regime, regime_strength)
        max_positions = self._calculate_max_positions(regime, regime_strength)
        
        return MarketContextSnapshot(
            symbol=self.symbol,
            timestamp=datetime.now(),
            d1_context=d1_analysis,
            h4_context=h4_analysis,
            h1_context=h1_analysis,
            macro_direction=macro_direction,
            short_term_direction=short_term_direction,
            regime=regime,
            regime_strength=regime_strength,
            recommended_strategies=recommended_strategies,
            allowed_directions=allowed_directions,
            risk_multiplier=risk_multiplier,
            max_positions=max_positions
        )
    
    def _analyze_timeframe(self, timeframe: str) -> Optional[TimeframeContext]:
        """Analisa um timeframe específico"""
        try:
            # Obter análise técnica completa do timeframe
            ta_result = self.ta.analyze(timeframe)
            if not ta_result or timeframe not in ta_result:
                return None
            
            tf_data = ta_result[timeframe]
            
            # Extrair indicadores
            adx_data = tf_data.get('adx', {})
            adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else 0
            di_plus = adx_data.get('di_plus', 0) if isinstance(adx_data, dict) else 0
            di_minus = adx_data.get('di_minus', 0) if isinstance(adx_data, dict) else 0
            
            rsi = tf_data.get('rsi', 50)
            
            macd_data = tf_data.get('macd', {})
            macd_hist = macd_data.get('histogram', 0) if isinstance(macd_data, dict) else 0
            
            ema_data = tf_data.get('ema', {})
            ema_9 = ema_data.get('ema_9', 0) if isinstance(ema_data, dict) else 0
            ema_21 = ema_data.get('ema_21', 0) if isinstance(ema_data, dict) else 0
            ema_50 = ema_data.get('ema_50', 0) if isinstance(ema_data, dict) else 0
            ema_200 = ema_data.get('ema_200', ema_50) if isinstance(ema_data, dict) else ema_50
            
            current_price = tf_data.get('current_price', 0)
            
            atr_raw = tf_data.get('atr', 0)
            atr = atr_raw if isinstance(atr_raw, (int, float)) else atr_raw.get('atr', 0)
            atr_pips = atr / 0.1 if self.symbol == 'XAUUSD' else atr / 0.0001
            
            # Determinar alinhamento de EMAs
            if ema_9 > ema_21 > ema_50:
                ema_alignment = 'bullish'
            elif ema_9 < ema_21 < ema_50:
                ema_alignment = 'bearish'
            else:
                ema_alignment = 'mixed'
            
            # Posição do preço vs EMA200
            if current_price > ema_200 * 1.001:
                price_vs_ema200 = 'above'
            elif current_price < ema_200 * 0.999:
                price_vs_ema200 = 'below'
            else:
                price_vs_ema200 = 'at'
            
            # Calcular direção
            direction = self._calculate_direction(
                adx, di_plus, di_minus, ema_alignment, 
                rsi, macd_hist, price_vs_ema200
            )
            
            # Calcular confiança
            confidence = self._calculate_confidence(
                adx, abs(di_plus - di_minus), ema_alignment, rsi
            )
            
            return TimeframeContext(
                timeframe=timeframe,
                direction=direction,
                adx=adx,
                di_plus=di_plus,
                di_minus=di_minus,
                ema_alignment=ema_alignment,
                rsi=rsi,
                macd_histogram=macd_hist,
                atr_pips=atr_pips,
                price_vs_ema200=price_vs_ema200,
                confidence=confidence,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Erro ao analisar {timeframe}: {e}")
            return None
    
    def _calculate_direction(
        self, adx: float, di_plus: float, di_minus: float,
        ema_alignment: str, rsi: float, macd_hist: float,
        price_vs_ema200: str
    ) -> MarketDirection:
        """Calcula a direção baseada nos indicadores"""
        
        score = 0
        
        # ADX e Direcionais (peso: 3)
        if adx > self.adx_strong_threshold:
            if di_plus > di_minus * 1.2:
                score += 3
            elif di_minus > di_plus * 1.2:
                score -= 3
        elif adx > self.adx_trend_threshold:
            if di_plus > di_minus:
                score += 2
            elif di_minus > di_plus:
                score -= 2
        
        # EMA Alignment (peso: 2)
        if ema_alignment == 'bullish':
            score += 2
        elif ema_alignment == 'bearish':
            score -= 2
        
        # RSI (peso: 1)
        if rsi > 55:
            score += 1
        elif rsi < 45:
            score -= 1
        
        # MACD Histogram (peso: 2)
        if macd_hist > 0:
            score += 2 if macd_hist > 1 else 1
        elif macd_hist < 0:
            score -= 2 if macd_hist < -1 else 1
        
        # Price vs EMA200 (peso: 2)
        if price_vs_ema200 == 'above':
            score += 2
        elif price_vs_ema200 == 'below':
            score -= 2
        
        # Converter score para direção
        if score >= 8:
            return MarketDirection.STRONG_BULLISH
        elif score >= 5:
            return MarketDirection.BULLISH
        elif score >= 2:
            return MarketDirection.WEAK_BULLISH
        elif score <= -8:
            return MarketDirection.STRONG_BEARISH
        elif score <= -5:
            return MarketDirection.BEARISH
        elif score <= -2:
            return MarketDirection.WEAK_BEARISH
        else:
            return MarketDirection.NEUTRAL
    
    def _calculate_confidence(
        self, adx: float, di_diff: float, 
        ema_alignment: str, rsi: float
    ) -> float:
        """Calcula confiança do contexto (0-1)"""
        
        confidence = 0.0
        
        # ADX contribui para confiança
        if adx > 40:
            confidence += 0.3
        elif adx > 30:
            confidence += 0.2
        elif adx > 25:
            confidence += 0.1
        
        # Diferença entre DI+ e DI-
        if di_diff > 15:
            confidence += 0.2
        elif di_diff > 10:
            confidence += 0.15
        elif di_diff > 5:
            confidence += 0.1
        
        # EMA alignment
        if ema_alignment in ['bullish', 'bearish']:
            confidence += 0.25
        
        # RSI não extremo
        if 35 < rsi < 65:
            confidence += 0.15
        elif 25 < rsi < 75:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_macro_direction(
        self, d1: Optional[TimeframeContext], 
        h4: Optional[TimeframeContext]
    ) -> MarketDirection:
        """Calcula direção macro (D1 + H4 combinados)"""
        
        if not d1 and not h4:
            return MarketDirection.NEUTRAL
        
        # Se só tem um, usa ele
        if not d1:
            return h4.direction
        if not h4:
            return d1.direction
        
        # Combinar D1 (peso 60%) e H4 (peso 40%)
        d1_score = d1.direction.value * 0.6
        h4_score = h4.direction.value * 0.4
        combined_score = d1_score + h4_score
        
        # Bonus se alinhados
        if d1.direction.value * h4.direction.value > 0:  # Mesmo sinal
            combined_score *= 1.2
        
        # Converter de volta
        if combined_score >= 3:
            return MarketDirection.STRONG_BULLISH
        elif combined_score >= 2:
            return MarketDirection.BULLISH
        elif combined_score >= 1:
            return MarketDirection.WEAK_BULLISH
        elif combined_score <= -3:
            return MarketDirection.STRONG_BEARISH
        elif combined_score <= -2:
            return MarketDirection.BEARISH
        elif combined_score <= -1:
            return MarketDirection.WEAK_BEARISH
        else:
            return MarketDirection.NEUTRAL
    
    def _determine_regime(
        self, d1: Optional[TimeframeContext],
        h4: Optional[TimeframeContext],
        h1: Optional[TimeframeContext]
    ) -> Tuple[MarketRegime, float]:
        """Determina o regime de mercado atual"""
        
        # Usar H4 como referência principal para regime
        ref = h4 or h1
        if not ref:
            return MarketRegime.RANGING, 0.5
        
        adx = ref.adx
        atr_pips = ref.atr_pips
        
        # ATR médio histórico (aproximado para XAUUSD)
        avg_atr = 15.0  # pips
        
        # Verificar volatilidade
        if atr_pips > avg_atr * self.atr_high_multiplier:
            return MarketRegime.HIGH_VOLATILITY, min(atr_pips / (avg_atr * 3), 1.0)
        
        if atr_pips < avg_atr * self.atr_low_multiplier:
            return MarketRegime.LOW_VOLATILITY, 1.0 - (atr_pips / avg_atr)
        
        # Verificar tendência baseado em ADX
        if adx >= self.adx_strong_threshold:
            return MarketRegime.TRENDING_STRONG, min((adx - 25) / 25, 1.0)
        elif adx >= self.adx_trend_threshold:
            return MarketRegime.TRENDING_WEAK, (adx - 15) / 20
        else:
            return MarketRegime.RANGING, 1.0 - (adx / 25)
    
    def _get_recommended_strategies(
        self, regime: MarketRegime, 
        direction: MarketDirection
    ) -> List[str]:
        """Retorna estratégias recomendadas para o regime atual"""
        
        recommendations = {
            MarketRegime.TRENDING_STRONG: [
                'trend_following',  # Principal
                'scalping',         # Na direção da tendência
            ],
            MarketRegime.TRENDING_WEAK: [
                'trend_following',
                'breakout',
            ],
            MarketRegime.RANGING: [
                'mean_reversion',   # Principal
                'range_trading',    # Suporte/resistência
            ],
            MarketRegime.HIGH_VOLATILITY: [
                'breakout',         # Pode haver movimentos fortes
            ],
            MarketRegime.LOW_VOLATILITY: [],  # Evitar trades
            MarketRegime.BREAKOUT: [
                'breakout',
                'trend_following',
            ]
        }
        
        return recommendations.get(regime, ['trend_following'])
    
    def _get_allowed_directions(
        self, macro: MarketDirection,
        short_term: MarketDirection,
        regime: MarketRegime
    ) -> List[str]:
        """
        Determina direções permitidas para trading.
        
        Esta é a REGRA DE OURO: estratégias só podem operar
        nas direções aprovadas pelo contexto maior.
        """
        
        # Se regime é ranging, permitir ambas com cuidado
        if regime == MarketRegime.RANGING:
            return ['BUY', 'SELL']  # Mean reversion pode ir para ambos lados
        
        # Se macro é neutro, usar short_term
        if macro == MarketDirection.NEUTRAL:
            if short_term.value > 0:
                return ['BUY']
            elif short_term.value < 0:
                return ['SELL']
            else:
                return []  # Não operar
        
        # Macro define a direção principal
        if macro.value >= MarketDirection.WEAK_BULLISH.value:
            # Tendência de alta - só permitir compras
            return ['BUY']
        elif macro.value <= MarketDirection.WEAK_BEARISH.value:
            # Tendência de baixa - só permitir vendas
            return ['SELL']
        else:
            return []  # Neutro - não operar
    
    def _calculate_risk_multiplier(
        self, regime: MarketRegime, 
        strength: float
    ) -> float:
        """Calcula multiplicador de risco baseado no contexto"""
        
        base_multipliers = {
            MarketRegime.TRENDING_STRONG: 1.2,   # Aumentar em tendência forte
            MarketRegime.TRENDING_WEAK: 1.0,     # Normal
            MarketRegime.RANGING: 0.8,           # Reduzir em ranging
            MarketRegime.HIGH_VOLATILITY: 0.5,   # Reduzir muito
            MarketRegime.LOW_VOLATILITY: 0.3,    # Evitar
            MarketRegime.BREAKOUT: 0.9,          # Cautela
        }
        
        return base_multipliers.get(regime, 1.0)
    
    def _calculate_max_positions(
        self, regime: MarketRegime, 
        strength: float
    ) -> int:
        """Calcula número máximo de posições baseado no contexto"""
        
        base_positions = {
            MarketRegime.TRENDING_STRONG: 4,
            MarketRegime.TRENDING_WEAK: 3,
            MarketRegime.RANGING: 2,
            MarketRegime.HIGH_VOLATILITY: 1,
            MarketRegime.LOW_VOLATILITY: 0,
            MarketRegime.BREAKOUT: 2,
        }
        
        return base_positions.get(regime, 2)
    
    # =========================================
    # MÉTODOS PÚBLICOS PARA ESTRATÉGIAS
    # =========================================
    
    def can_trade(self, direction: str) -> bool:
        """
        Verifica se uma direção específica é permitida.
        
        Args:
            direction: 'BUY' ou 'SELL'
            
        Returns:
            True se permitido, False caso contrário
        """
        context = self.get_context()
        if not context:
            return False
        
        return direction.upper() in context.allowed_directions
    
    def is_strategy_recommended(self, strategy_name: str) -> bool:
        """
        Verifica se uma estratégia é recomendada para o regime atual.
        
        Args:
            strategy_name: Nome da estratégia (ex: 'scalping', 'trend_following')
            
        Returns:
            True se recomendada, False caso contrário
        """
        context = self.get_context()
        if not context:
            return True  # Default: permitir
        
        return strategy_name.lower() in context.recommended_strategies
    
    def get_risk_adjustment(self) -> float:
        """
        Retorna o multiplicador de risco atual.
        
        Estratégias devem usar isso para ajustar tamanho de posição.
        
        Returns:
            Float entre 0.3 e 1.2
        """
        context = self.get_context()
        if not context:
            return 1.0
        
        return context.risk_multiplier
    
    def get_max_positions(self) -> int:
        """
        Retorna número máximo de posições permitidas.
        
        Returns:
            Int entre 0 e 4
        """
        context = self.get_context()
        if not context:
            return 2
        
        return context.max_positions
    
    def get_macro_bias(self) -> str:
        """
        Retorna o viés macro simplificado.
        
        Returns:
            'BULLISH', 'BEARISH', ou 'NEUTRAL'
        """
        context = self.get_context()
        if not context:
            return 'NEUTRAL'
        
        if context.macro_direction.value >= 2:
            return 'BULLISH'
        elif context.macro_direction.value <= -2:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def get_regime(self) -> str:
        """
        Retorna o regime atual.
        
        Returns:
            String do regime
        """
        context = self.get_context()
        if not context:
            return 'UNKNOWN'
        
        return context.regime.value


# =========================================
# SINGLETON GLOBAL
# =========================================

_market_context_instances: Dict[str, MarketContextAnalyzer] = {}
_lock = threading.Lock()


def get_market_context(technical_analyzer, config: Dict, symbol: str = "XAUUSD") -> MarketContextAnalyzer:
    """
    Factory function para obter/criar MarketContextAnalyzer.
    
    Garante que existe apenas uma instância por símbolo (singleton).
    """
    global _market_context_instances
    
    with _lock:
        if symbol not in _market_context_instances:
            _market_context_instances[symbol] = MarketContextAnalyzer(
                technical_analyzer, config, symbol
            )
        return _market_context_instances[symbol]


def clear_all_contexts():
    """Limpa todos os contextos em cache"""
    global _market_context_instances
    with _lock:
        _market_context_instances.clear()
