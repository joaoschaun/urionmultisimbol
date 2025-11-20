"""
Time Helper - Funções para trabalhar com timezone corretamente
"""
from datetime import datetime
import pytz


def get_current_times():
    """
    Retorna horários atuais em UTC e EST
    
    Returns:
        dict: {
            'utc': datetime,
            'est': datetime,
            'utc_str': str,
            'est_str': str,
            'timezone_name': str,
            'offset': str
        }
    """
    # Hora UTC
    utc_now = datetime.now(pytz.UTC)
    
    # Hora EST/EDT
    est_tz = pytz.timezone('America/New_York')
    est_now = utc_now.astimezone(est_tz)
    
    return {
        'utc': utc_now,
        'est': est_now,
        'utc_str': utc_now.strftime('%H:%M:%S'),
        'est_str': est_now.strftime('%H:%M:%S'),
        'timezone_name': est_now.tzname(),
        'offset': est_now.strftime('%z')
    }


def format_time_display():
    """
    Formata horário atual para exibição
    
    Returns:
        str: String formatada com UTC e EST
    """
    times = get_current_times()
    
    return (
        f"UTC: {times['utc_str']} | "
        f"EST: {times['est_str']} ({times['timezone_name']})"
    )


def print_current_time():
    """Imprime horário atual formatado"""
    times = get_current_times()
    
    print("\n" + "="*60)
    print("HORÁRIO ATUAL")
    print("="*60)
    print(f"UTC: {times['utc_str']}")
    print(f"EST: {times['est_str']} ({times['timezone_name']} UTC{times['offset']})")
    print("="*60 + "\n")
