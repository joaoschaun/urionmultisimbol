"""
Script de teste para verificar fuso horário America/New_York
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime
import pytz
from loguru import logger
from core.config_manager import ConfigManager
from core.market_hours import MarketHoursManager


def test_timezone():
    """Testa configuração de fuso horário"""
    
    print("\n" + "="*80)
    print(" TESTE DE FUSO HORÁRIO - URION TRADING BOT")
    print("="*80 + "\n")
    
    # 1. Carregar configuração
    print("📋 Carregando configuração...")
    config = ConfigManager()
    
    # 2. Verificar timezone configurado
    schedule_config = config.get('schedule', {})
    timezone_str = schedule_config.get('timezone', 'UTC')
    
    print(f"\n✅ Timezone configurado: {timezone_str}")
    
    # 3. Criar timezone objects
    try:
        ny_tz = pytz.timezone('America/New_York')
        utc_tz = pytz.UTC
        
        print(f"✅ Timezone object criado: {ny_tz}")
    except Exception as e:
        print(f"❌ Erro ao criar timezone: {e}")
        return False
    
    # 4. Mostrar hora atual em diferentes timezones
    print("\n" + "="*80)
    print(" HORA ATUAL")
    print("="*80)
    
    now_local = datetime.now()
    now_utc = datetime.now(utc_tz)
    now_ny = datetime.now(ny_tz)
    
    print(f"\n⏰ Hora Local (Windows): {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏰ Hora UTC:            {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"⏰ Hora New York:       {now_ny.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # 5. Calcular diferença
    offset_hours = (now_ny.utcoffset().total_seconds() / 3600)
    print(f"\n📊 Diferença UTC → New York: {offset_hours:+.1f} horas")
    
    if now_ny.dst():
        print("☀️  EDT (Eastern Daylight Time) - Horário de Verão")
    else:
        print("❄️  EST (Eastern Standard Time) - Horário Padrão")
    
    # 6. Testar MarketHoursManager
    print("\n" + "="*80)
    print(" TESTANDO MARKET HOURS MANAGER")
    print("="*80 + "\n")
    
    try:
        market_hours = MarketHoursManager(config.config)
        
        # Hora atual no timezone configurado
        current_time = market_hours.get_current_time()
        print(f"⏰ Hora atual (config): {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Verificar se mercado está aberto
        is_open = market_hours.is_market_open()
        print(f"\n{'✅' if is_open else '❌'} Mercado está {'ABERTO' if is_open else 'FECHADO'}")
        
        # Status detalhado
        status = market_hours.get_market_status()
        
        print(f"\n📊 Status do Mercado:")
        print(f"   • Dia da semana: {status['current_time'].strftime('%A')}")
        print(f"   • Mercado aberto: {status['is_open']}")
        
        if status.get('can_trade') is not None:
            print(f"   • Pode operar: {status['can_trade']}")
        
        if status.get('next_event'):
            next_event = status['next_event']
            event_time = next_event['datetime'].strftime('%d/%m/%Y %H:%M:%S %Z')
            event_type = next_event.get('type', next_event.get('event', 'Evento'))
            print(f"   • Próximo evento: {event_type} em {event_time}")
        
    except Exception as e:
        print(f"❌ Erro ao testar MarketHoursManager: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 7. Horários importantes
    print("\n" + "="*80)
    print(" HORÁRIOS DE TRADING (New York Time)")
    print("="*80)
    
    print(f"""
📅 Domingo:
   Abertura: 18:30 EST/EDT

📅 Segunda a Quinta:
   Trading: 00:00 - 16:30 EST/EDT (pausa 16:30-18:20)
   Trading: 18:20 - 23:59 EST/EDT

📅 Sexta:
   Fechamento: 16:30 EST/EDT
   
⚠️  Pausa diária: 16:30 - 18:20 EST/EDT
⚠️  Posições fechadas: 30 min antes do fechamento (16:00 EST/EDT)
    """)
    
    print("\n" + "="*80)
    print(" ✅ TESTE CONCLUÍDO COM SUCESSO!")
    print("="*80 + "\n")
    
    return True


if __name__ == "__main__":
    try:
        success = test_timezone()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
