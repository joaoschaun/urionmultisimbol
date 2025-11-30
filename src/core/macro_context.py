# -*- coding: utf-8 -*-
"""
MACRO CONTEXT ANALYZER - URION 2.0
==================================
Integra índices macroeconômicos para contexto de mercado

Índices Monitorados:
- DXY (Dollar Index) - Correlação inversa com XAUUSD
- VIX (Volatility Index) - Medo/incerteza do mercado
- US10Y (Treasury Yields) - Impacto em moedas e ouro

Autor: Urion Trading Bot
Versão: 2.0
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from loguru import logger

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance não disponível - instale com: pip install yfinance")


class MarketSentiment(Enum):
    """Sentimento geral do mercado"""
    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"


class DXYTrend(Enum):
    """Tendência do Dollar Index"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class VIXLevel(Enum):
    """Níveis do VIX (medo do mercado)"""
    COMPLACENT = "complacent"      # VIX < 12 - Baixa volatilidade
    LOW = "low"                     # VIX 12-16 - Normal baixo
    NORMAL = "normal"               # VIX 16-20 - Normal
    ELEVATED = "elevated"           # VIX 20-25 - Elevado
    HIGH = "high"                   # VIX 25-30 - Alto
    EXTREME = "extreme"             # VIX > 30 - Pânico


@dataclass
class MacroData:
    """Dados de um índice macro"""
    symbol: str
    current_price: float
    previous_close: float
    change_percent: float
    high_52w: float = 0.0
    low_52w: float = 0.0
    sma_20: float = 0.0
    sma_50: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    
    @property
    def above_sma20(self) -> bool:
        return self.current_price > self.sma_20 if self.sma_20 > 0 else False
    
    @property
    def above_sma50(self) -> bool:
        return self.current_price > self.sma_50 if self.sma_50 > 0 else False
    
    @property
    def trend_strength(self) -> float:
        """Força da tendência baseado em SMAs (-1 a 1)"""
        if self.sma_20 == 0 or self.sma_50 == 0:
            return 0.0
        
        # Distância do preço em relação às médias
        dist_20 = (self.current_price - self.sma_20) / self.sma_20
        dist_50 = (self.current_price - self.sma_50) / self.sma_50
        
        return np.clip((dist_20 + dist_50) / 2 * 10, -1.0, 1.0)


@dataclass
class MacroContext:
    """Contexto macroeconômico completo"""
    dxy: Optional[MacroData] = None
    vix: Optional[MacroData] = None
    us10y: Optional[MacroData] = None
    
    dxy_trend: DXYTrend = DXYTrend.NEUTRAL
    vix_level: VIXLevel = VIXLevel.NORMAL
    market_sentiment: MarketSentiment = MarketSentiment.NEUTRAL
    
    # Impacto em símbolos específicos
    xauusd_bias: float = 0.0   # -1 = bearish, 0 = neutral, 1 = bullish
    eurusd_bias: float = 0.0
    gbpusd_bias: float = 0.0
    usdjpy_bias: float = 0.0
    
    # Ajustes de risco recomendados
    risk_multiplier: float = 1.0
    volatility_adjustment: float = 1.0
    
    # Alertas
    alerts: List[str] = field(default_factory=list)
    
    last_update: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'dxy_trend': self.dxy_trend.value,
            'vix_level': self.vix_level.value,
            'market_sentiment': self.market_sentiment.value,
            'biases': {
                'XAUUSD': self.xauusd_bias,
                'EURUSD': self.eurusd_bias,
                'GBPUSD': self.gbpusd_bias,
                'USDJPY': self.usdjpy_bias
            },
            'risk_multiplier': self.risk_multiplier,
            'volatility_adjustment': self.volatility_adjustment,
            'alerts': self.alerts,
            'last_update': self.last_update.isoformat()
        }


