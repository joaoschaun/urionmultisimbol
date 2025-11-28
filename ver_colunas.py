import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
cursor = conn.cursor()

# Pegar estrutura da tabela
cursor.execute("PRAGMA table_info(strategy_trades)")
columns = cursor.fetchall()

print("Colunas da tabela strategy_trades:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()
