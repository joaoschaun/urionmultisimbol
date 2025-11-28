import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tabelas:", [r[0] for r in cursor.fetchall()])
conn.close()
