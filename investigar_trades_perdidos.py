import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

# Tickets que aparecem no histórico MT5 como fechados
tickets_fechados_mt5 = [207855307, 207856745, 207861120, 207861221]

print("=" * 80)
print("INVESTIGAÇÃO: TRADES FECHADOS NÃO CONTABILIZADOS")
print("=" * 80)
print()

for ticket in tickets_fechados_mt5:
    c.execute("SELECT * FROM strategy_trades WHERE ticket = ?", (ticket,))
    row = c.fetchone()
    
    if row:
        print(f"Ticket {ticket}:")
        print(f"  Estratégia: {row[1]}")
        print(f"  Open Time: {row[4]}")
        print(f"  Close Time: {row[5] if row[5] else 'NULL'}")
        print(f"  Profit: ${row[6] if row[6] else 0:.2f}")
        print(f"  Status: {row[10] if len(row) > 10 else 'N/A'}")
    else:
        print(f"Ticket {ticket}: ❌ NÃO ENCONTRADO NO BANCO")
    print()

print()
print("RESUMO:")
print(f"Total de tickets verificados: {len(tickets_fechados_mt5)}")

c.execute("""
    SELECT COUNT(*) 
    FROM strategy_trades 
    WHERE ticket IN (?, ?, ?, ?)
""", tuple(tickets_fechados_mt5))

encontrados = c.fetchone()[0]
print(f"Tickets encontrados no banco: {encontrados}")
print(f"Tickets PERDIDOS: {len(tickets_fechados_mt5) - encontrados}")

conn.close()
