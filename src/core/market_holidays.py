"""
Market Holidays Manager
Gerencia feriados do mercado financeiro (NYSE, COMEX)
"""
from datetime import datetime, date
from typing import Dict, List, Optional
from loguru import logger
import pytz


class MarketHolidays:
    """Gerencia feriados do mercado XAUUSD (COMEX Gold)"""
    
    def __init__(self):
        """Inicializa calendário de feriados"""
        self.ny_tz = pytz.timezone('America/New_York')
        
        # 🗓️ Feriados fixos anuais (COMEX Gold)
        self.fixed_holidays = {
            (1, 1): "New Year's Day",
            (7, 4): "Independence Day",
            (12, 25): "Christmas Day",
        }
        
        # 🗓️ Feriados variáveis 2025-2026
        self.variable_holidays = {
            2025: [
                date(2025, 1, 20),   # Martin Luther King Jr. Day
                date(2025, 2, 17),   # Presidents' Day
                date(2025, 4, 18),   # Good Friday
                date(2025, 5, 26),   # Memorial Day
                date(2025, 9, 1),    # Labor Day
                date(2025, 11, 27),  # Thanksgiving 🦃
                date(2025, 11, 28),  # Day After Thanksgiving
            ],
            2026: [
                date(2026, 1, 19),   # Martin Luther King Jr. Day
                date(2026, 2, 16),   # Presidents' Day
                date(2026, 4, 3),    # Good Friday
                date(2026, 5, 25),   # Memorial Day
                date(2026, 9, 7),    # Labor Day
                date(2026, 11, 26),  # Thanksgiving
                date(2026, 11, 27),  # Day After Thanksgiving
            ],
        }
        
        # 🕐 Fechamentos antecipados (early close @ 13:00 NY)
        self.early_close_days = {
            2025: [
                date(2025, 7, 3),    # Day before Independence Day
                date(2025, 11, 26),  # Day before Thanksgiving
                date(2025, 12, 24),  # Christmas Eve
            ],
            2026: [
                date(2026, 7, 3),
                date(2026, 11, 25),
                date(2026, 12, 24),
            ],
        }
        
        logger.info("MarketHolidays inicializado com calendário 2025-2026")
    
    def is_holiday(self, check_date: Optional[datetime] = None) -> tuple[bool, str]:
        """
        Verifica se é feriado de mercado
        
        Args:
            check_date: Data para verificar (default: hoje)
            
        Returns:
            tuple (is_holiday, holiday_name)
        """
        if check_date is None:
            check_date = datetime.now(self.ny_tz)
        
        # Converter para date se necessário
        if isinstance(check_date, datetime):
            check_date = check_date.date()
        
        year = check_date.year
        month = check_date.month
        day = check_date.day
        
        # Verificar feriados fixos
        if (month, day) in self.fixed_holidays:
            holiday_name = self.fixed_holidays[(month, day)]
            
            # Se cai em sábado, observado na sexta
            # Se cai em domingo, observado na segunda
            weekday = check_date.weekday()
            if weekday == 5:  # Sábado
                logger.info(f"🏖️ Feriado: {holiday_name} (observado sexta)")
                return True, f"{holiday_name} (observed Friday)"
            elif weekday == 6:  # Domingo
                logger.info(f"🏖️ Feriado: {holiday_name} (observado segunda)")
                return False, ""  # Mercado abre segunda
            else:
                logger.info(f"🏖️ Feriado: {holiday_name}")
                return True, holiday_name
        
        # Verificar feriados variáveis
        if year in self.variable_holidays:
            if check_date in self.variable_holidays[year]:
                # Identificar qual feriado
                holiday_names = {
                    1: "Martin Luther King Jr. Day",
                    2: "Presidents' Day",
                    4: "Good Friday",
                    5: "Memorial Day",
                    9: "Labor Day",
                    11: "Thanksgiving" if check_date.day < 28 else "Day After Thanksgiving",
                }
                holiday_name = holiday_names.get(month, "Market Holiday")
                logger.info(f"🏖️ Feriado: {holiday_name}")
                return True, holiday_name
        
        return False, ""
    
    def is_early_close(self, check_date: Optional[datetime] = None) -> tuple[bool, str]:
        """
        Verifica se é dia de fechamento antecipado (13:00 NY)
        
        Args:
            check_date: Data para verificar (default: hoje)
            
        Returns:
            tuple (is_early_close, reason)
        """
        if check_date is None:
            check_date = datetime.now(self.ny_tz)
        
        if isinstance(check_date, datetime):
            check_date = check_date.date()
        
        year = check_date.year
        
        if year in self.early_close_days:
            if check_date in self.early_close_days[year]:
                reason = "Early close @ 13:00 NY"
                logger.info(f"⏰ {reason}")
                return True, reason
        
        return False, ""
    
    def can_trade(self, check_datetime: Optional[datetime] = None) -> tuple[bool, str]:
        """
        Verifica se pode operar (considera feriados + early close)
        
        Args:
            check_datetime: Datetime para verificar (default: agora)
            
        Returns:
            tuple (can_trade, reason)
        """
        if check_datetime is None:
            check_datetime = datetime.now(self.ny_tz)
        
        # Verificar feriado
        is_holiday, holiday_name = self.is_holiday(check_datetime)
        if is_holiday:
            return False, f"Market closed: {holiday_name}"
        
        # Verificar early close
        is_early, reason = self.is_early_close(check_datetime)
        if is_early:
            current_time = check_datetime.time()
            close_time = datetime.strptime("13:00", "%H:%M").time()
            
            if current_time >= close_time:
                return False, "Market closed early @ 13:00 NY"
            else:
                logger.warning(f"⚠️ {reason} - Mercado fecha cedo hoje!")
                return True, reason  # Pode operar, mas com aviso
        
        return True, "Market open"
    
    def get_next_holiday(self) -> tuple[date, str]:
        """
        Retorna próximo feriado
        
        Returns:
            tuple (date, holiday_name)
        """
        today = datetime.now(self.ny_tz).date()
        year = today.year
        
        # Combinar feriados fixos e variáveis
        all_holidays = []
        
        # Fixos
        for (month, day), name in self.fixed_holidays.items():
            holiday_date = date(year, month, day)
            if holiday_date >= today:
                all_holidays.append((holiday_date, name))
        
        # Variáveis
        if year in self.variable_holidays:
            for holiday_date in self.variable_holidays[year]:
                if holiday_date >= today:
                    # Identificar nome
                    month = holiday_date.month
                    holiday_names = {
                        1: "Martin Luther King Jr. Day",
                        2: "Presidents' Day",
                        4: "Good Friday",
                        5: "Memorial Day",
                        9: "Labor Day",
                        11: "Thanksgiving",
                    }
                    name = holiday_names.get(month, "Market Holiday")
                    all_holidays.append((holiday_date, name))
        
        # Ordenar e retornar próximo
        if all_holidays:
            all_holidays.sort(key=lambda x: x[0])
            return all_holidays[0]
        
        return None, ""
    
    def get_holidays_this_month(self) -> List[tuple[date, str]]:
        """
        Retorna todos os feriados do mês atual
        
        Returns:
            List de tuples (date, holiday_name)
        """
        today = datetime.now(self.ny_tz).date()
        year = today.year
        month = today.month
        
        holidays_this_month = []
        
        # Fixos
        for (hol_month, day), name in self.fixed_holidays.items():
            if hol_month == month:
                holiday_date = date(year, hol_month, day)
                holidays_this_month.append((holiday_date, name))
        
        # Variáveis
        if year in self.variable_holidays:
            for holiday_date in self.variable_holidays[year]:
                if holiday_date.month == month:
                    month_num = holiday_date.month
                    holiday_names = {
                        1: "Martin Luther King Jr. Day",
                        2: "Presidents' Day",
                        4: "Good Friday",
                        5: "Memorial Day",
                        9: "Labor Day",
                        11: "Thanksgiving" if holiday_date.day < 28 else "Day After Thanksgiving",
                    }
                    name = holiday_names.get(month_num, "Market Holiday")
                    holidays_this_month.append((holiday_date, name))
        
        holidays_this_month.sort(key=lambda x: x[0])
        return holidays_this_month


# 🎯 Singleton instance
_market_holidays_instance = None

def get_market_holidays() -> MarketHolidays:
    """Retorna instância singleton do MarketHolidays"""
    global _market_holidays_instance
    if _market_holidays_instance is None:
        _market_holidays_instance = MarketHolidays()
    return _market_holidays_instance
