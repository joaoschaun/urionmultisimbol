"""Script para analisar o database de estratégias"""
import sqlite3
import os

db_path = 'data/strategy_stats.db'

if not os.path.exists(db_path):
    print("Database não existe!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Listar tabelas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=" * 70)
print("TABELAS NO DATABASE:")
print("=" * 70)

for table in tables:
    table_name = table[0]
    print(f"\n📊 Tabela: {table_name}")
    print("-" * 50)
    
    # Schema da tabela
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print("Colunas:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Quantidade de registros
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"\nTotal de registros: {count}")
    
    # Amostra de dados
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()
        print("\nÚltimos registros:")
        for row in rows:
            print(f"  {row}")

conn.close()
print("\n" + "=" * 70)
