"""
Trading Session Manager
Gerencia horários de trading baseado em sessões de mercado

Sessões:
- Sydney: 22:00-07:00 UTC (baixa liquidez)
- Tokyo: 00:00-09:00 UTC (média liquidez)
- London: 08:00-17:00 UTC (alta liquidez)
- New York: 13:00-22:00 UTC (alta liquidez)

Melhores horários:
- London/NY overlap: 13:00-17:00 UTC (máxima liquidez)
- Evitar: 21:00-00:00 UTC (transição)
"""
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from loguru import logger
import pytz


class TradingSession(Enum):
    """Sessões de trading"""
    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    CLOSED = "closed"


class SessionQuality(Enum):
    """Qualidade da sessão para trading"""
    EXCELLENT = "excellent"  # London/NY overlap
    GOOD = "good"           # London ou NY
    MODERATE = "moderate"   # Tokyo
    POOR = "poor"           # Sydney ou transição
    CLOSED = "closed"       # Mercado fechado


class TradingSessionManager:
    """
    Gerenciador de sessões de trading
    
    Funcionalidades:
    - Identificar sessão atual
    - Verificar qualidade do horário
    - Filtrar operações por sessão
    - Ajustar parâmetros por sessão
    """
    
    # Definição das sessões em UTC
    SESSIONS = {
        TradingSession.SYDNEY: {
            "start": time(22, 0),   # 22:00 UTC (dia anterior)
            "end": time(7, 0),      # 07:00 UTC
            "quality": SessionQuality.POOR,
            "description": "Sydney - Baixa liquidez",
            "volatility_factor": 0.6,
            "spread_factor": 1.5,
        },
        TradingSession.TOKYO: {
            "start": time(0, 0),    # 00:00 UTC
            "end": time(9, 0),      # 09:00 UTC
            "quality": SessionQuality.MODERATE,
            "description": "Tokyo - Média liquidez",
            "volatility_factor": 0.8,
            "spread_factor": 1.2,
        },
        TradingSession.LONDON: {
            "start": time(8, 0),    # 08:00 UTC
            "end": time(17, 0),     # 17:00 UTC
            "quality": SessionQuality.GOOD,
            "description": "London - Alta liquidez",
            "volatility_factor": 1.2,
            "spread_factor": 0.8,
        },
        TradingSession.NEW_YORK: {
            "start": time(13, 0),   # 13:00 UTC
            "end": time(22, 0),     # 22:00 UTC
            "quality": SessionQuality.GOOD,
            "description": "New York - Alta liquidez",
            "volatility_factor": 1.3,
            "spread_factor": 0.9,
        },
    }
    
    # Overlap London/NY (melhor período)
    LONDON_NY_OVERLAP = {
        "start": time(13, 0),   # 13:00 UTC
        "end": time(17, 0),     # 17:00 UTC
        "quality": SessionQuality.EXCELLENT,
        "description": "London/NY Overlap - Máxima liquidez",
        "volatility_factor": 1.5,
        "spread_factor": 0.7,
    }
    
    # Períodos a evitar
    AVOID_PERIODS = [
        {
            "start": time(21, 0),
            "end": time(23, 59),
            "reason": "Transição NY/Sydney - Baixa liquidez",
        },
        {
            "start": time(0, 0),
            "end": time(0, 30),
            "reason": "Início de dia - Spreads altos",
        },
    ]
    
    # Configurações por símbolo
    SYMBOL_PREFERENCES = {
        "XAUUSD": {
            "best_sessions": [TradingSession.LONDON, TradingSession.NEW_YORK],
            "avoid_sessions": [TradingSession.SYDNEY],
            "min_quality": SessionQuality.MODERATE,
        },
        "EURUSD": {
            "best_sessions": [TradingSession.LONDON, TradingSession.NEW_YORK],
            "avoid_sessions": [],
            "min_quality": SessionQuality.MODERATE,
        },
        "GBPUSD": {
            "best_sessions": [TradingSession.LONDON],
            "avoid_sessions": [TradingSession.SYDNEY],
            "min_quality": SessionQuality.MODERATE,
        },
        "USDJPY": {
            "best_sessions": [TradingSession.TOKYO, TradingSession.NEW_YORK],
            "avoid_sessions": [TradingSession.SYDNEY],
            "min_quality": SessionQuality.MODERATE,
        },
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Inicializa o gerenciador de sessões
        
        Args:
            config: Configuração opcional
        """
        self.config = config or {}
        self.timezone = pytz.UTC
        
        # Configurações do config
        session_config = self.config.get('trading_sessions', {})
        self.enabled = session_config.get('enabled', True)
        self.strict_mode = session_config.get('strict_mode', False)
        self.allow_overlap_only = session_config.get('allow_overlap_only', False)
        
        logger.info(
            f"📅 Trading Session Manager inicializado | "
            f"Enabled: {self.enabled} | "
            f"Strict: {self.strict_mode}"
        )
    
    def get_current_time_utc(self) -> datetime:
        """Retorna horário atual em UTC"""
        return datetime.now(self.timezone)
    
    def _is_time_in_range(
        self,
        current: time,
        start: time,
        end: time
    ) -> bool:
        """Verifica se horário está no range (considerando virada de meia-noite)"""
        if start <= end:
            return start <= current <= end
        else:  # Range cruza meia-noite
            return current >= start or current <= end
    
    def get_active_sessions(
        self,
        at_time: Optional[datetime] = None
    ) -> List[TradingSession]:
        """
        Retorna lista de sessões ativas no momento
        
        Args:
            at_time: Horário para verificar (default: agora)
            
        Returns:
            Lista de sessões ativas
        """
        if at_time is None:
            at_time = self.get_current_time_utc()
        
        current_time = at_time.time()
        active = []
        
        for session, info in self.SESSIONS.items():
            if self._is_time_in_range(current_time, info["start"], info["end"]):
                active.append(session)
        
        return active
    
    def is_london_ny_overlap(self, at_time: Optional[datetime] = None) -> bool:
        """Verifica se está no período de overlap London/NY"""
        if at_time is None:
            at_time = self.get_current_time_utc()
        
        current_time = at_time.time()
        return self._is_time_in_range(
            current_time,
            self.LONDON_NY_OVERLAP["start"],
            self.LONDON_NY_OVERLAP["end"]
        )
    
    def get_session_quality(
        self,
        at_time: Optional[datetime] = None
    ) -> Tuple[SessionQuality, str]:
        """
        Retorna qualidade da sessão atual
        
        Returns:
            Tuple[SessionQuality, descrição]
        """
        if at_time is None:
            at_time = self.get_current_time_utc()
        
        # Verificar se é fim de semana
        if at_time.weekday() >= 5:  # Sábado ou Domingo
            # Mercado forex abre domingo 22:00 UTC
            if at_time.weekday() == 6 and at_time.time() >= time(22, 0):
                pass  # Mercado aberto
            else:
                return SessionQuality.CLOSED, "Mercado fechado (fim de semana)"
        
        # Verificar overlap London/NY (melhor período)
        if self.is_london_ny_overlap(at_time):
            return (
                SessionQuality.EXCELLENT,
                self.LONDON_NY_OVERLAP["description"]
            )
        
        # Verificar períodos a evitar
        current_time = at_time.time()
        for period in self.AVOID_PERIODS:
            if self._is_time_in_range(current_time, period["start"], period["end"]):
                return SessionQuality.POOR, period["reason"]
        
        # Verificar sessões ativas
        active_sessions = self.get_active_sessions(at_time)
        
        if not active_sessions:
            return SessionQuality.CLOSED, "Nenhuma sessão ativa"
        
        # Retornar a melhor qualidade entre as sessões ativas
        best_quality = SessionQuality.POOR
        best_description = ""
        
        for session in active_sessions:
            info = self.SESSIONS[session]
            quality = info["quality"]
            
            if self._quality_rank(quality) > self._quality_rank(best_quality):
                best_quality = quality
                best_description = info["description"]
        
        return best_quality, best_description
    
    def _quality_rank(self, quality: SessionQuality) -> int:
        """Retorna ranking numérico da qualidade"""
        ranks = {
            SessionQuality.CLOSED: 0,
            SessionQuality.POOR: 1,
            SessionQuality.MODERATE: 2,
            SessionQuality.GOOD: 3,
            SessionQuality.EXCELLENT: 4,
        }
        return ranks.get(quality, 0)
    
    def get_session_factors(
        self,
        at_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Retorna fatores de ajuste baseados na sessão atual
        
        Returns:
            Dict com fatores de volatilidade e spread
        """
        if at_time is None:
            at_time = self.get_current_time_utc()
        
        # Overlap tem prioridade
        if self.is_london_ny_overlap(at_time):
            return {
                "volatility_factor": self.LONDON_NY_OVERLAP["volatility_factor"],
                "spread_factor": self.LONDON_NY_OVERLAP["spread_factor"],
                "confidence_boost": 0.1,  # +10% confiança
            }
        
        # Média ponderada das sessões ativas
        active = self.get_active_sessions(at_time)
        
        if not active:
            return {
                "volatility_factor": 0.5,
                "spread_factor": 2.0,
                "confidence_boost": -0.2,  # -20% confiança
            }
        
        total_vol = 0
        total_spread = 0
        
        for session in active:
            info = self.SESSIONS[session]
            total_vol += info["volatility_factor"]
            total_spread += info["spread_factor"]
        
        n = len(active)
        
        return {
            "volatility_factor": total_vol / n,
            "spread_factor": total_spread / n,
            "confidence_boost": 0.0,
        }
    
    def can_trade(
        self,
        symbol: str,
        strategy_name: Optional[str] = None,
        at_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verifica se é permitido operar no momento atual
        
        Args:
            symbol: Símbolo (ex: XAUUSD)
            strategy_name: Nome da estratégia (opcional)
            at_time: Horário para verificar
            
        Returns:
            Dict com 'allowed', 'reason', 'quality', 'factors'
        """
        if not self.enabled:
            return {
                "allowed": True,
                "reason": "Filtro de sessão desabilitado",
                "quality": SessionQuality.GOOD,
                "factors": {"volatility_factor": 1.0, "spread_factor": 1.0},
            }
        
        if at_time is None:
            at_time = self.get_current_time_utc()
        
        # Verificar fim de semana
        if at_time.weekday() >= 5:
            if not (at_time.weekday() == 6 and at_time.time() >= time(22, 0)):
                return {
                    "allowed": False,
                    "reason": "Mercado fechado (fim de semana)",
                    "quality": SessionQuality.CLOSED,
                    "factors": {},
                }
        
        # Obter qualidade atual
        quality, description = self.get_session_quality(at_time)
        factors = self.get_session_factors(at_time)
        
        # Modo strict: só permite GOOD ou EXCELLENT
        if self.strict_mode:
            if quality not in [SessionQuality.GOOD, SessionQuality.EXCELLENT]:
                return {
                    "allowed": False,
                    "reason": f"Modo strict ativo - {description}",
                    "quality": quality,
                    "factors": factors,
                }
        
        # Modo overlap only: só permite London/NY overlap
        if self.allow_overlap_only:
            if not self.is_london_ny_overlap(at_time):
                return {
                    "allowed": False,
                    "reason": "Permitido apenas durante London/NY overlap (13:00-17:00 UTC)",
                    "quality": quality,
                    "factors": factors,
                }
        
        # Verificar preferências do símbolo
        symbol_prefs = self.SYMBOL_PREFERENCES.get(symbol, {})
        min_quality = symbol_prefs.get("min_quality", SessionQuality.POOR)
        avoid_sessions = symbol_prefs.get("avoid_sessions", [])
        
        # Verificar qualidade mínima
        if self._quality_rank(quality) < self._quality_rank(min_quality):
            return {
                "allowed": False,
                "reason": f"{symbol} requer qualidade mínima {min_quality.value}, atual: {quality.value}",
                "quality": quality,
                "factors": factors,
            }
        
        # Verificar sessões a evitar
        active_sessions = self.get_active_sessions(at_time)
        for session in active_sessions:
            if session in avoid_sessions:
                if len(active_sessions) == 1:  # Só esta sessão está ativa
                    return {
                        "allowed": False,
                        "reason": f"{symbol} deve evitar sessão {session.value}",
                        "quality": quality,
                        "factors": factors,
                    }
        
        # Estratégias específicas
        if strategy_name:
            # Scalping: só em sessões de alta liquidez
            if strategy_name.lower() == "scalping":
                if quality not in [SessionQuality.GOOD, SessionQuality.EXCELLENT]:
                    return {
                        "allowed": False,
                        "reason": f"Scalping requer alta liquidez, atual: {description}",
                        "quality": quality,
                        "factors": factors,
                    }
            
            # News Trading: evitar períodos de transição
            if strategy_name.lower() == "news_trading":
                current_time = at_time.time()
                for period in self.AVOID_PERIODS:
                    if self._is_time_in_range(current_time, period["start"], period["end"]):
                        return {
                            "allowed": False,
                            "reason": f"News Trading: {period['reason']}",
                            "quality": quality,
                            "factors": factors,
                        }
        
        # Tudo OK
        return {
            "allowed": True,
            "reason": description,
            "quality": quality,
            "factors": factors,
            "active_sessions": [s.value for s in active_sessions],
            "is_overlap": self.is_london_ny_overlap(at_time),
        }
    
    def get_next_good_session(
        self,
        symbol: str = "XAUUSD",
        from_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calcula quando será a próxima sessão de boa qualidade
        
        Returns:
            Dict com 'session', 'starts_in', 'start_time'
        """
        if from_time is None:
            from_time = self.get_current_time_utc()
        
        # Procurar nas próximas 24 horas
        check_time = from_time
        
        for _ in range(96):  # A cada 15 minutos, por 24 horas
            check_time += timedelta(minutes=15)
            
            result = self.can_trade(symbol, at_time=check_time)
            
            if result["allowed"] and result["quality"] in [SessionQuality.GOOD, SessionQuality.EXCELLENT]:
                wait_minutes = (check_time - from_time).total_seconds() / 60
                
                return {
                    "found": True,
                    "start_time": check_time,
                    "wait_minutes": round(wait_minutes),
                    "quality": result["quality"].value,
                    "session": result.get("reason", ""),
                }
        
        return {
            "found": False,
            "reason": "Nenhuma sessão boa nas próximas 24 horas",
        }
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo completo da sessão atual
        
        Returns:
            Dict com todas as informações da sessão
        """
        now = self.get_current_time_utc()
        quality, description = self.get_session_quality(now)
        factors = self.get_session_factors(now)
        active = self.get_active_sessions(now)
        
        return {
            "current_time_utc": now.strftime("%Y-%m-%d %H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "active_sessions": [s.value for s in active],
            "quality": quality.value,
            "description": description,
            "is_london_ny_overlap": self.is_london_ny_overlap(now),
            "factors": factors,
            "is_weekend": now.weekday() >= 5,
            "trading_enabled": self.enabled,
            "strict_mode": self.strict_mode,
        }


# Singleton global
_session_manager: Optional[TradingSessionManager] = None


def get_session_manager(config: Optional[Dict] = None) -> TradingSessionManager:
    """Obtém instância singleton do Session Manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = TradingSessionManager(config)
    return _session_manager


# Exemplo de uso:
"""
from core.trading_session_manager import get_session_manager, SessionQuality

session_mgr = get_session_manager(config)

# Verificar se pode operar
result = session_mgr.can_trade("XAUUSD", strategy_name="scalping")
if not result["allowed"]:
    logger.warning(f"Trading bloqueado: {result['reason']}")
    return

# Obter fatores de ajuste
factors = result["factors"]
adjusted_sl = base_sl * factors["volatility_factor"]

# Resumo da sessão
summary = session_mgr.get_session_summary()
logger.info(f"Sessão: {summary['active_sessions']} - {summary['quality']}")
"""
