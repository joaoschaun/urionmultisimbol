"""
Adaptive Trading Manager
Gerencia operação 24h com adaptação a diferentes períodos de liquidez
"""

from datetime import datetime, time, timedelta
from typing import Dict, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
import pytz
from loguru import logger


class TradingMode(Enum):
    """Modos de operação baseado na liquidez"""
    AGGRESSIVE = "aggressive"      # Alta liquidez - London/NY overlap
    NORMAL = "normal"              # Boa liquidez - London ou NY
    CONSERVATIVE = "conservative"  # Liquidez moderada - Tokyo
    MINIMAL = "minimal"            # Baixa liquidez - Sydney/Off-hours
    CLOSED = "closed"              # Fim de semana


@dataclass
class SessionParams:
    """Parâmetros adaptativos para cada sessão"""
    mode: TradingMode
    lot_multiplier: float          # Multiplicador de lote
    confidence_boost: float        # Ajuste de confiança mínima
    max_positions: int             # Posições máximas
    cycle_multiplier: float        # Multiplicador do ciclo (mais lento em baixa liquidez)
    sl_multiplier: float           # Multiplicador SL (mais largo em baixa volatilidade)
    tp_multiplier: float           # Multiplicador TP
    spread_tolerance: float        # Tolerância de spread extra
    strategies_enabled: list       # Estratégias recomendadas
    avoid_strategies: list         # Estratégias a evitar


