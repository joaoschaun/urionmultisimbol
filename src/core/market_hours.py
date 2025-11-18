"""
Market Hours Manager
Gerencia horários de abertura/fechamento do mercado
Fecha posições automaticamente antes do fechamento
"""
from datetime import datetime, time, timedelta
from typing import Dict, Optional, Tuple
from loguru import logger
import pytz


class MarketHoursManager:
    """Gerencia horários de trading e fecha posições automaticamente"""
    
    def __init__(self, config: Dict):
        """
        Inicializa gerenciador de horários
        
        Args:
            config: Configuração completa
        """
        self.config = config
        schedule_config = config.get('schedule', {})
        
        # Timezone
        tz_str = schedule_config.get('timezone', 'UTC')
        self.timezone = pytz.timezone(tz_str)
        
        # Horários do mercado Forex (NYC time - UTC-5)
        # Domingo 18:00 (abertura) até Sexta 17:00 (fechamento)
        
        # Fechamento semanal (Sexta-feira)
        self.weekly_close_day = 4  # 0=Segunda, 4=Sexta
        self.weekly_close_time = time(16, 30)  # 16:30 (4:30 PM)
        
        # Abertura semanal (Domingo)
        self.weekly_open_day = 6  # Domingo
        self.weekly_open_time = time(18, 30)  # 18:30 (6:30 PM)
        
        # Janelas de segurança
        self.close_before_minutes = 30  # Fechar posições 30 min antes
        self.no_trade_after_open_minutes = 15  # Não operar 15 min após abertura
        
        logger.info("MarketHoursManager inicializado")
        logger.info(f"Timezone: {tz_str}")
        logger.info(f"Fecha posições: {self.close_before_minutes} min antes do fechamento")
        logger.info(f"Bloqueia trades: {self.no_trade_after_open_minutes} min após abertura")
    
    def get_current_time(self) -> datetime:
        """Retorna hora atual no timezone configurado"""
        return datetime.now(self.timezone)
    
    def is_market_open(self) -> bool:
        """
        Verifica se mercado está aberto
        
        Returns:
            True se mercado aberto
        """
        now = self.get_current_time()
        weekday = now.weekday()
        current_time = now.time()
        
        # Sábado: Fechado
        if weekday == 5:
            return False
        
        # Domingo: Abre às 18:30
        if weekday == 6:
            return current_time >= self.weekly_open_time
        
        # Sexta-feira: Fecha às 16:30
        if weekday == 4:
            return current_time < self.weekly_close_time
        
        # Segunda a Quinta: Sempre aberto
        return True
    
    def should_close_positions(self) -> bool:
        """
        Verifica se deve fechar posições (30 min antes do fechamento)
        
        Returns:
            True se deve fechar posições
        """
        now = self.get_current_time()
        weekday = now.weekday()
        current_time = now.time()
        
        # Sexta-feira: Fechar 30 min antes (16:00)
        if weekday == 4:
            close_time = datetime.combine(
                now.date(),
                self.weekly_close_time
            )
            close_warning_time = close_time - timedelta(
                minutes=self.close_before_minutes
            )
            
            if now >= close_warning_time:
                return True
        
        return False
    
    def can_open_new_positions(self) -> Tuple[bool, str]:
        """
        Verifica se pode abrir novas posições
        
        Returns:
            Tuple (can_trade, reason)
        """
        now = self.get_current_time()
        weekday = now.weekday()
        current_time = now.time()
        
        # Mercado fechado
        if not self.is_market_open():
            return False, "Mercado fechado"
        
        # Sexta-feira: Não operar 30 min antes do fechamento
        if weekday == 4:
            close_time = datetime.combine(
                now.date(),
                self.weekly_close_time
            )
            close_warning_time = close_time - timedelta(
                minutes=self.close_before_minutes
            )
            
            if now >= close_warning_time:
                return False, f"Mercado fecha em menos de {self.close_before_minutes} min"
        
        # Domingo: Não operar 15 min após abertura
        if weekday == 6:
            open_time = datetime.combine(
                now.date(),
                self.weekly_open_time
            )
            no_trade_until = open_time + timedelta(
                minutes=self.no_trade_after_open_minutes
            )
            
            if now < no_trade_until:
                return False, f"Aguardando {self.no_trade_after_open_minutes} min após abertura"
        
        return True, "OK"
    
    def get_next_market_event(self) -> Dict:
        """
        Retorna próximo evento do mercado (abertura ou fechamento)
        
        Returns:
            Dict com informações do próximo evento
        """
        now = self.get_current_time()
        weekday = now.weekday()
        
        # Se sexta-feira e antes do fechamento
        if weekday == 4 and now.time() < self.weekly_close_time:
            close_datetime = datetime.combine(
                now.date(),
                self.weekly_close_time,
                tzinfo=self.timezone
            )
            time_until = close_datetime - now
            
            return {
                'event': 'close',
                'datetime': close_datetime,
                'time_until_seconds': time_until.total_seconds(),
                'time_until_str': str(time_until).split('.')[0]
            }
        
        # Calcular próxima abertura (Domingo)
        days_until_sunday = (6 - weekday) % 7
        if days_until_sunday == 0 and now.time() >= self.weekly_open_time:
            days_until_sunday = 7
        
        next_open_date = now.date() + timedelta(days=days_until_sunday)
        next_open_datetime = datetime.combine(
            next_open_date,
            self.weekly_open_time,
            tzinfo=self.timezone
        )
        time_until = next_open_datetime - now
        
        return {
            'event': 'open',
            'datetime': next_open_datetime,
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
            'current_time': self.get_current_time(),
            'next_event': next_event
        }
    
    def log_market_status(self):
        """Loga status atual do mercado"""
        status = self.get_market_status()
        
        logger.info("=" * 60)
        logger.info("MARKET STATUS")
        logger.info("=" * 60)
        logger.info(f"Hora atual: {status['current_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"Mercado: {'🟢 ABERTO' if status['is_open'] else '🔴 FECHADO'}")
        logger.info(f"Pode abrir posições: {'✅ SIM' if status['can_open_positions'] else '❌ NÃO'}")
        
        if not status['can_open_positions']:
            logger.warning(f"Motivo: {status['reason']}")
        
        if status['should_close_positions']:
            logger.warning("⚠️  FECHAR POSIÇÕES ABERTAS (próximo do fechamento)")
        
        next_event = status['next_event']
        event_name = 'ABERTURA' if next_event['event'] == 'open' else 'FECHAMENTO'
        logger.info(f"Próximo evento: {event_name}")
        logger.info(f"Data/Hora: {next_event['datetime'].strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Tempo restante: {next_event['time_until_str']}")
        logger.info("=" * 60)
