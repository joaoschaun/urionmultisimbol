"""
Análise rápida do sistema
"""
import sqlite3

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

print("=" * 80)
print("ANÁLISE DO SISTEMA DE TRADING")
print("=" * 80)
print()

# 1. Resumo geral
print("1. RESUMO GERAL")
print("-" * 80)
c.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN close_time IS NOT NULL THEN 1 ELSE 0 END) as fechados,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
        ROUND(SUM(profit), 2) as total_profit
    FROM strategy_trades
""")
row = c.fetchone()
print(f"Total de trades no banco: {row[0]}")
print(f"Trades fechados: {row[1]}")
print(f"Wins: {row[2]}")
print(f"Losses: {row[3]}")
print(f"Profit total: ${row[4]:.2f}")
print()

# 2. Últimas 24 horas
print("2. ÚLTIMAS 24 HORAS")
print("-" * 80)
c.execute("""
    SELECT 
        strategy_name,
        COUNT(*) as total,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
        ROUND(SUM(profit), 2) as profit
    FROM strategy_trades
    WHERE open_time > datetime('now', '-24 hours')
    GROUP BY strategy_name
    ORDER BY profit DESC
""")
print(f"{'Estratégia':<25} {'Total':<8} {'Wins':<6} {'Loss':<6} {'Profit':<12}")
print("-" * 80)
for row in c.fetchall():
    print(f"{row[0]:<25} {row[1]:<8} {row[2]:<6} {row[3]:<6} ${row[4]:<11.2f}")
print()

# 3. Últimos 10 trades com profit != 0
print("3. ÚLTIMOS 10 TRADES COM RESULTADO")
print("-" * 80)
c.execute("""
    SELECT 
        ticket,
        strategy_name,
        ROUND(profit, 2) as profit,
        close_time
    FROM strategy_trades
    WHERE profit != 0 AND profit IS NOT NULL
    ORDER BY close_time DESC
    LIMIT 10
""")
print(f"{'Ticket':<12} {'Estratégia':<25} {'Profit':<12} {'Fechado'}")
print("-" * 80)
for row in c.fetchall():
    emoji = "🟢" if row[2] > 0 else "🔴"
    print(f"{row[0]:<12} {row[1]:<25} {emoji} ${row[2]:<10.2f} {row[3]}")
print()

# 4. Performance por estratégia (apenas trades com profit)
print("4. PERFORMANCE POR ESTRATÉGIA (trades com profit registrado)")
print("-" * 80)
c.execute("""
    SELECT 
        strategy_name,
        COUNT(*) as total,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        ROUND(AVG(profit), 2) as avg,
        ROUND(SUM(profit), 2) as total_profit,
        ROUND(100.0 * SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as wr
    FROM strategy_trades
    WHERE profit IS NOT NULL AND profit != 0
    GROUP BY strategy_name
    ORDER BY total_profit DESC
""")
print(f"{'Estratégia':<25} {'Total':<8} {'Wins':<6} {'Avg':<12} {'Total':<12} {'WR%'}")
print("-" * 80)
for row in c.fetchall():
    print(f"{row[0]:<25} {row[1]:<8} {row[2]:<6} ${row[3]:<11.2f} ${row[4]:<11.2f} {row[5]:.1f}%")
print()

# 5. Verificar aprendizagem
print("5. SISTEMA DE APRENDIZAGEM")
print("-" * 80)
import os
import json

if os.path.exists('data/strategy_learning.json'):
    with open('data/strategy_learning.json', 'r') as f:
        learning = json.load(f)
    
    print(f"{'Estratégia':<25} {'Min Conf':<12} {'Trades':<10} {'Última Atualização'}")
    print("-" * 80)
    for strat, data in learning.items():
        print(f"{strat:<25} {data.get('min_confidence', 0):<12.2f} {data.get('total_trades_learned', 0):<10} {data.get('last_adjustment', 'N/A')}")
else:
    print("⚠️  Arquivo strategy_learning.json não encontrado")

print()

# 6. Verificar trades sem profit
print("6. DIAGNÓSTICO - TRADES SEM PROFIT")
print("-" * 80)
c.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN close_time IS NULL THEN 1 ELSE 0 END) as sem_close,
        SUM(CASE WHEN profit IS NULL OR profit = 0 THEN 1 ELSE 0 END) as sem_profit
    FROM strategy_trades
    WHERE open_time > datetime('now', '-24 hours')
""")
row = c.fetchone()
print(f"Trades nas últimas 24h: {row[0]}")
print(f"Sem close_time: {row[1]}")
print(f"Sem profit (NULL ou 0): {row[2]}")

if row[2] > 0:
    print()
    print("⚠️  ATENÇÃO: Existem trades sem profit registrado!")
    print("Possíveis causas:")
    print("  1. Trades ainda abertos (normal)")
    print("  2. Trades fechados mas OrderManager não detectou")
    print("  3. Broker demo limpou histórico muito rápido")

conn.close()

print()
print("=" * 80)
