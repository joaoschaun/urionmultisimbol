"""
Market Hours Manager
Gerencia horários de abertura/fechamento do mercado
MODO 24H: Opera 24/5 com apenas fechamento no fim de semana
"""
from datetime import datetime, time, timedelta
from typing import Dict, Optional, Tuple, Any
from loguru import logger
import pytz


class ForexMarketHours:
    """
    Gerenciador para Forex e CFDs - Opera 24h/5 dias
    Domingo 22:00 UTC até Sexta 22:00 UTC
    SEM pausas diárias (exceto rollover de 1-2 min que ignoramos)
    """
    
    def __init__(self, config: Dict):
        self.config = config
        schedule_config = config.get('schedule', {})
        tz_str = schedule_config.get('timezone', 'UTC')
        self.timezone = pytz.timezone(tz_str)
        
        logger.info("✅ ForexMarketHours: Opera 24/5, SEM pausas diárias")
    
    def get_current_time(self) -> datetime:
        """Retorna hora atual UTC"""
        return datetime.now(pytz.UTC)
    
    def is_market_open(self) -> bool:
        """
        Forex abre Domingo 22:00 UTC, fecha Sexta 22:00 UTC
        Opera 24h durante a semana
        """
        now = self.get_current_time()
        weekday = now.weekday()
        current_hour = now.hour
        
        # Sábado: Fechado
        if weekday == 5:
            return False
        
        # Domingo: Abre 22:00 UTC
        if weekday == 6:
            return current_hour >= 22
        
        # Sexta: Fecha 22:00 UTC
        if weekday == 4:
            return current_hour < 22
        
        # Segunda a Quinta: Sempre aberto 24h
        return True
    
    def has_daily_pause(self) -> bool:
        """Modo 24h não tem pausa diária"""
        return False
    
    def should_close_positions(self) -> bool:
        """Fecha posições Sexta 21:30 UTC (30 min antes)"""
        now = self.get_current_time()
        if now.weekday() == 4:  # Sexta
            return now.hour == 21 and now.minute >= 30
        return False
    
    def can_open_new_positions(self) -> Tuple[bool, str]:
        """Pode abrir posições quando mercado está aberto"""
        is_open = self.is_market_open()
        reason = "" if is_open else "Forex fechado (fim de semana)"
        return is_open, reason
    
    def get_market_status(self) -> Dict[str, Any]:
        """Retorna status do mercado forex"""
        is_open = self.is_market_open()
        should_close = self.should_close_positions()
        
        return {
            'is_open': is_open,
            'reason': None if is_open else "Mercado fechado",
            'should_close_positions': should_close,
            'has_daily_pause': False,
            'is_holiday': False
        }


