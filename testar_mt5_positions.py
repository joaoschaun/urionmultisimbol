"""
Script para testar conexão MT5 e visualizar posições abertas
"""
import MetaTrader5 as mt5
from datetime import datetime

print("=" * 70)
print("TESTE DE POSIÇÕES MT5")
print("=" * 70)

# Inicializar
if not mt5.initialize():
    print("❌ Erro ao inicializar MT5")
    exit()

print("✅ MT5 inicializado")
print()

# Info da conta
acc = mt5.account_info()
if acc:
    print("=== INFORMAÇÕES DA CONTA ===")
    print(f"Login: {acc.login}")
    print(f"Server: {acc.server}")
    print(f"Balance: ${acc.balance:.2f}")
    print(f"Equity: ${acc.equity:.2f}")
    print(f"Margin Free: ${acc.margin_free:.2f}")
    print()

# Testar positions_get() sem parâmetros
print("=== POSITIONS_GET() - SEM FILTRO ===")
pos_all = mt5.positions_get()
if pos_all is None:
    print("❌ positions_get() retornou None")
elif len(pos_all) == 0:
    print("⚠️  Nenhuma posição encontrada")
else:
    print(f"✅ {len(pos_all)} posição(ões) encontrada(s):")
    for p in pos_all:
        tipo = "BUY" if p.type == 0 else "SELL"
        print(f"  - Ticket {p.ticket}: {p.symbol} {tipo} {p.volume} lots")
        print(f"    Open: {p.price_open:.2f}, Current: {p.price_current:.2f}, Profit: ${p.profit:.2f}")
        print(f"    SL: {p.sl:.2f}, TP: {p.tp:.2f}")
        print(f"    Magic: {p.magic}, Comment: {p.comment}")
        print()

# Testar positions_get(symbol='XAUUSD')
print("=== POSITIONS_GET(symbol='XAUUSD') ===")
pos_xau = mt5.positions_get(symbol='XAUUSD')
if pos_xau is None:
    print("❌ positions_get(symbol='XAUUSD') retornou None")
elif len(pos_xau) == 0:
    print("⚠️  Nenhuma posição XAUUSD encontrada")
else:
    print(f"✅ {len(pos_xau)} posição(ões) XAUUSD encontrada(s):")
    for p in pos_xau:
        tipo = "BUY" if p.type == 0 else "SELL"
        print(f"  - Ticket {p.ticket}: {tipo} @ {p.price_open:.2f}, Profit: ${p.profit:.2f}")

print()
print("=== VERIFICAR SYMBOL INFO ===")
symbol_info = mt5.symbol_info('XAUUSD')
if symbol_info:
    print(f"✅ XAUUSD encontrado")
    print(f"  - Visible: {symbol_info.visible}")
    print(f"  - Bid: {symbol_info.bid:.2f}")
    print(f"  - Ask: {symbol_info.ask:.2f}")
else:
    print("❌ XAUUSD não encontrado")

mt5.shutdown()
print()
print("=" * 70)
print("TESTE CONCLUÍDO")
print("=" * 70)