class MacroContextAnalyzer:
    """
    Analisador de Contexto Macroeconômico
    
    Usa DXY, VIX e US10Y para:
    1. Determinar viés direcional de pares
    2. Ajustar risco baseado em volatilidade
    3. Alertar sobre condições extremas
    
    Correlações conhecidas:
    - XAUUSD vs DXY: -0.80 (inversa forte)
    - EURUSD vs DXY: -0.95 (inversa muito forte)
    - VIX alto = mais volatilidade = reduzir tamanho
    """
    
    # Símbolos do Yahoo Finance
    SYMBOLS = {
        'DXY': 'DX-Y.NYB',      # Dollar Index
        'VIX': '^VIX',          # Volatility Index
        'US10Y': '^TNX'         # 10-Year Treasury Yield
    }
    
    # Limiares do VIX
    VIX_THRESHOLDS = {
        'complacent': 12,
        'low': 16,
        'normal': 20,
        'elevated': 25,
        'high': 30
    }
    
    def __init__(self, config: dict = None):
        """
        Args:
            config: Configurações do módulo
        """
        self.config = config or {}
        
        # Configurações
        self.update_interval = self.config.get('update_interval_minutes', 15)
        self.cache_duration = timedelta(minutes=self.config.get('cache_duration_minutes', 5))
        self.vix_risk_threshold = self.config.get('vix_risk_threshold', 25)
        self.dxy_sensitivity = self.config.get('dxy_sensitivity', 1.0)
        
        # Cache
        self._macro_cache: Dict[str, MacroData] = {}
        self._last_fetch: Optional[datetime] = None
        self._current_context: Optional[MacroContext] = None
        
        # Histórico para análise de tendência
        self._price_history: Dict[str, List[float]] = {
            'DXY': [],
            'VIX': [],
            'US10Y': []
        }
        
        logger.info("📊 MacroContextAnalyzer inicializado")
        
        if not YFINANCE_AVAILABLE:
            logger.warning("⚠️ yfinance não disponível - dados macro limitados")
    
    async def fetch_macro_data(self) -> Dict[str, MacroData]:
        """
        Busca dados macro do Yahoo Finance
        
        Returns:
            Dict com dados de cada índice
        """
        if not YFINANCE_AVAILABLE:
            logger.warning("yfinance não disponível")
            return {}
        
        # Verificar cache
        if self._last_fetch and datetime.now() - self._last_fetch < self.cache_duration:
            return self._macro_cache
        
        try:
            result = {}
            
            for name, symbol in self.SYMBOLS.items():
                try:
                    data = await self._fetch_single_symbol(symbol, name)
                    if data:
                        result[name] = data
                        self._macro_cache[name] = data
                        
                        # Adicionar ao histórico
                        self._price_history[name].append(data.current_price)
                        if len(self._price_history[name]) > 100:
                            self._price_history[name] = self._price_history[name][-100:]
                            
                except Exception as e:
                    logger.warning(f"Erro ao buscar {name}: {e}")
            
            self._last_fetch = datetime.now()
            return result
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados macro: {e}")
            return self._macro_cache
    
    async def _fetch_single_symbol(self, symbol: str, name: str) -> Optional[MacroData]:
        """
        Busca dados de um único símbolo
        
        Args:
            symbol: Símbolo Yahoo Finance
            name: Nome do índice (DXY, VIX, etc)
            
        Returns:
            MacroData ou None
        """
        try:
            # Executar em thread separada para não bloquear
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, yf.Ticker, symbol)
            
            # Buscar dados históricos para calcular SMAs
            hist = await loop.run_in_executor(
                None, 
                lambda: ticker.history(period='3mo')
            )
            
            if hist.empty:
                logger.warning(f"Sem dados para {symbol}")
                return None
            
            # Dados atuais
            current = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current
            
            # SMAs
            sma_20 = hist['Close'].tail(20).mean() if len(hist) >= 20 else current
            sma_50 = hist['Close'].tail(50).mean() if len(hist) >= 50 else current
            
            # 52 semanas
            high_52w = hist['High'].max()
            low_52w = hist['Low'].min()
            
            # Calcular mudança percentual
            change_pct = ((current - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            
            return MacroData(
                symbol=name,
                current_price=current,
                previous_close=prev_close,
                change_percent=change_pct,
                high_52w=high_52w,
                low_52w=low_52w,
                sma_20=sma_20,
                sma_50=sma_50,
                last_update=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Erro ao processar {symbol}: {e}")
            return None
    
    async def get_context(self, force_refresh: bool = False) -> MacroContext:
        """
        Obtém contexto macro completo
        
        Args:
            force_refresh: Forçar atualização do cache
            
        Returns:
            MacroContext com análise completa
        """
        # Verificar cache de contexto
        if (not force_refresh and 
            self._current_context and 
            datetime.now() - self._current_context.last_update < self.cache_duration):
            return self._current_context
        
        # Buscar dados
        data = await self.fetch_macro_data()
        
        if not data:
            # Retornar contexto neutro se não houver dados
            return MacroContext()
        
        # Analisar cada componente
        context = MacroContext(
            dxy=data.get('DXY'),
            vix=data.get('VIX'),
            us10y=data.get('US10Y'),
            last_update=datetime.now()
        )
        
        # Analisar DXY
        if context.dxy:
            context.dxy_trend = self._analyze_dxy_trend(context.dxy)
        
        # Analisar VIX
        if context.vix:
            context.vix_level = self._analyze_vix_level(context.vix)
        
        # Calcular biases por símbolo
        self._calculate_symbol_biases(context)
        
        # Calcular ajustes de risco
        self._calculate_risk_adjustments(context)
        
        # Determinar sentimento geral
        context.market_sentiment = self._determine_market_sentiment(context)
        
        # Gerar alertas
        context.alerts = self._generate_alerts(context)
        
        self._current_context = context
        
        logger.debug(f"📊 Contexto macro atualizado: DXY={context.dxy_trend.value}, VIX={context.vix_level.value}")
        
        return context
    
    def _analyze_dxy_trend(self, dxy: MacroData) -> DXYTrend:
        """
        Analisa tendência do Dollar Index
        
        Args:
            dxy: Dados do DXY
            
        Returns:
            DXYTrend
        """
        # Baseado na posição relativa às SMAs
        strength = dxy.trend_strength
        change = dxy.change_percent
        
        # Combinar força de tendência com mudança recente
        score = strength * 0.7 + (change / 2) * 0.3
        
        if score > 0.5:
            return DXYTrend.STRONG_BULLISH
        elif score > 0.2:
            return DXYTrend.BULLISH
        elif score > -0.2:
            return DXYTrend.NEUTRAL
        elif score > -0.5:
            return DXYTrend.BEARISH
        else:
            return DXYTrend.STRONG_BEARISH
    
    def _analyze_vix_level(self, vix: MacroData) -> VIXLevel:
        """
        Analisa nível do VIX
        
        Args:
            vix: Dados do VIX
            
        Returns:
            VIXLevel
        """
        price = vix.current_price
        
        if price < self.VIX_THRESHOLDS['complacent']:
            return VIXLevel.COMPLACENT
        elif price < self.VIX_THRESHOLDS['low']:
            return VIXLevel.LOW
        elif price < self.VIX_THRESHOLDS['normal']:
            return VIXLevel.NORMAL
        elif price < self.VIX_THRESHOLDS['elevated']:
            return VIXLevel.ELEVATED
        elif price < self.VIX_THRESHOLDS['high']:
            return VIXLevel.HIGH
        else:
            return VIXLevel.EXTREME
    
    def _calculate_symbol_biases(self, context: MacroContext) -> None:
        """
        Calcula viés direcional para cada símbolo baseado no DXY
        
        Correlações:
        - XAUUSD vs DXY: -0.80 (ouro sobe quando dólar cai)
        - EURUSD vs DXY: -0.95 (euro é ~57% do DXY)
        - GBPUSD vs DXY: -0.90 (libra correlação inversa)
        - USDJPY vs DXY: +0.70 (positiva, JPY é ativo safe-haven)
        
        Args:
            context: Contexto a ser atualizado
        """
        if not context.dxy:
            return
        
        dxy_strength = context.dxy.trend_strength
        
        # Mapear DXY trend para score numérico
        trend_scores = {
            DXYTrend.STRONG_BULLISH: 1.0,
            DXYTrend.BULLISH: 0.5,
            DXYTrend.NEUTRAL: 0.0,
            DXYTrend.BEARISH: -0.5,
            DXYTrend.STRONG_BEARISH: -1.0
        }
        
        dxy_score = trend_scores.get(context.dxy_trend, 0.0)
        
        # Aplicar correlações (inverter sinal para correlações negativas)
        sensitivity = self.dxy_sensitivity
        
        # XAUUSD: Correlação -0.80 com DXY
        # DXY subindo = XAUUSD bearish
        context.xauusd_bias = -dxy_score * 0.80 * sensitivity
        
        # EURUSD: Correlação -0.95 com DXY (mais forte)
        context.eurusd_bias = -dxy_score * 0.95 * sensitivity
        
        # GBPUSD: Correlação -0.90 com DXY
        context.gbpusd_bias = -dxy_score * 0.90 * sensitivity
        
        # USDJPY: Correlação +0.70 com DXY (positiva)
        # DXY subindo = USDJPY bullish
        context.usdjpy_bias = dxy_score * 0.70 * sensitivity
        
        # Clipar valores
        context.xauusd_bias = np.clip(context.xauusd_bias, -1.0, 1.0)
        context.eurusd_bias = np.clip(context.eurusd_bias, -1.0, 1.0)
        context.gbpusd_bias = np.clip(context.gbpusd_bias, -1.0, 1.0)
        context.usdjpy_bias = np.clip(context.usdjpy_bias, -1.0, 1.0)
    
    def _calculate_risk_adjustments(self, context: MacroContext) -> None:
        """
        Calcula ajustes de risco baseado no VIX
        
        VIX alto = mais volatilidade = reduzir tamanho
        VIX baixo = menos volatilidade = posições normais
        
        Args:
            context: Contexto a ser atualizado
        """
        if not context.vix:
            return
        
        vix_price = context.vix.current_price
        
        # Ajuste de volatilidade (inverso do VIX normalizado)
        # VIX 20 = base (1.0)
        # VIX 30 = reduzir para 0.67
        # VIX 40 = reduzir para 0.50
        # VIX 15 = aumentar para 1.33 (capped at 1.2)
        base_vix = 20.0
        volatility_ratio = base_vix / vix_price if vix_price > 0 else 1.0
        
        # Clipar entre 0.5 e 1.2
        context.volatility_adjustment = np.clip(volatility_ratio, 0.5, 1.2)
        
        # Multiplicador de risco geral
        risk_levels = {
            VIXLevel.COMPLACENT: 1.0,      # VIX muito baixo pode anteceder volatilidade
            VIXLevel.LOW: 1.0,
            VIXLevel.NORMAL: 1.0,
            VIXLevel.ELEVATED: 0.8,         # Reduzir risco
            VIXLevel.HIGH: 0.6,             # Reduzir mais
            VIXLevel.EXTREME: 0.4           # Modo conservador
        }
        
        context.risk_multiplier = risk_levels.get(context.vix_level, 1.0)
    
    def _determine_market_sentiment(self, context: MacroContext) -> MarketSentiment:
        """
        Determina sentimento geral do mercado
        
        Combina:
        - VIX (medo/ganância)
        - DXY trend (risk-on vs risk-off)
        
        Args:
            context: Contexto com dados analisados
            
        Returns:
            MarketSentiment
        """
        # Score baseado no VIX (inverso - VIX alto = medo)
        vix_sentiment_scores = {
            VIXLevel.COMPLACENT: 0.8,    # Complacência = ganância extrema
            VIXLevel.LOW: 0.5,
            VIXLevel.NORMAL: 0.0,
            VIXLevel.ELEVATED: -0.3,
            VIXLevel.HIGH: -0.6,
            VIXLevel.EXTREME: -1.0       # Pânico = medo extremo
        }
        
        vix_score = vix_sentiment_scores.get(context.vix_level, 0.0)
        
        # DXY forte geralmente indica risk-off (medo)
        dxy_sentiment_scores = {
            DXYTrend.STRONG_BULLISH: -0.3,   # Risk-off
            DXYTrend.BULLISH: -0.1,
            DXYTrend.NEUTRAL: 0.0,
            DXYTrend.BEARISH: 0.1,
            DXYTrend.STRONG_BEARISH: 0.3     # Risk-on
        }
        
        dxy_score = dxy_sentiment_scores.get(context.dxy_trend, 0.0)
        
        # Combinar (VIX tem mais peso)
        total_score = vix_score * 0.7 + dxy_score * 0.3
        
        if total_score > 0.6:
            return MarketSentiment.EXTREME_GREED
        elif total_score > 0.2:
            return MarketSentiment.GREED
        elif total_score > -0.2:
            return MarketSentiment.NEUTRAL
        elif total_score > -0.6:
            return MarketSentiment.FEAR
        else:
            return MarketSentiment.EXTREME_FEAR
    
    def _generate_alerts(self, context: MacroContext) -> List[str]:
        """
        Gera alertas baseados nas condições macro
        
        Args:
            context: Contexto analisado
            
        Returns:
            Lista de alertas
        """
        alerts = []
        
        # Alertas de VIX
        if context.vix_level == VIXLevel.EXTREME:
            alerts.append("🚨 VIX EXTREMO - Volatilidade muito alta, considere reduzir exposição")
        elif context.vix_level == VIXLevel.HIGH:
            alerts.append("⚠️ VIX Alto - Mercado com medo elevado, cuidado com posições")
        elif context.vix_level == VIXLevel.COMPLACENT:
            alerts.append("💤 VIX muito baixo - Complacência pode anteceder volatilidade")
        
        # Alertas de DXY
        if context.dxy_trend == DXYTrend.STRONG_BULLISH:
            alerts.append("💵 DXY em forte alta - Pressão bearish em XAUUSD, EURUSD, GBPUSD")
        elif context.dxy_trend == DXYTrend.STRONG_BEARISH:
            alerts.append("💵 DXY em forte queda - Suporte bullish para XAUUSD, EURUSD, GBPUSD")
        
        # Alertas de sentimento
        if context.market_sentiment == MarketSentiment.EXTREME_FEAR:
            alerts.append("😱 Sentimento: Medo Extremo - Possível oportunidade de compra em ativos de risco")
        elif context.market_sentiment == MarketSentiment.EXTREME_GREED:
            alerts.append("🤑 Sentimento: Ganância Extrema - Cuidado com correções")
        
        # Alerta de risco reduzido
        if context.risk_multiplier < 1.0:
            alerts.append(f"📉 Risco reduzido para {context.risk_multiplier:.0%} devido a volatilidade elevada")
        
        return alerts
    
    def get_symbol_bias(self, symbol: str) -> Tuple[float, str]:
        """
        Obtém viés para um símbolo específico
        
        Args:
            symbol: Símbolo (XAUUSD, EURUSD, etc)
            
        Returns:
            Tuple (bias_score, bias_description)
        """
        if not self._current_context:
            return 0.0, "neutral"
        
        # Mapear símbolo para atributo
        bias_map = {
            'XAUUSD': self._current_context.xauusd_bias,
            'EURUSD': self._current_context.eurusd_bias,
            'GBPUSD': self._current_context.gbpusd_bias,
            'USDJPY': self._current_context.usdjpy_bias
        }
        
        bias = bias_map.get(symbol.upper(), 0.0)
        
        if bias > 0.5:
            return bias, "strong_bullish"
        elif bias > 0.2:
            return bias, "bullish"
        elif bias > -0.2:
            return bias, "neutral"
        elif bias > -0.5:
            return bias, "bearish"
        else:
            return bias, "strong_bearish"
    
    def should_filter_trade(
        self,
        symbol: str,
        direction: str,
        min_alignment: float = 0.3
    ) -> Tuple[bool, str]:
        """
        Verifica se trade deve ser filtrado baseado no contexto macro
        
        Args:
            symbol: Símbolo sendo negociado
            direction: 'buy' ou 'sell'
            min_alignment: Alinhamento mínimo necessário (0-1)
            
        Returns:
            Tuple (should_filter, reason)
        """
        if not self._current_context:
            return False, "no_context"
        
        bias, bias_desc = self.get_symbol_bias(symbol)
        
        # Verificar alinhamento
        if direction.lower() == 'buy':
            if bias < -min_alignment:
                return True, f"macro_conflict_bearish_{abs(bias):.2f}"
        else:  # sell
            if bias > min_alignment:
                return True, f"macro_conflict_bullish_{bias:.2f}"
        
        # Verificar VIX extremo
        if self._current_context.vix_level == VIXLevel.EXTREME:
            return True, "vix_extreme"
        
        return False, "aligned"
    
    def adjust_confidence(
        self,
        symbol: str,
        direction: str,
        base_confidence: float
    ) -> float:
        """
        Ajusta confiança do sinal baseado no contexto macro
        
        Args:
            symbol: Símbolo
            direction: 'buy' ou 'sell'
            base_confidence: Confiança base do sinal
            
        Returns:
            Confiança ajustada
        """
        if not self._current_context:
            return base_confidence
        
        bias, _ = self.get_symbol_bias(symbol)
        
        # Calcular alinhamento
        if direction.lower() == 'buy':
            alignment = bias  # Bias positivo = alinhado com compra
        else:
            alignment = -bias  # Bias negativo = alinhado com venda
        
        # Ajuste baseado no alinhamento (-10% a +10%)
        alignment_adjustment = alignment * 0.10
        
        # Ajuste baseado no VIX
        vix_adjustments = {
            VIXLevel.COMPLACENT: 0.0,
            VIXLevel.LOW: 0.0,
            VIXLevel.NORMAL: 0.0,
            VIXLevel.ELEVATED: -0.03,
            VIXLevel.HIGH: -0.05,
            VIXLevel.EXTREME: -0.10
        }
        
        vix_adjustment = vix_adjustments.get(self._current_context.vix_level, 0.0)
        
        # Aplicar ajustes
        adjusted = base_confidence + alignment_adjustment + vix_adjustment
        
        # Clipar entre 0 e 1
        return float(np.clip(adjusted, 0.0, 1.0))
    
    def get_adjusted_lot_size(
        self,
        base_lot: float,
        symbol: str = None
    ) -> float:
        """
        Ajusta tamanho de lote baseado na volatilidade do mercado
        
        Args:
            base_lot: Lote base calculado
            symbol: Símbolo (opcional, para ajustes específicos)
            
        Returns:
            Lote ajustado
        """
        if not self._current_context:
            return base_lot
        
        # Aplicar multiplicador de risco e ajuste de volatilidade
        adjusted = base_lot * self._current_context.risk_multiplier
        adjusted *= self._current_context.volatility_adjustment
        
        # Arredondar para 2 casas decimais
        return round(adjusted, 2)
    
    async def get_summary(self) -> str:
        """
        Retorna resumo textual do contexto macro
        
        Returns:
            String com resumo formatado
        """
        context = await self.get_context()
        
        lines = [
            "📊 === CONTEXTO MACROECONÔMICO ===",
            ""
        ]
        
        # DXY
        if context.dxy:
            lines.append(f"💵 DXY: {context.dxy.current_price:.2f} ({context.dxy.change_percent:+.2f}%)")
            lines.append(f"   Tendência: {context.dxy_trend.value}")
        
        # VIX
        if context.vix:
            lines.append(f"📈 VIX: {context.vix.current_price:.2f} ({context.vix.change_percent:+.2f}%)")
            lines.append(f"   Nível: {context.vix_level.value}")
        
        # Sentimento
        lines.append(f"\n🎯 Sentimento: {context.market_sentiment.value}")
        
        # Biases
        lines.append("\n📊 Viés por Símbolo:")
        lines.append(f"   XAUUSD: {context.xauusd_bias:+.2f}")
        lines.append(f"   EURUSD: {context.eurusd_bias:+.2f}")
        lines.append(f"   GBPUSD: {context.gbpusd_bias:+.2f}")
        lines.append(f"   USDJPY: {context.usdjpy_bias:+.2f}")
        
        # Ajustes de risco
        lines.append(f"\n⚠️ Multiplicador de Risco: {context.risk_multiplier:.0%}")
        lines.append(f"📉 Ajuste Volatilidade: {context.volatility_adjustment:.0%}")
        
        # Alertas
        if context.alerts:
            lines.append("\n🔔 Alertas:")
            for alert in context.alerts:
                lines.append(f"   {alert}")
        
        return "\n".join(lines)


# =======================
# EXEMPLO DE USO
# =======================

async def example_usage():
    """Exemplo de uso do MacroContextAnalyzer"""
    
    # Configuração
    config = {
        'update_interval_minutes': 15,
        'cache_duration_minutes': 5,
        'vix_risk_threshold': 25,
        'dxy_sensitivity': 1.0
    }
    
    # Criar analisador
    analyzer = MacroContextAnalyzer(config)
    
    # Obter contexto
    context = await analyzer.get_context()
    
    # Imprimir resumo
    summary = await analyzer.get_summary()
    print(summary)
    
    # Verificar se deve filtrar trade
    should_filter, reason = analyzer.should_filter_trade(
        symbol="XAUUSD",
        direction="buy",
        min_alignment=0.3
    )
    print(f"\nFiltrar trade XAUUSD BUY? {should_filter} ({reason})")
    
    # Ajustar confiança
    adjusted_conf = analyzer.adjust_confidence(
        symbol="EURUSD",
        direction="sell",
        base_confidence=0.75
    )
    print(f"Confiança ajustada EURUSD SELL: {adjusted_conf:.2%}")
    
    # Ajustar lote
    adjusted_lot = analyzer.get_adjusted_lot_size(base_lot=0.10)
    print(f"Lote ajustado: {adjusted_lot:.2f}")


if __name__ == "__main__":
    asyncio.run(example_usage())