class MarketHoursManager:
    """
    Gerenciador de horários de trading
    MODO 24H: Opera o dia todo, apenas fecha no fim de semana
    Sem pausas diárias - adaptação de liquidez feita pelo AdaptiveTradingManager
    """
    
    def __init__(self, config: Dict):
        """
        Inicializa gerenciador de horários
        
        🔄 MODO 24H: Opera 24/5 para todos os símbolos
        - Sem pausa de rollover (gerenciada pelo broker)
        - Adaptação de liquidez via AdaptiveTradingManager
        
        Args:
            config: Configuração completa
        """
        self.config = config
        schedule_config = config.get('schedule', {})
        
        # Timezone - UTC para consistência
        tz_str = schedule_config.get('timezone', 'UTC')
        self.timezone = pytz.timezone(tz_str)
        
        # Janela de segurança para fechamento semanal
        self.close_before_minutes = 30  # Fechar posições 30 min antes
        
        # 🆕 MODO 24H: Sem pausa diária
        self.daily_pause_enabled = False
        
        logger.info("🔄 MarketHoursManager MODO 24H inicializado")
        logger.info("📊 Opera 24/5 - Domingo 22:00 UTC até Sexta 22:00 UTC")
        logger.info("💡 Adaptação de liquidez via AdaptiveTradingManager")
    
    def get_current_time(self) -> datetime:
        """Retorna hora atual no timezone configurado"""
        return datetime.now(self.timezone)
    
    def is_market_open(self) -> bool:
        """
        Verifica se mercado está aberto
        
        🔄 MODO 24H: Opera 24/5
        - Domingo 22:00 UTC - Sexta 22:00 UTC
        - Sem pausas diárias
        
        Returns:
            True se mercado aberto
        """
        now = datetime.now(pytz.UTC)
        weekday = now.weekday()
        current_hour = now.hour
        
        # Sábado: Fechado
        if weekday == 5:
            return False
        
        # Domingo: Abre às 22:00 UTC
        if weekday == 6:
            return current_hour >= 22
        
        # Sexta-feira: Fecha às 22:00 UTC
        if weekday == 4:
            return current_hour < 22
        
        # Segunda a Quinta: Sempre aberto 24h
        return True
    
    def should_close_positions(self) -> bool:
        """
        Verifica se deve fechar posições (30 min antes do fechamento semanal)
        
        Returns:
            True se deve fechar posições
        """
        now = datetime.now(pytz.UTC)
        
        # Apenas sexta-feira às 21:30 UTC (30 min antes de 22:00)
        if now.weekday() == 4:  # Sexta
            if now.hour == 21 and now.minute >= 30:
                return True
        
        return False
    
    def can_open_new_positions(self) -> Tuple[bool, str]:
        """
        Verifica se pode abrir novas posições
        
        🔄 MODO 24H: Apenas bloqueia fim de semana
        
        Returns:
            Tuple (can_trade, reason)
        """
        now = datetime.now(pytz.UTC)
        
        # Mercado fechado
        if not self.is_market_open():
            return False, "Mercado fechado (fim de semana)"
        
        # Sexta após 21:30 - não abrir novas posições
        if now.weekday() == 4 and now.hour >= 21 and now.minute >= 30:
            return False, "Fechamento semanal em menos de 30 min"
        
        return True, "OK - Mercado aberto 24h"
    
    def get_next_market_event(self) -> Dict:
        """
        Retorna próximo evento do mercado
        
        Returns:
            Dict com informações do próximo evento
        """
        now = datetime.now(pytz.UTC)
        weekday = now.weekday()
        current_hour = now.hour
        
        # Se sexta antes das 22:00 - próximo evento é fechamento
        if weekday == 4 and current_hour < 22:
            close_datetime = now.replace(hour=22, minute=0, second=0)
            time_until = close_datetime - now
            return {
                'event': 'close',
                'datetime': close_datetime,
                'time_until_seconds': time_until.total_seconds(),
                'time_until_str': str(time_until).split('.')[0]
            }
        
        # Se fim de semana ou sexta após 22:00 - próximo evento é abertura
        if weekday >= 5 or (weekday == 4 and current_hour >= 22):
            # Calcular próximo domingo 22:00
            days_until_sunday = (6 - weekday) % 7
            if days_until_sunday == 0 and current_hour >= 22:
                days_until_sunday = 7
            
            next_open_date = now.date() + timedelta(days=days_until_sunday)
            next_open_datetime = datetime.combine(
                next_open_date,
                time(22, 0),
                tzinfo=pytz.UTC
            )
            time_until = next_open_datetime - now
            return {
                'event': 'open',
                'datetime': next_open_datetime,
                'time_until_seconds': time_until.total_seconds(),
                'time_until_str': str(time_until).split('.')[0]
            }
        
        # Durante a semana - próximo evento é fechamento sexta
        days_until_friday = (4 - weekday) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        
        next_close_date = now.date() + timedelta(days=days_until_friday)
        next_close_datetime = datetime.combine(
            next_close_date,
            time(22, 0),
            tzinfo=pytz.UTC
        )
        time_until = next_close_datetime - now
        
        return {
            'event': 'close',
            'datetime': next_close_datetime,
            'time_until_seconds': time_until.total_seconds(),
            'time_until_str': str(time_until).split('.')[0]
        }
    
    def get_market_status(self) -> Dict:
        """
        Retorna status completo do mercado
        
        Returns:
            Dict com status
        """
        is_open = self.is_market_open()
        should_close = self.should_close_positions()
        can_trade, reason = self.can_open_new_positions()
        next_event = self.get_next_market_event()
        
        return {
            'is_open': is_open,
            'should_close_positions': should_close,
            'can_open_positions': can_trade,
            'reason': reason,
            'current_time': datetime.now(pytz.UTC),
            'next_event': next_event,
            'mode': '24H'  # Indica modo 24h
        }
    
    def log_market_status(self):
        """Loga status atual do mercado"""
        status = self.get_market_status()
        
        logger.info("=" * 60)
        logger.info("🔄 MARKET STATUS - MODO 24H")
        logger.info("=" * 60)
        logger.info(
            f"Hora atual: "
            f"{status['current_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        logger.info(
            f"Mercado: {'🟢 ABERTO' if status['is_open'] else '🔴 FECHADO'}"
        )
        logger.info(
            f"Pode abrir posições: "
            f"{'✅ SIM' if status['can_open_positions'] else '❌ NÃO'}"
        )
        
        if not status['can_open_positions']:
            logger.warning(f"Motivo: {status['reason']}")
        
        if status['should_close_positions']:
            logger.warning(
                "⚠️  FECHAR POSIÇÕES ABERTAS (fechamento semanal próximo)"
            )
        
        next_event = status['next_event']
        event_names = {
            'open': 'ABERTURA (Domingo 22:00 UTC)',
            'close': 'FECHAMENTO (Sexta 22:00 UTC)'
        }
        event_name = event_names.get(next_event['event'], next_event['event'])
        logger.info(f"Próximo evento: {event_name}")
        logger.info(
            f"Data/Hora: "
            f"{next_event['datetime'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(f"Tempo restante: {next_event['time_until_str']}")
        logger.info("=" * 60)
