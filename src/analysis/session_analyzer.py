"""
Session Analyzer
Analisa e otimiza trading por sessão de mercado (Asia, London, NY)
"""

from datetime import datetime, time, timedelta
from typing import Dict, Optional, Tuple
from enum import Enum
import pytz
from loguru import logger


class MarketSession(Enum):
    """Sessões de mercado"""
    ASIA = "asia"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP_LONDON_NY = "overlap_london_ny"
    OVERLAP_ASIA_LONDON = "overlap_asia_london"
    OFF_HOURS = "off_hours"


class SessionAnalyzer:
    """
    Analisa características de cada sessão de mercado
    e otimiza estratégias baseado no horário
    """
    
    # Horários das sessões (UTC)
    SESSIONS = {
        MarketSession.ASIA: {
            'start': time(0, 0),   # 00:00 UTC
            'end': time(9, 0),     # 09:00 UTC
            'volatility': 'low',
            'best_pairs': ['USDJPY', 'AUDUSD', 'NZDUSD'],
            'characteristics': {
                'trend_strength': 0.3,
                'breakout_probability': 0.2,
                'range_probability': 0.7,
                'avg_pips_move': {'XAUUSD': 8, 'EURUSD': 20, 'GBPUSD': 25, 'USDJPY': 25}
            }
        },
        MarketSession.LONDON: {
            'start': time(7, 0),   # 07:00 UTC
            'end': time(16, 0),    # 16:00 UTC
            'volatility': 'high',
            'best_pairs': ['EURUSD', 'GBPUSD', 'XAUUSD'],
            'characteristics': {
                'trend_strength': 0.7,
                'breakout_probability': 0.6,
                'range_probability': 0.3,
                'avg_pips_move': {'XAUUSD': 25, 'EURUSD': 50, 'GBPUSD': 60, 'USDJPY': 40}
            }
        },
        MarketSession.NEW_YORK: {
            'start': time(12, 0),  # 12:00 UTC
            'end': time(21, 0),    # 21:00 UTC
            'volatility': 'high',
            'best_pairs': ['EURUSD', 'GBPUSD', 'XAUUSD', 'USDJPY'],
            'characteristics': {
                'trend_strength': 0.8,
                'breakout_probability': 0.5,
                'range_probability': 0.2,
                'avg_pips_move': {'XAUUSD': 30, 'EURUSD': 45, 'GBPUSD': 55, 'USDJPY': 45}
            }
        },
        MarketSession.OVERLAP_LONDON_NY: {
            'start': time(12, 0),  # 12:00 UTC
            'end': time(16, 0),    # 16:00 UTC
            'volatility': 'very_high',
            'best_pairs': ['EURUSD', 'GBPUSD', 'XAUUSD'],
            'characteristics': {
                'trend_strength': 0.9,
                'breakout_probability': 0.7,
                'range_probability': 0.1,
                'avg_pips_move': {'XAUUSD': 40, 'EURUSD': 70, 'GBPUSD': 80, 'USDJPY': 50}
            }
        },
        MarketSession.OVERLAP_ASIA_LONDON: {
            'start': time(7, 0),   # 07:00 UTC
            'end': time(9, 0),     # 09:00 UTC
            'volatility': 'medium',
            'best_pairs': ['EURUSD', 'GBPUSD', 'USDJPY'],
            'characteristics': {
                'trend_strength': 0.5,
                'breakout_probability': 0.5,
                'range_probability': 0.4,
                'avg_pips_move': {'XAUUSD': 15, 'EURUSD': 35, 'GBPUSD': 40, 'USDJPY': 35}
            }
        }
    }
    
    # Dias importantes (menor liquidez)
    LOW_LIQUIDITY_DAYS = [
        (1, 1),   # Ano Novo
        (7, 4),   # Independence Day
        (12, 25), # Natal
        (12, 26), # Boxing Day
    ]
    
    def __init__(self, config: dict = None):
        """Inicializa Session Analyzer"""
        self.config = config or {}
        self.timezone = pytz.UTC
        
        # Estatísticas por sessão
        self.session_stats: Dict[str, Dict] = {
            session.value: {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'profit': 0.0,
                'avg_duration': 0
            }
            for session in MarketSession
        }
        
        logger.info("SessionAnalyzer inicializado")
    
    def get_current_session(self) -> MarketSession:
        """Retorna a sessão de mercado atual"""
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        # Verificar overlaps primeiro (maior prioridade)
        overlap_london_ny = self.SESSIONS[MarketSession.OVERLAP_LONDON_NY]
        if overlap_london_ny['start'] <= current_time <= overlap_london_ny['end']:
            return MarketSession.OVERLAP_LONDON_NY
        
        overlap_asia_london = self.SESSIONS[MarketSession.OVERLAP_ASIA_LONDON]
        if overlap_asia_london['start'] <= current_time <= overlap_asia_london['end']:
            return MarketSession.OVERLAP_ASIA_LONDON
        
        # Verificar sessões principais
        for session in [MarketSession.LONDON, MarketSession.NEW_YORK, MarketSession.ASIA]:
            session_info = self.SESSIONS[session]
            if session_info['start'] <= current_time <= session_info['end']:
                return session
        
        return MarketSession.OFF_HOURS
    
    def get_session_info(self, session: MarketSession = None) -> Dict:
        """Retorna informações da sessão"""
        if session is None:
            session = self.get_current_session()
        
        return {
            'session': session.value,
            **self.SESSIONS.get(session, {})
        }
    
    def is_good_time_for_symbol(self, symbol: str) -> Tuple[bool, float, str]:
        """
        Verifica se é um bom momento para operar o símbolo
        
        Returns:
            Tuple[bool, float, str]: (is_good, score, reason)
        """
        session = self.get_current_session()
        session_info = self.SESSIONS.get(session, {})
        
        # Off hours - não recomendado
        if session == MarketSession.OFF_HOURS:
            return False, 0.2, "Fora do horário de mercado principal"
        
        # Verificar se o símbolo é bom para esta sessão
        best_pairs = session_info.get('best_pairs', [])
        
        # Normalizar símbolo
        symbol_clean = symbol.replace('.', '').upper()
        
        if symbol_clean in best_pairs:
            score = 1.0
            reason = f"{symbol} é ideal para sessão {session.value}"
        elif session in [MarketSession.OVERLAP_LONDON_NY, MarketSession.LONDON]:
            score = 0.8
            reason = f"Alta liquidez na sessão {session.value}"
        elif session == MarketSession.ASIA and symbol_clean not in ['USDJPY', 'AUDUSD']:
            score = 0.4
            reason = f"{symbol} tem baixa liquidez na sessão Asia"
        else:
            score = 0.6
            reason = f"Liquidez moderada para {symbol}"
        
        # Verificar feriados
        now = datetime.now(self.timezone)
        if (now.month, now.day) in self.LOW_LIQUIDITY_DAYS:
            score *= 0.5
            reason += " (⚠️ Feriado - baixa liquidez)"
        
        # Verificar fim de semana próximo (sexta depois das 20h UTC)
        if now.weekday() == 4 and now.hour >= 20:
            score *= 0.6
            reason += " (⚠️ Fim de semana próximo)"
        
        return score >= 0.5, score, reason
    
    def get_recommended_strategies(self, symbol: str = None) -> Dict[str, float]:
        """
        Retorna estratégias recomendadas para a sessão atual
        
        Returns:
            Dict[str, float]: {strategy_name: weight_multiplier}
        """
        session = self.get_current_session()
        session_info = self.SESSIONS.get(session, {})
        characteristics = session_info.get('characteristics', {})
        
        # Base weights
        weights = {
            'trend_following': 0.5,
            'mean_reversion': 0.5,
            'breakout': 0.5,
            'scalping': 0.5,
            'range_trading': 0.5,
            'news_trading': 0.5
        }
        
        # Ajustar baseado nas características da sessão
        trend_strength = characteristics.get('trend_strength', 0.5)
        breakout_prob = characteristics.get('breakout_probability', 0.5)
        range_prob = characteristics.get('range_probability', 0.5)
        volatility = session_info.get('volatility', 'medium')
        
        # Trend Following
        weights['trend_following'] = 0.3 + (trend_strength * 0.7)
        
        # Breakout
        weights['breakout'] = 0.3 + (breakout_prob * 0.7)
        
        # Range Trading
        weights['range_trading'] = 0.3 + (range_prob * 0.7)
        
        # Mean Reversion - melhor em baixa volatilidade
        if volatility == 'low':
            weights['mean_reversion'] = 0.8
        elif volatility == 'very_high':
            weights['mean_reversion'] = 0.3
        else:
            weights['mean_reversion'] = 0.5
        
        # Scalping - melhor em alta volatilidade com spread apertado
        if volatility in ['high', 'very_high']:
            weights['scalping'] = 0.8
        elif volatility == 'low':
            weights['scalping'] = 0.3
        else:
            weights['scalping'] = 0.5
        
        # News Trading - sempre ativo, mas melhor em London/NY
        if session in [MarketSession.LONDON, MarketSession.NEW_YORK, MarketSession.OVERLAP_LONDON_NY]:
            weights['news_trading'] = 0.9
        else:
            weights['news_trading'] = 0.4
        
        return weights
    
    def get_optimal_lot_multiplier(self, symbol: str) -> float:
        """
        Retorna multiplicador de lote baseado na sessão
        """
        session = self.get_current_session()
        session_info = self.SESSIONS.get(session, {})
        volatility = session_info.get('volatility', 'medium')
        
        if volatility == 'very_high':
            return 0.7  # Reduzir lote
        elif volatility == 'high':
            return 0.9
        elif volatility == 'low':
            return 1.1  # Aumentar lote levemente
        else:
            return 1.0
    
    def get_expected_move(self, symbol: str) -> Optional[float]:
        """Retorna movimento esperado em pips para o símbolo na sessão atual"""
        session = self.get_current_session()
        session_info = self.SESSIONS.get(session, {})
        characteristics = session_info.get('characteristics', {})
        avg_moves = characteristics.get('avg_pips_move', {})
        
        symbol_clean = symbol.replace('.', '').upper()
        return avg_moves.get(symbol_clean)
    
    def get_session_summary(self) -> Dict:
        """Retorna resumo da sessão atual"""
        session = self.get_current_session()
        session_info = self.get_session_info(session)
        
        now = datetime.now(self.timezone)
        
        # Calcular tempo restante na sessão
        end_time = session_info.get('end', time(0, 0))
        end_datetime = datetime.combine(now.date(), end_time)
        end_datetime = self.timezone.localize(end_datetime)
        
        if end_datetime < now:
            end_datetime += timedelta(days=1)
        
        time_remaining = end_datetime - now
        
        return {
            'current_session': session.value,
            'volatility': session_info.get('volatility', 'unknown'),
            'best_pairs': session_info.get('best_pairs', []),
            'time_remaining': str(time_remaining).split('.')[0],
            'recommended_strategies': self.get_recommended_strategies(),
            'timestamp': now.isoformat()
        }
    
    def record_trade(self, session: MarketSession, win: bool, profit: float, duration_minutes: int):
        """Registra resultado de trade para estatísticas da sessão"""
        stats = self.session_stats[session.value]
        stats['trades'] += 1
        
        if win:
            stats['wins'] += 1
        else:
            stats['losses'] += 1
        
        stats['profit'] += profit
        
        # Média móvel da duração
        if stats['avg_duration'] == 0:
            stats['avg_duration'] = duration_minutes
        else:
            stats['avg_duration'] = (stats['avg_duration'] * 0.9) + (duration_minutes * 0.1)
    
    def get_session_performance(self) -> Dict:
        """Retorna performance por sessão"""
        performance = {}
        
        for session_name, stats in self.session_stats.items():
            if stats['trades'] > 0:
                win_rate = stats['wins'] / stats['trades']
                performance[session_name] = {
                    'trades': stats['trades'],
                    'win_rate': round(win_rate * 100, 2),
                    'profit': round(stats['profit'], 2),
                    'avg_duration_min': round(stats['avg_duration'], 1)
                }
        
        return performance
