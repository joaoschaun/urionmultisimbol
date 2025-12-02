"""
Adaptive Time Manager - Gestão Temporal Adaptativa
===================================================

🎯 OBJETIVO:
Gerenciar posições baseado na relação TEMPO vs PERFORMANCE.
Liberar capital de trades "mortos" que não vão a lugar nenhum.

📐 REGRAS PRINCIPAIS:
1. Cada estratégia tem um "tempo esperado" diferente
2. Se trade demora demais SEM lucrar → Fecha
3. Se trade demora demais MAS lucrando → Aperta SL
4. Não interfere em trades que estão performando bem

🔧 LÓGICA:
- Tempo < esperado → HOLD (deixa correr)
- Tempo > 1.5x esperado + lucro > 0.5R → TIGHTEN_SL
- Tempo > 2x esperado + lucro < 0.5R → CLOSE (libera margem)
- Tempo > 3x esperado + qualquer caso → CLOSE ou TIGHTEN forte

💡 COMPLEMENTA O PROFIT PROTECTOR:
- ProfitProtector → Age baseado em LUCRO/DRAWDOWN
- TimeManager → Age baseado em TEMPO/PERFORMANCE
- Ambos trabalham juntos sem conflito!

Autor: João Schaun / Claude
Versão: 1.0
Data: 01/12/2025
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime, timezone, timedelta
from loguru import logger
from dataclasses import dataclass, field
from enum import Enum


class TimeAction(Enum):
    """Ações possíveis baseadas em tempo"""
    HOLD = "hold"                    # Continuar normalmente
    TIGHTEN_SL = "tighten_sl"        # Apertar SL (proteger lucro)
    CLOSE_PARTIAL = "close_partial"  # Fechar parcialmente
    CLOSE_FULL = "close_full"        # Fechar totalmente
    WARN = "warn"                    # Apenas alertar


class TimeStatus(Enum):
    """Status temporal da posição"""
    ON_TIME = "on_time"              # Dentro do tempo esperado
    SLIGHTLY_LATE = "slightly_late"  # 1-1.5x do tempo esperado
    LATE = "late"                    # 1.5-2x do tempo esperado
    VERY_LATE = "very_late"          # 2-3x do tempo esperado
    OVERTIME = "overtime"            # > 3x do tempo esperado


@dataclass
class TimeAnalysis:
    """Resultado da análise temporal"""
    ticket: int
    symbol: str
    strategy: str
    time_open_minutes: float
    expected_time_minutes: float
    time_ratio: float  # time_open / expected
    status: TimeStatus
    action: TimeAction
    reason: str
    current_rr: float = 0.0
    new_sl: Optional[float] = None


class AdaptiveTimeManager:
    """
    Gerencia posições baseado em tempo vs performance
    
    Trabalha em harmonia com ProfitProtector:
    - ProfitProtector cuida de proteção de LUCRO
    - TimeManager cuida de TEMPO excessivo
    """
    
    # ⏱️ Tempos esperados por estratégia (em minutos)
    DEFAULT_EXPECTED_TIMES = {
        'scalping': 5,              # 5 minutos
        'catamilho': 3,             # 3 minutos (ultra-rápido)
        'range_trading': 30,        # 30 minutos
        'mean_reversion': 20,       # 20 minutos
        'trend_following': 120,     # 2 horas
        'breakout': 45,             # 45 minutos
        'news_trading': 10,         # 10 minutos
        'momentum': 15,             # 15 minutos
        'default': 30               # Padrão: 30 minutos
    }
    
    # 📊 Thresholds de RR para decisões
    RR_THRESHOLDS = {
        'profitable': 0.5,      # Acima de 0.5R = lucrativo
        'breakeven': 0.0,       # 0R = empate
        'losing': -0.5,         # Abaixo de -0.5R = perdendo
    }
    
    def __init__(self, config: Dict = None):
        """
        Inicializa Adaptive Time Manager
        
        Args:
            config: Configuração global do sistema
        """
        self.config = config or {}
        self.time_config = self.config.get('time_manager', {})
        
        # Configurações
        self.enabled = self.time_config.get('enabled', True)
        
        # Tempos esperados (pode ser customizado via config)
        self.expected_times = {
            **self.DEFAULT_EXPECTED_TIMES,
            **self.time_config.get('expected_times', {})
        }
        
        # Multiplicadores para ações
        self.slight_late_mult = self.time_config.get('slight_late_multiplier', 1.5)
        self.late_mult = self.time_config.get('late_multiplier', 2.0)
        self.very_late_mult = self.time_config.get('very_late_multiplier', 3.0)
        self.overtime_mult = self.time_config.get('overtime_multiplier', 4.0)
        
        # RR mínimo para cada fase
        self.min_rr_for_late = self.time_config.get('min_rr_for_late', 0.5)
        self.min_rr_for_very_late = self.time_config.get('min_rr_for_very_late', 0.3)
        
        # Tracking de posições
        self.position_warnings: Dict[int, List[datetime]] = {}  # ticket -> lista de warnings
        
        logger.info(f"⏱️ AdaptiveTimeManager inicializado | Enabled: {self.enabled}")
    
    def analyze_position(
        self,
        ticket: int,
        symbol: str,
        strategy: str,
        open_time: datetime,
        entry_price: float,
        current_price: float,
        sl: float,
        position_type: str,  # 'BUY' ou 'SELL'
        current_profit: float = 0.0,
        volume: float = 0.1
    ) -> TimeAnalysis:
        """
        Analisa uma posição e retorna recomendação baseada em tempo
        
        Args:
            ticket: Ticket da posição
            symbol: Símbolo (EURUSD, XAUUSD, etc)
            strategy: Nome da estratégia
            open_time: Quando a posição foi aberta
            entry_price: Preço de entrada
            current_price: Preço atual
            sl: Stop Loss atual
            position_type: 'BUY' ou 'SELL'
            current_profit: Lucro atual em $
            volume: Volume da posição
            
        Returns:
            TimeAnalysis com recomendação
        """
        if not self.enabled:
            return TimeAnalysis(
                ticket=ticket,
                symbol=symbol,
                strategy=strategy,
                time_open_minutes=0,
                expected_time_minutes=0,
                time_ratio=0,
                status=TimeStatus.ON_TIME,
                action=TimeAction.HOLD,
                reason="TimeManager desabilitado"
            )
        
        # Calcular tempo aberto
        now = datetime.now(timezone.utc)
        if open_time.tzinfo is None:
            open_time = open_time.replace(tzinfo=timezone.utc)
        
        time_open = now - open_time
        time_open_minutes = time_open.total_seconds() / 60
        
        # Obter tempo esperado para esta estratégia
        strategy_lower = strategy.lower().replace(' ', '_')
        expected_minutes = self.expected_times.get(
            strategy_lower, 
            self.expected_times['default']
        )
        
        # Calcular ratio de tempo
        time_ratio = time_open_minutes / expected_minutes if expected_minutes > 0 else 0
        
        # Calcular RR atual
        current_rr = self._calculate_rr(
            entry_price, current_price, sl, position_type, current_profit, volume
        )
        
        # Determinar status temporal
        status = self._determine_status(time_ratio)
        
        # Determinar ação baseado em tempo + RR
        action, reason, new_sl = self._determine_action(
            status, current_rr, entry_price, current_price, sl, position_type, time_ratio
        )
        
        # Registrar warning se aplicável
        if action in [TimeAction.WARN, TimeAction.TIGHTEN_SL, TimeAction.CLOSE_PARTIAL]:
            self._record_warning(ticket)
        
        analysis = TimeAnalysis(
            ticket=ticket,
            symbol=symbol,
            strategy=strategy,
            time_open_minutes=round(time_open_minutes, 1),
            expected_time_minutes=expected_minutes,
            time_ratio=round(time_ratio, 2),
            status=status,
            action=action,
            reason=reason,
            current_rr=round(current_rr, 2),
            new_sl=new_sl
        )
        
        # Log se ação necessária
        if action != TimeAction.HOLD:
            logger.info(
                f"⏱️ [{symbol}] #{ticket} | "
                f"Tempo: {time_open_minutes:.0f}min (esperado: {expected_minutes}min) | "
                f"Ratio: {time_ratio:.1f}x | RR: {current_rr:.2f} | "
                f"Ação: {action.value} | {reason}"
            )
        
        return analysis
    
    def _calculate_rr(
        self,
        entry_price: float,
        current_price: float,
        sl: float,
        position_type: str,
        current_profit: float,
        volume: float
    ) -> float:
        """Calcula RR atual baseado no risco inicial"""
        
        # Risco inicial em pips
        risk_pips = abs(entry_price - sl)
        
        if risk_pips == 0:
            return 0.0
        
        # Lucro atual em pips
        if position_type == 'BUY':
            profit_pips = current_price - entry_price
        else:
            profit_pips = entry_price - current_price
        
        # RR = lucro / risco
        rr = profit_pips / risk_pips
        
        return rr
    
    def _determine_status(self, time_ratio: float) -> TimeStatus:
        """Determina status temporal baseado no ratio"""
        
        if time_ratio < self.slight_late_mult:
            return TimeStatus.ON_TIME
        elif time_ratio < self.late_mult:
            return TimeStatus.SLIGHTLY_LATE
        elif time_ratio < self.very_late_mult:
            return TimeStatus.LATE
        elif time_ratio < self.overtime_mult:
            return TimeStatus.VERY_LATE
        else:
            return TimeStatus.OVERTIME
    
    def _determine_action(
        self,
        status: TimeStatus,
        current_rr: float,
        entry_price: float,
        current_price: float,
        sl: float,
        position_type: str,
        time_ratio: float
    ) -> Tuple[TimeAction, str, Optional[float]]:
        """
        Determina ação baseado em status temporal + RR
        
        Retorna: (ação, razão, novo_sl)
        """
        new_sl = None
        
        # 🟢 ON_TIME - Tudo bem, deixa o ProfitProtector cuidar
        if status == TimeStatus.ON_TIME:
            return TimeAction.HOLD, "Tempo dentro do esperado", None
        
        # 🟡 SLIGHTLY_LATE (1-1.5x) - Apenas observar
        if status == TimeStatus.SLIGHTLY_LATE:
            if current_rr < 0:
                return TimeAction.WARN, f"Trade levemente atrasado e no vermelho (RR: {current_rr:.2f})", None
            return TimeAction.HOLD, "Levemente atrasado mas ok", None
        
        # 🟠 LATE (1.5-2x) - Tomar ação se não lucrativo
        if status == TimeStatus.LATE:
            if current_rr >= self.min_rr_for_late:
                # Lucrando → Apertar SL para garantir lucro
                new_sl = self._calculate_protective_sl(
                    entry_price, current_price, sl, position_type, 
                    protection_pct=0.5  # Protege 50% do lucro
                )
                return TimeAction.TIGHTEN_SL, f"Atrasado ({time_ratio:.1f}x) mas lucrando - apertando SL", new_sl
            
            elif current_rr >= 0:
                # Break-even → Mover SL para BE
                new_sl = entry_price
                return TimeAction.TIGHTEN_SL, f"Atrasado ({time_ratio:.1f}x) no BE - movendo SL para entrada", new_sl
            
            else:
                # Perdendo → Alertar
                return TimeAction.WARN, f"Atrasado ({time_ratio:.1f}x) e perdendo (RR: {current_rr:.2f})", None
        
        # 🔴 VERY_LATE (2-3x) - Ação mais agressiva
        if status == TimeStatus.VERY_LATE:
            if current_rr >= self.min_rr_for_very_late:
                # Ainda lucrando → Apertar bastante o SL
                new_sl = self._calculate_protective_sl(
                    entry_price, current_price, sl, position_type,
                    protection_pct=0.7  # Protege 70% do lucro
                )
                return TimeAction.TIGHTEN_SL, f"Muito atrasado ({time_ratio:.1f}x) - protegendo 70% do lucro", new_sl
            
            elif current_rr >= -0.3:
                # Perto de BE → Fecha parcial
                return TimeAction.CLOSE_PARTIAL, f"Muito atrasado ({time_ratio:.1f}x) e estagnado - fechando parcial", None
            
            else:
                # Perdendo muito → Recomenda fechar
                return TimeAction.CLOSE_FULL, f"Muito atrasado ({time_ratio:.1f}x) e perdendo (RR: {current_rr:.2f}) - fechar", None
        
        # ⛔ OVERTIME (> 3x) - Fechar ou apertar muito
        if status == TimeStatus.OVERTIME:
            if current_rr > 0:
                # Ainda positivo → Apertar máximo o SL
                new_sl = self._calculate_protective_sl(
                    entry_price, current_price, sl, position_type,
                    protection_pct=0.9  # Protege 90% do lucro
                )
                return TimeAction.TIGHTEN_SL, f"OVERTIME ({time_ratio:.1f}x) - protegendo 90% do lucro", new_sl
            
            else:
                # Negativo → Fechar
                return TimeAction.CLOSE_FULL, f"OVERTIME ({time_ratio:.1f}x) e negativo - FECHAR para liberar margem", None
        
        return TimeAction.HOLD, "Nenhuma ação necessária", None
    
    def _calculate_protective_sl(
        self,
        entry_price: float,
        current_price: float,
        current_sl: float,
        position_type: str,
        protection_pct: float = 0.5
    ) -> float:
        """
        Calcula novo SL para proteger X% do lucro atual
        
        Args:
            protection_pct: Percentual do lucro a proteger (0.5 = 50%)
        """
        if position_type == 'BUY':
            profit_pips = current_price - entry_price
            if profit_pips <= 0:
                return entry_price  # Move para BE
            
            # Novo SL = entry + (profit * protection)
            new_sl = entry_price + (profit_pips * protection_pct)
            
            # Só move se for mais protetor que SL atual
            return max(new_sl, current_sl) if current_sl else new_sl
        
        else:  # SELL
            profit_pips = entry_price - current_price
            if profit_pips <= 0:
                return entry_price  # Move para BE
            
            # Novo SL = entry - (profit * protection)
            new_sl = entry_price - (profit_pips * protection_pct)
            
            # Só move se for mais protetor que SL atual
            return min(new_sl, current_sl) if current_sl else new_sl
    
    def _record_warning(self, ticket: int):
        """Registra warning para um ticket"""
        if ticket not in self.position_warnings:
            self.position_warnings[ticket] = []
        
        self.position_warnings[ticket].append(datetime.now(timezone.utc))
        
        # Manter apenas últimos 10 warnings
        if len(self.position_warnings[ticket]) > 10:
            self.position_warnings[ticket] = self.position_warnings[ticket][-10:]
    
    def get_warning_count(self, ticket: int) -> int:
        """Retorna quantidade de warnings para um ticket"""
        return len(self.position_warnings.get(ticket, []))
    
    def cleanup(self, ticket: int):
        """Limpa dados de um ticket fechado"""
        if ticket in self.position_warnings:
            del self.position_warnings[ticket]
            logger.debug(f"⏱️ Cleanup TimeManager para ticket #{ticket}")
    
    def get_status_summary(self) -> Dict:
        """Retorna resumo do status do manager"""
        return {
            'enabled': self.enabled,
            'positions_tracked': len(self.position_warnings),
            'expected_times': self.expected_times,
            'thresholds': {
                'slight_late': f'{self.slight_late_mult}x',
                'late': f'{self.late_mult}x',
                'very_late': f'{self.very_late_mult}x',
                'overtime': f'{self.overtime_mult}x'
            }
        }


# Variável para verificar disponibilidade
TIME_MANAGER_AVAILABLE = True
