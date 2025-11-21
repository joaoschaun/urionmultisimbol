#!/usr/bin/env python3
"""Visualizar últimos trades"""

import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT ticket, strategy_name, type, profit, open_price, sl, tp, open_time
    FROM strategy_trades 
    ORDER BY open_time DESC 
    LIMIT 30
''')

print("\n=== ÚLTIMOS 30 TRADES ===")
print(f"{'Ticket':<12} | {'Estratégia':<18} | {'Tipo':<4} | {'Profit':>8} | {'Open':>8} | {'SL':>8} | {'TP':>8}")
print("-" * 100)

for row in cursor.fetchall():
    ticket, strat, tipo, profit, open_price, sl, tp, open_time = row
    tipo_str = "BUY" if tipo == 0 else "SELL"
    profit = profit or 0.0
    emoji = "🟢" if profit > 0 else "🔴" if profit < 0 else "⚪"
    print(f"{emoji} {ticket:<10} | {strat:<18} | {tipo_str:<4} | ${profit:>7.2f} | {open_price:>8.2f} | {sl:>8.2f} | {tp:>8.2f}")

conn.close()
