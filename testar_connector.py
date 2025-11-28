"""
Testar MT5Connector get_open_positions()
"""
from src.core.mt5_connector import MT5Connector
from src.core.config_manager import ConfigManager

config = ConfigManager().config
mt5 = MT5Connector(config)

print("Conectando ao MT5...")
if mt5.connect():
    print("✅ Conectado")
    
    print("\nTestando get_open_positions()...")
    positions = mt5.get_open_positions()
    
    print(f"Retornou: {len(positions)} posições")
    
    if positions:
        for p in positions:
            print(f"  Ticket {p['ticket']}: {p['symbol']} {p['type']} @ {p['price_open']:.2f}")
            print(f"    Profit: ${p['profit']:.2f}, SL: {p['sl']:.2f}, TP: {p['tp']:.2f}")
    else:
        print("❌ Lista vazia!")
    
    mt5.disconnect()
else:
    print("❌ Falha ao conectar")
