import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
cursor = conn.cursor()

# Buscar o trade específico
cursor.execute('''
    SELECT ticket, strategy_name, type, volume, open_price, close_price, 
           sl, tp, profit, close_time, status 
    FROM strategy_trades 
    WHERE ticket = 207931286
    ORDER BY id DESC
''')

rows = cursor.fetchall()

print("\n" + "="*80)
print("TRADE 207931286 - DETALHES COMPLETOS")
print("="*80 + "\n")

if rows:
    for r in rows:
        print(f"Ticket: {r[0]}")
        print(f"Strategy: {r[1]}")
        print(f"Action: {r[2]}")
        print(f"Volume: {r[3]}")
        print(f"Open Price: {r[4]:.2f}")
        print(f"Close Price: {r[5] if r[5] else 'None (ainda aberta)'}")
        print(f"SL: {r[6]:.2f}")
        print(f"TP: {r[7]:.2f}")
        print(f"Profit: ${r[8] if r[8] else 0.0}")
        print(f"Status: {r[10]}")
        print(f"Close Time: {r[9] if r[9] else 'None'}")
        print("-" * 80)
else:
    print("❌ Trade não encontrado!")

# Buscar TODOS os trades recentes
cursor.execute('''
    SELECT ticket, strategy_name, type, volume, open_price, close_price, 
           profit, status, close_time
    FROM strategy_trades 
    ORDER BY id DESC 
    LIMIT 10
''')

recent_trades = cursor.fetchall()

print("\n" + "="*80)
print("ÚLTIMOS 10 TRADES NO DATABASE")
print("="*80 + "\n")
print(f"{'Ticket':<12} {'Strategy':<16} {'Action':<6} {'Vol':<6} {'Open':<9} {'Close':<9} {'Profit':<10} {'Status':<10}")
print("=" * 100)

for r in recent_trades:
    close_price = f"{r[5]:.2f}" if r[5] else "None"
    profit = f"${r[6]:.2f}" if r[6] else "$0.00"
    print(f"{r[0]:<12} {r[1]:<16} {r[2]:<6} {r[3]:<6} {r[4]:<9.2f} {close_price:<9} {profit:<10} {r[7]:<10}")

conn.close()
