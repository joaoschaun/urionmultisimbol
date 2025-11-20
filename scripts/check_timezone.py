"""
Script para verificar e corrigir cálculo de timezone
"""
from datetime import datetime
import pytz

def check_timezone():
    """Verifica horário atual em diferentes timezones"""
    
    # Hora UTC
    utc_now = datetime.now(pytz.UTC)
    
    # Hora EST/EDT (America/New_York)
    est_tz = pytz.timezone('America/New_York')
    est_now = utc_now.astimezone(est_tz)
    
    print("\n" + "="*60)
    print("VERIFICAÇÃO DE TIMEZONE")
    print("="*60)
    
    print(f"\nUTC:")
    print(f"  Hora: {utc_now.strftime('%H:%M:%S')}")
    print(f"  Data completa: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    print(f"\nAmerica/New_York:")
    print(f"  Hora: {est_now.strftime('%H:%M:%S')}")
    print(f"  Data completa: {est_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Timezone: {est_now.tzname()}")
    print(f"  Offset: UTC{est_now.strftime('%z')}")
    
    # Diferença
    offset_hours = (est_now.hour - utc_now.hour) % 24
    if offset_hours > 12:
        offset_hours = offset_hours - 24
    
    print(f"\nDiferença: {offset_hours:+d} horas")
    
    # Verificar se está correto
    if est_now.tzname() == 'EST':
        expected_offset = -5
    else:  # EDT
        expected_offset = -4
    
    print(f"Offset esperado: UTC{expected_offset:+d}")
    print(f"Offset atual: UTC{offset_hours:+d}")
    
    if offset_hours == expected_offset:
        print("\n✅ TIMEZONE CORRETO!")
    else:
        print("\n❌ TIMEZONE INCORRETO!")
    
    print("="*60 + "\n")
    
    return est_now

if __name__ == "__main__":
    check_timezone()