class AdaptiveTradingManager:
    """
    Gerencia adaptação automática de parâmetros de trading
    baseado em sessão de mercado e liquidez
    """
    
    # Configuração de sessões com parâmetros adaptativos
    SESSION_CONFIGS = {
        # ═══════════════════════════════════════════════════════════════
        # 🌏 SYDNEY/WELLINGTON (21:00 - 06:00 UTC)
        # Baixíssima liquidez, spreads altos, movimentos lentos
        # ═══════════════════════════════════════════════════════════════
        'sydney': {
            'start_utc': time(21, 0),
            'end_utc': time(6, 0),
            'params': SessionParams(
                mode=TradingMode.MINIMAL,
                lot_multiplier=0.5,         # 50% do lote normal
                confidence_boost=0.10,      # +10% na confiança mínima
                max_positions=1,            # Apenas 1 posição
                cycle_multiplier=2.0,       # Ciclos 2x mais lentos
                sl_multiplier=1.5,          # SL 50% mais largo
                tp_multiplier=1.2,          # TP 20% maior (capturar moves lentos)
                spread_tolerance=2.0,       # 2x tolerância de spread
                strategies_enabled=['range_trading', 'mean_reversion'],
                avoid_strategies=['breakout', 'news_trading', 'scalping']
            ),
            'description': 'Sydney - Baixa liquidez',
            'volatility': 'very_low',
            'best_pairs': ['AUDUSD', 'NZDUSD', 'USDJPY']
        },
        
        # ═══════════════════════════════════════════════════════════════
        # 🗼 TOKYO (00:00 - 09:00 UTC)
        # Liquidez moderada, bom para JPY pairs
        # ═══════════════════════════════════════════════════════════════
        'tokyo': {
            'start_utc': time(0, 0),
            'end_utc': time(9, 0),
            'params': SessionParams(
                mode=TradingMode.CONSERVATIVE,
                lot_multiplier=0.7,         # 70% do lote normal
                confidence_boost=0.05,      # +5% na confiança mínima
                max_positions=2,            # Até 2 posições
                cycle_multiplier=1.5,       # Ciclos 50% mais lentos
                sl_multiplier=1.2,          # SL 20% mais largo
                tp_multiplier=1.0,          # TP normal
                spread_tolerance=1.5,       # 1.5x tolerância de spread
                strategies_enabled=['range_trading', 'mean_reversion', 'scalping'],
                avoid_strategies=['news_trading']  # Notícias asiáticas menos impacto
            ),
            'description': 'Tokyo - Liquidez moderada (JPY focus)',
            'volatility': 'low',
            'best_pairs': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY']
        },
        
        # ═══════════════════════════════════════════════════════════════
        # 🇬🇧 LONDON (07:00 - 16:00 UTC)
        # Alta liquidez, movimentos fortes, spreads apertados
        # ═══════════════════════════════════════════════════════════════
        'london': {
            'start_utc': time(7, 0),
            'end_utc': time(16, 0),
            'params': SessionParams(
                mode=TradingMode.NORMAL,
                lot_multiplier=1.0,         # Lote normal
                confidence_boost=0.0,       # Sem ajuste
                max_positions=2,            # 2 posições
                cycle_multiplier=1.0,       # Ciclo normal
                sl_multiplier=1.0,          # SL normal
                tp_multiplier=1.0,          # TP normal
                spread_tolerance=1.0,       # Tolerância normal
                strategies_enabled=['trend_following', 'breakout', 'scalping', 
                                    'range_trading', 'mean_reversion', 'news_trading'],
                avoid_strategies=[]
            ),
            'description': 'London - Alta liquidez',
            'volatility': 'high',
            'best_pairs': ['EURUSD', 'GBPUSD', 'XAUUSD', 'EURGBP']
        },
        
        # ═══════════════════════════════════════════════════════════════
        # 🇺🇸 NEW YORK (12:00 - 21:00 UTC)
        # Alta liquidez, volatilidade em notícias US
        # ═══════════════════════════════════════════════════════════════
        'new_york': {
            'start_utc': time(12, 0),
            'end_utc': time(21, 0),
            'params': SessionParams(
                mode=TradingMode.NORMAL,
                lot_multiplier=1.0,
                confidence_boost=0.0,
                max_positions=2,
                cycle_multiplier=1.0,
                sl_multiplier=1.0,
                tp_multiplier=1.0,
                spread_tolerance=1.0,
                strategies_enabled=['trend_following', 'breakout', 'scalping',
                                    'range_trading', 'mean_reversion', 'news_trading'],
                avoid_strategies=[]
            ),
            'description': 'New York - Alta liquidez',
            'volatility': 'high',
            'best_pairs': ['EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY', 'USDCAD']
        },
        
        # ═══════════════════════════════════════════════════════════════
        # 🔥 LONDON-NY OVERLAP (12:00 - 16:00 UTC)
        # MÁXIMA liquidez - melhor momento para operar
        # ═══════════════════════════════════════════════════════════════
        'london_ny_overlap': {
            'start_utc': time(12, 0),
            'end_utc': time(16, 0),
            'params': SessionParams(
                mode=TradingMode.AGGRESSIVE,
                lot_multiplier=1.2,         # +20% no lote
                confidence_boost=-0.05,     # -5% confiança (mais oportunidades)
                max_positions=3,            # Até 3 posições
                cycle_multiplier=0.8,       # Ciclos 20% mais rápidos
                sl_multiplier=0.9,          # SL 10% mais apertado
                tp_multiplier=1.2,          # TP 20% maior (capturar moves)
                spread_tolerance=0.8,       # Exigir spread mais apertado
                strategies_enabled=['trend_following', 'breakout', 'scalping',
                                    'news_trading'],
                avoid_strategies=['range_trading']  # Não é hora de range
            ),
            'description': 'London-NY Overlap - MÁXIMA liquidez',
            'volatility': 'very_high',
            'best_pairs': ['EURUSD', 'GBPUSD', 'XAUUSD']
        },
        
        # ═══════════════════════════════════════════════════════════════
        # 🌙 TOKYO-LONDON OVERLAP (07:00 - 09:00 UTC)
        # Transição interessante, movimentos iniciais de London
        # ═══════════════════════════════════════════════════════════════
        'tokyo_london_overlap': {
            'start_utc': time(7, 0),
            'end_utc': time(9, 0),
            'params': SessionParams(
                mode=TradingMode.NORMAL,
                lot_multiplier=0.9,
                confidence_boost=0.0,
                max_positions=2,
                cycle_multiplier=1.0,
                sl_multiplier=1.1,          # SL levemente maior (transição)
                tp_multiplier=1.0,
                spread_tolerance=1.2,
                strategies_enabled=['trend_following', 'breakout', 'mean_reversion'],
                avoid_strategies=['scalping']  # Volatilidade ainda instável
            ),
            'description': 'Tokyo-London Overlap - Transição',
            'volatility': 'medium',
            'best_pairs': ['EURUSD', 'GBPUSD', 'USDJPY']
        }
    }
    
    # Ajustes por símbolo
    SYMBOL_ADJUSTMENTS = {
        'XAUUSD': {
            'lot_multiplier': 0.5,      # Gold é mais volátil
            'sl_multiplier': 1.3,       # SL 30% maior
            'best_sessions': ['london', 'new_york', 'london_ny_overlap'],
            'avoid_sessions': ['sydney']
        },
        'EURUSD': {
            'lot_multiplier': 1.0,
            'sl_multiplier': 1.0,
            'best_sessions': ['london', 'new_york', 'london_ny_overlap'],
            'avoid_sessions': []
        },
        'GBPUSD': {
            'lot_multiplier': 0.9,      # GBP mais volátil que EUR
            'sl_multiplier': 1.1,
            'best_sessions': ['london', 'london_ny_overlap'],
            'avoid_sessions': ['sydney', 'tokyo']
        },
        'USDJPY': {
            'lot_multiplier': 1.0,
            'sl_multiplier': 1.0,
            'best_sessions': ['tokyo', 'new_york', 'tokyo_london_overlap'],
            'avoid_sessions': []
        }
    }
    
    def __init__(self, config: Dict = None):
        """Inicializa Adaptive Trading Manager"""
        self.config = config or {}
        self.timezone = pytz.UTC
        
        # Cache de sessão atual
        self._current_session = None
        self._session_cache_time = None
        self._cache_duration = timedelta(minutes=5)
        
        logger.info("🔄 AdaptiveTradingManager inicializado")
        logger.info("📊 Operação 24h com adaptação de liquidez ativa")
    
    def get_current_session(self) -> Tuple[str, Dict]:
        """
        Retorna sessão atual e sua configuração
        
        Returns:
            Tuple[str, Dict]: (nome_sessao, config_sessao)
        """
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        # Verificar overlaps primeiro (maior prioridade)
        for session_name in ['london_ny_overlap', 'tokyo_london_overlap']:
            session = self.SESSION_CONFIGS[session_name]
            if self._is_time_in_range(current_time, session['start_utc'], session['end_utc']):
                return session_name, session
        
        # Verificar sessões principais
        for session_name in ['london', 'new_york', 'tokyo', 'sydney']:
            session = self.SESSION_CONFIGS[session_name]
            if self._is_time_in_range(current_time, session['start_utc'], session['end_utc']):
                return session_name, session
        
        # Fallback para Sydney (off-hours)
        return 'sydney', self.SESSION_CONFIGS['sydney']
    
    def _is_time_in_range(self, current: time, start: time, end: time) -> bool:
        """Verifica se horário está no range (suporta overnight)"""
        if start <= end:
            return start <= current <= end
        else:
            # Range overnight (ex: 21:00 - 06:00)
            return current >= start or current <= end
    
    def get_session_params(self, symbol: str = None) -> SessionParams:
        """
        Retorna parâmetros adaptados para a sessão atual
        
        Args:
            symbol: Símbolo para ajustes específicos
            
        Returns:
            SessionParams com ajustes aplicados
        """
        session_name, session_config = self.get_current_session()
        params = session_config['params']
        
        # Se tiver símbolo, aplicar ajustes específicos
        if symbol and symbol in self.SYMBOL_ADJUSTMENTS:
            adj = self.SYMBOL_ADJUSTMENTS[symbol]
            
            # Verificar se símbolo deve evitar esta sessão
            if session_name in adj.get('avoid_sessions', []):
                # Retornar modo MINIMAL para sessões ruins
                return SessionParams(
                    mode=TradingMode.MINIMAL,
                    lot_multiplier=0.3,
                    confidence_boost=0.15,
                    max_positions=1,
                    cycle_multiplier=3.0,
                    sl_multiplier=2.0,
                    tp_multiplier=1.5,
                    spread_tolerance=3.0,
                    strategies_enabled=['range_trading'],
                    avoid_strategies=['breakout', 'trend_following', 'news_trading', 'scalping']
                )
            
            # Aplicar multiplicadores do símbolo
            return SessionParams(
                mode=params.mode,
                lot_multiplier=params.lot_multiplier * adj.get('lot_multiplier', 1.0),
                confidence_boost=params.confidence_boost,
                max_positions=params.max_positions,
                cycle_multiplier=params.cycle_multiplier,
                sl_multiplier=params.sl_multiplier * adj.get('sl_multiplier', 1.0),
                tp_multiplier=params.tp_multiplier,
                spread_tolerance=params.spread_tolerance,
                strategies_enabled=params.strategies_enabled,
                avoid_strategies=params.avoid_strategies
            )
        
        return params
    
    def should_trade(self, symbol: str, strategy_name: str) -> Tuple[bool, str]:
        """
        Verifica se deve operar baseado na sessão atual
        
        Returns:
            Tuple[bool, str]: (pode_operar, motivo)
        """
        now = datetime.now(self.timezone)
        
        # Verificar fim de semana
        if now.weekday() >= 5:  # Sábado ou Domingo
            if now.weekday() == 6 and now.hour < 22:  # Domingo antes das 22:00 UTC
                return False, "Mercado fechado (fim de semana)"
            elif now.weekday() == 5:  # Sábado
                return False, "Mercado fechado (sábado)"
        
        # Verificar sexta após 21:00 UTC
        if now.weekday() == 4 and now.hour >= 21:
            return False, "Mercado fechando (sexta >21:00 UTC)"
        
        session_name, session_config = self.get_current_session()
        params = session_config['params']
        
        # Verificar se estratégia está na lista de evitar
        if strategy_name.lower() in [s.lower() for s in params.avoid_strategies]:
            return False, f"{strategy_name} não recomendada na sessão {session_name}"
        
        # Verificar ajustes de símbolo
        if symbol in self.SYMBOL_ADJUSTMENTS:
            adj = self.SYMBOL_ADJUSTMENTS[symbol]
            if session_name in adj.get('avoid_sessions', []):
                return False, f"{symbol} não recomendado na sessão {session_name}"
        
        return True, f"OK - {session_name} ({params.mode.value})"
    
    def adjust_order_params(self, 
                            symbol: str,
                            strategy_name: str,
                            volume: float,
                            sl_distance: float,
                            tp_distance: float,
                            min_confidence: float) -> Dict[str, Any]:
        """
        Ajusta parâmetros de ordem baseado na sessão
        
        Args:
            symbol: Símbolo
            strategy_name: Nome da estratégia
            volume: Volume original
            sl_distance: Distância SL original (pips)
            tp_distance: Distância TP original (pips)
            min_confidence: Confiança mínima original
            
        Returns:
            Dict com parâmetros ajustados
        """
        params = self.get_session_params(symbol)
        session_name, _ = self.get_current_session()
        
        adjusted = {
            'volume': round(volume * params.lot_multiplier, 2),
            'sl_distance': round(sl_distance * params.sl_multiplier, 1),
            'tp_distance': round(tp_distance * params.tp_multiplier, 1),
            'min_confidence': min(0.95, max(0.5, min_confidence + params.confidence_boost)),
            'max_positions': params.max_positions,
            'cycle_seconds_multiplier': params.cycle_multiplier,
            'spread_tolerance': params.spread_tolerance,
            'mode': params.mode.value,
            'session': session_name
        }
        
        logger.debug(
            f"[{strategy_name}@{symbol}] Parâmetros ajustados: "
            f"vol={volume}→{adjusted['volume']}, "
            f"SL={sl_distance}→{adjusted['sl_distance']}, "
            f"TP={tp_distance}→{adjusted['tp_distance']}, "
            f"conf={min_confidence:.0%}→{adjusted['min_confidence']:.0%}"
        )
        
        return adjusted
    
    def get_session_summary(self) -> Dict:
        """Retorna resumo da sessão atual"""
        session_name, session_config = self.get_current_session()
        params = session_config['params']
        now = datetime.now(self.timezone)
        
        return {
            'session': session_name,
            'description': session_config['description'],
            'mode': params.mode.value,
            'volatility': session_config.get('volatility', 'unknown'),
            'best_pairs': session_config.get('best_pairs', []),
            'strategies_enabled': params.strategies_enabled,
            'strategies_avoided': params.avoid_strategies,
            'lot_multiplier': params.lot_multiplier,
            'max_positions': params.max_positions,
            'timestamp_utc': now.isoformat()
        }
    
    def log_session_status(self):
        """Loga status da sessão atual"""
        summary = self.get_session_summary()
        
        mode_emoji = {
            'aggressive': '🔥',
            'normal': '✅',
            'conservative': '⚠️',
            'minimal': '🐌',
            'closed': '🔴'
        }
        
        emoji = mode_emoji.get(summary['mode'], '❓')
        
        logger.info("═" * 60)
        logger.info(f"{emoji} SESSÃO ATUAL: {summary['session'].upper()}")
        logger.info(f"   📝 {summary['description']}")
        logger.info(f"   🎚️  Modo: {summary['mode']} | Volatilidade: {summary['volatility']}")
        logger.info(f"   📊 Lote: {summary['lot_multiplier']}x | Max Posições: {summary['max_positions']}")
        logger.info(f"   ✅ Estratégias: {', '.join(summary['strategies_enabled'])}")
        if summary['strategies_avoided']:
            logger.info(f"   ❌ Evitar: {', '.join(summary['strategies_avoided'])}")
        logger.info(f"   💹 Melhores pares: {', '.join(summary['best_pairs'])}")
        logger.info("═" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# Funções auxiliares para integração rápida
# ═══════════════════════════════════════════════════════════════════════════

_adaptive_manager = None

def get_adaptive_manager(config: Dict = None) -> AdaptiveTradingManager:
    """Retorna instância singleton do AdaptiveTradingManager"""
    global _adaptive_manager
    if _adaptive_manager is None:
        _adaptive_manager = AdaptiveTradingManager(config)
    return _adaptive_manager
