"""
Script para verificar o spread atual do XAUUSD
"""
import MetaTrader5 as mt5
from datetime import datetime
import pytz

# Inicializar MT5
if not mt5.initialize():
    print("Erro ao inicializar MT5")
    exit()

try:
    # Obter informações do símbolo
    symbol_info = mt5.symbol_info_tick('XAUUSD')
    
    if symbol_info is None:
        print("Erro ao obter informações do XAUUSD")
        exit()
    
    # Calcular spread
    spread_points = symbol_info.ask - symbol_info.bid
    spread_pips = spread_points * 10  # 1 pip = 0.1 para ouro
    
    # Obter horários
    utc_now = datetime.now(pytz.UTC)
    est_now = utc_now.astimezone(pytz.timezone('America/New_York'))
    
    # Configuração do bot
    limite_pips = 5
    
    # Exibir informações
    print("\n" + "="*60)
    print("         XAUUSD - SPREAD ATUAL")
    print("="*60)
    
    print(f"\n⏰ HORÁRIO:")
    print(f"   UTC: {utc_now.strftime('%H:%M:%S')}")
    print(f"   EST: {est_now.strftime('%H:%M:%S')} ({est_now.tzname()})")
    
    print(f"\n💰 PREÇOS:")
    print(f"   Bid: {symbol_info.bid:.2f}")
    print(f"   Ask: {symbol_info.ask:.2f}")
    print(f"   Spread: {spread_points:.2f} pontos = {spread_pips:.1f} pips")
    
    print(f"\n📊 ANÁLISE:")
    
    # Determinar status baseado no spread
    if spread_pips <= 2:
        status = "EXCELENTE ✅ - Tier 1 (Europa+NY)"
        tier = 1
    elif spread_pips <= limite_pips:
        status = f"BOM ✅ - Abaixo do limite ({limite_pips} pips)"
        tier = 2
    elif spread_pips <= 8:
        status = f"ACEITÁVEL ⚠️ - Tier 3 (Europa Solo)"
        tier = 3
    else:
        status = f"ALTO ❌ - Acima de 8 pips"
        tier = 4
    
    print(f"   Status: {status}")
    print(f"   Config: Limite {limite_pips} pips")
    
    if spread_pips <= limite_pips:
        print(f"   🤖 Bot: PODE OPERAR ✅")
    else:
        print(f"   🤖 Bot: AGUARDANDO SPREAD MENOR ⏳")
    
    print(f"\n💹 LIQUIDEZ:")
    if tier == 1:
        print(f"   Tier 1: 08:00-12:00 EST (100% liquidez)")
        print(f"           Spread: 2-3 pips - EXCELENTE")
    elif tier == 2:
        print(f"   Tier 2: 12:00-15:00 EST (70-80% liquidez)")
        print(f"           Spread: 3-5 pips - MUITO BOM")
    elif tier == 3:
        print(f"   Tier 3: 03:00-08:00 EST (50-60% liquidez)")
        print(f"           Spread: 5-8 pips - BOM")
    else:
        print(f"   Tier 4: Sessão Asiática/Noite NY (20-40% liquidez)")
        print(f"           Spread: 8-30 pips - EVITAR")
    
    print("\n" + "="*60 + "\n")

finally:
    mt5.shutdown()
