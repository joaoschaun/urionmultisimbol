#!/usr/bin/env python3
"""
Análise crítica: Verificar se ordens estão com SL/TP invertidos
"""

import sqlite3
import MetaTrader5 as mt5

# Conectar ao MT5
if not mt5.initialize():
    print("❌ Falha ao conectar MT5")
    exit(1)

# Obter preço atual
symbol = "XAUUSD"
tick = mt5.symbol_info_tick(symbol)
current_price = tick.bid

print(f"\n🔍 ANÁLISE DE TRADES - Preço Atual: {current_price:.2f}")
print("="*100)

# Buscar trades no database
conn = sqlite3.connect('data/strategy_stats.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT ticket, strategy_name, type, open_price, sl, tp
    FROM strategy_trades
    WHERE close_time IS NULL
    ORDER BY open_time DESC
    LIMIT 10
''')

print(f"\n{'Ticket':<12} | {'Estratégia':<18} | {'Tipo':<4} | {'Open':>8} | {'SL':>8} | {'TP':>8} | {'Status SL':<15} | {'Status TP':<15}")
print("-"*130)

problems = []

for row in cursor.fetchall():
    ticket, strat, tipo, open_price, sl, tp = row
    tipo_str = "BUY" if tipo == 0 else "SELL"
    
    # Verificar se SL/TP estão corretos
    if tipo == 0:  # BUY
        # SL deve estar ABAIXO do preço de abertura
        # TP deve estar ACIMA do preço de abertura
        sl_ok = sl < open_price
        tp_ok = tp > open_price
        
        sl_status = "✅ CORRETO" if sl_ok else "🔴 INVERTIDO"
        tp_status = "✅ CORRETO" if tp_ok else "🔴 INVERTIDO"
        
    else:  # SELL
        # SL deve estar ACIMA do preço de abertura
        # TP deve estar ABAIXO do preço de abertura
        sl_ok = sl > open_price
        tp_ok = tp < open_price
        
        sl_status = "✅ CORRETO" if sl_ok else "🔴 INVERTIDO"
        tp_status = "✅ CORRETO" if tp_ok else "🔴 INVERTIDO"
    
    print(f"{ticket:<12} | {strat:<18} | {tipo_str:<4} | {open_price:>8.2f} | {sl:>8.2f} | {tp:>8.2f} | {sl_status:<15} | {tp_status:<15}")
    
    if not sl_ok or not tp_ok:
        problems.append({
            'ticket': ticket,
            'type': tipo_str,
            'open': open_price,
            'sl': sl,
            'tp': tp,
            'sl_ok': sl_ok,
            'tp_ok': tp_ok
        })

conn.close()
mt5.shutdown()

print("\n" + "="*100)

if problems:
    print(f"\n🚨 PROBLEMAS ENCONTRADOS: {len(problems)} trades com SL/TP incorretos!")
    print("\nDETALHES:")
    for p in problems:
        print(f"\n  Ticket {p['ticket']} ({p['type']}):")
        print(f"    Open: {p['open']:.2f}")
        print(f"    SL:   {p['sl']:.2f}  {'❌ Deveria estar ' + ('ABAIXO' if p['type'] == 'BUY' else 'ACIMA') if not p['sl_ok'] else '✅'}")
        print(f"    TP:   {p['tp']:.2f}  {'❌ Deveria estar ' + ('ACIMA' if p['type'] == 'BUY' else 'ABAIXO') if not p['tp_ok'] else '✅'}")
else:
    print("\n✅ Todos os trades têm SL/TP configurados corretamente!")

print("\n")
