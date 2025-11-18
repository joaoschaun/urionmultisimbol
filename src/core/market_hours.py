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
        
        Horários Forex (UTC):
        - Domingo: 18:20 - 23:59
        - Segunda a Quinta: 00:00 - 16:30 e 18:20 - 23:59 (pausa 16:30-18:20)
        - Sexta: 00:00 - 16:30 (fechamento semanal)
        
        Args:
            config: Configuração completa
        """
        self.config = config
        schedule_config = config.get('schedule', {})
        
        # Timezone
        tz_str = schedule_config.get('timezone', 'UTC')
        self.timezone = pytz.timezone(tz_str)
        
        # Horários de pausa diária (segunda a sexta)
        self.daily_close_time = time(16, 30)  # Fecha diariamente às 16:30
        self.daily_open_time = time(18, 20)   # Reabre às 18:20
        
        # Dias especiais
        self.weekly_close_day = 4  # Sexta-feira (não reabre após 16:30)
        self.weekly_open_day = 6   # Domingo (abre às 18:20)
        
        # Janelas de segurança
        self.close_before_minutes = 30  # Fechar posições 30 min antes
        self.no_trade_after_open_minutes = 15  # Não operar 15 min após abertura
        
        logger.info("MarketHoursManager inicializado")
        logger.info(f"Timezone: {tz_str}")
        logger.info(f"Pausa diária: {self.daily_close_time} - {self.daily_open_time}")
        logger.info(f"Fecha posições: {self.close_before_minutes} min antes")
        logger.info(f"Bloqueia trades: {self.no_trade_after_open_minutes} min após abertura")
    
    def get_current_time(self) -> datetime:
        """Retorna hora atual no timezone configurado"""
        return datetime.now(self.timezone)
    
    def is_market_open(self) -> bool:
        """
        Verifica se mercado está aberto (considera pausa diária)
        
        Horários:
        - Domingo: 18:20 - 23:59
        - Segunda a Quinta: 00:00 - 16:30 e 18:20 - 23:59
        - Sexta: 00:00 - 16:30
        - Sábado: Fechado
        
        Returns:
            True se mercado aberto
        """
        now = self.get_current_time()
        weekday = now.weekday()
        current_time = now.time()
        
        # Sábado: Fechado
        if weekday == 5:
            return False
        
        # Domingo: Abre às 18:20
        if weekday == 6:
            return current_time >= self.daily_open_time
        
        # Sexta-feira: Fecha às 16:30 (não reabre)
        if weekday == 4:
            return current_time < self.daily_close_time
        
        # Segunda a Quinta: Aberto exceto na pausa 16:30-18:20
        if weekday in [0, 1, 2, 3]:
            # Se está na pausa diária
            if self.daily_close_time <= current_time < self.daily_open_time:
                return False
            return True
        
        return False
    
    def should_close_positions(self) -> bool:
        """
        Verifica se deve fechar posições (30 min antes do fechamento)
        
        Fecha posições:
        - Segunda a Sexta às 16:00 (30 min antes de 16:30)
        
        Returns:
            True se deve fechar posições
        """
        now = self.get_current_time()
        weekday = now.weekday()
        
        # Segunda a Sexta: Fechar 30 min antes da pausa/fechamento (16:00)
        if weekday in [0, 1, 2, 3, 4]:  # Segunda a Sexta
            close_time = datetime.combine(
                now.date(),
                self.daily_close_time,
                tzinfo=self.timezone
            )
            close_warning_time = close_time - timedelta(
                minutes=self.close_before_minutes
            )
            
            if now >= close_warning_time and now.time() < self.daily_close_time:
                return True
        
        return False
    
    def can_open_new_positions(self) -> Tuple[bool, str]:
        """
        Verifica se pode abrir novas posições
        
        Bloqueios:
        - Mercado fechado (sábado, pausa diária)
        - 30 min antes de fechar (16:00)
        - 15 min após abrir (domingo 18:20-18:35, dias úteis 18:20-18:35)
        
        Returns:
            Tuple (can_trade, reason)
        """
        now = self.get_current_time()
        weekday = now.weekday()
        current_time = now.time()
        
        # Mercado fechado
        if not self.is_market_open():
            return False, "Mercado fechado (pausa ou fim de semana)"
        
        # Segunda a Sexta: Não operar 30 min antes da pausa/fechamento
        if weekday in [0, 1, 2, 3, 4]:
            close_time = datetime.combine(
                now.date(),
                self.daily_close_time,
                tzinfo=self.timezone
            )
            close_warning_time = close_time - timedelta(
                minutes=self.close_before_minutes
            )
            
            if now >= close_warning_time and now.time() < self.daily_close_time:
                return False, f"Pausa diária em menos de {self.close_before_minutes} min"
        
        # Após reabertura: Não operar 15 min
        # Domingo 18:20-18:35 ou Segunda-Quinta 18:20-18:35
        if weekday == 6 or weekday in [0, 1, 2, 3]:
            open_time = datetime.combine(
                now.date(),
                self.daily_open_time,
                tzinfo=self.timezone
            )
            no_trade_until = open_time + timedelta(
                minutes=self.no_trade_after_open_minutes
            )
            
            # Se acabou de abrir (ainda na janela de 15 min)
            if self.daily_open_time <= current_time < no_trade_until.time():
                return False, f"Aguardando {self.no_trade_after_open_minutes} min após abertura"
        
        return True, "OK"
    
    def get_next_market_event(self) -> Dict:
        """
        Retorna próximo evento do mercado (abertura ou fechamento/pausa)
        
        Returns:
            Dict com informações do próximo evento
        """
        now = self.get_current_time()
        weekday = now.weekday()
        current_time = now.time()
        
        # Se estamos antes da pausa diária (segunda a sexta)
        if weekday in [0, 1, 2, 3, 4] and current_time < self.daily_close_time:
            close_datetime = datetime.combine(
                now.date(),
                self.daily_close_time,
                tzinfo=self.timezone
            )
            time_until = close_datetime - now
            
            event_name = 'close' if weekday == 4 else 'pause'
            
            return {
                'event': event_name,
                'datetime': close_datetime,
                'time_until_seconds': time_until.total_seconds(),
                'time_until_str': str(time_until).split('.')[0]
            }
        
        # Se estamos na pausa diária (segunda a quinta)
        if weekday in [0, 1, 2, 3] and self.daily_close_time <= current_time < self.daily_open_time:
            open_datetime = datetime.combine(
                now.date(),
                self.daily_open_time,
                tzinfo=self.timezone
            )
            time_until = open_datetime - now
            
            return {
                'event': 'open',
                'datetime': open_datetime,
                'time_until_seconds': time_until.total_seconds(),
                'time_until_str': str(time_until).split('.')[0]
            }
        
        # Se sexta após 16:30, sábado, ou domingo antes 18:20: próxima abertura domingo
        if (weekday == 4 and current_time >= self.daily_close_time) or \
           weekday == 5 or \
           (weekday == 6 and current_time < self.daily_open_time):
            
            days_until_sunday = (6 - weekday) % 7
            if weekday == 6 and current_time < self.daily_open_time:
                days_until_sunday = 0
            
            next_open_date = now.date() + timedelta(days=days_until_sunday)
            next_open_datetime = datetime.combine(
                next_open_date,
                self.daily_open_time,
                tzinfo=self.timezone
            )
            time_until = next_open_datetime - now
            
            return {
                'event': 'open',
                'datetime': next_open_datetime,
                'time_until_seconds': time_until.total_seconds(),
                'time_until_str': str(time_until).split('.')[0]
            }
        
        # Se domingo ou segunda-quinta após 18:20: próxima pausa
        next_close_date = now.date()
        if current_time >= self.daily_open_time:
            next_close_date += timedelta(days=1)
        
        next_close_datetime = datetime.combine(
            next_close_date,
            self.daily_close_time,
            tzinfo=self.timezone
        )
        time_until = next_close_datetime - now
        
        # Determinar tipo de evento
        next_weekday = next_close_date.weekday()
        event_name = 'close' if next_weekday == 4 else 'pause'
        
        return {
            'event': event_name,
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
            logger.warning("⚠️  FECHAR POSIÇÕES ABERTAS (próximo da pausa/fechamento)")
        
        next_event = status['next_event']
        event_names = {
            'open': 'ABERTURA',
            'pause': 'PAUSA DIÁRIA',
            'close': 'FECHAMENTO SEMANAL'
        }
        event_name = event_names.get(next_event['event'], next_event['event'].upper())
        logger.info(f"Próximo evento: {event_name}")
        logger.info(f"Data/Hora: {next_event['datetime'].strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Tempo restante: {next_event['time_until_str']}")
        logger.info("=" * 60)
