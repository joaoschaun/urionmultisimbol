import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

print("\n" + "=" * 80)
print("ESTRUTURA DA TABELA strategy_trades")
print("=" * 80)

c.execute('PRAGMA table_info(strategy_trades)')
columns = c.fetchall()

print(f"\n{'ID':<5} {'Nome':<25} {'Tipo':<15} {'NotNull':<10} {'Default':<10} {'PK'}")
print("-" * 80)
for col in columns:
    print(f"{col[0]:<5} {col[1]:<25} {col[2]:<15} {col[3]:<10} {str(col[4]):<10} {col[5]}")

print("\n" + "=" * 80)
print("EXEMPLO DE DADOS (Ticket 207855307)")
print("=" * 80)

c.execute("SELECT * FROM strategy_trades WHERE ticket = 207855307")
row = c.fetchone()

if row:
    print()
    for i, col in enumerate(columns):
        col_name = col[1]
        col_value = row[i]
        print(f"Coluna {i:2d} ({col_name:20s}): {col_value}")

conn.close()
