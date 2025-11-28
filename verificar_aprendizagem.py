"""
Verificar sistema de aprendizagem e estatísticas
"""
import sqlite3
from datetime import datetime, timedelta

print("=" * 80)
print("VERIFICAÇÃO DO SISTEMA DE APRENDIZAGEM")
print("=" * 80)
print()

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

# 1. Verificar trades com close_time e profit
print("=== 1. TRADES COM DADOS COMPLETOS ===")
c.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN close_time IS NOT NULL THEN 1 ELSE 0 END) as com_close,
        SUM(CASE WHEN profit IS NOT NULL AND profit != 0 THEN 1 ELSE 0 END) as com_profit
    FROM strategy_trades
""")
row = c.fetchone()
print(f"Total de trades: {row[0]}")
print(f"Com close_time: {row[1]} ({row[1]/row[0]*100:.1f}%)")
print(f"Com profit: {row[2]} ({row[2]/row[0]*100:.1f}%)")
print()

# 2. Verificar trades das últimas 24h
print("=== 2. TRADES DAS ÚLTIMAS 24 HORAS ===")
c.execute("""
    SELECT 
        strategy_name,
        COUNT(*) as total,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
        ROUND(AVG(profit), 2) as avg_profit,
        ROUND(SUM(profit), 2) as total_profit
    FROM strategy_trades
    WHERE open_time > datetime('now', '-24 hours')
    GROUP BY strategy_name
    ORDER BY total_profit DESC
""")
print(f"{'Estratégia':<20} {'Trades':<8} {'Wins':<6} {'Loss':<6} {'Avg':<10} {'Total':<10}")
print("-" * 80)
for row in c.fetchall():
    print(f"{row[0]:<20} {row[1]:<8} {row[2]:<6} {row[3]:<6} ${row[4]:<9.2f} ${row[5]:<9.2f}")
print()

# 3. Verificar dados de aprendizagem (strategy_daily_stats)
print("=== 3. ESTATÍSTICAS DIÁRIAS (ÚLTIMOS 7 DIAS) ===")
c.execute("""
    SELECT 
        strategy_name,
        date,
        total_trades,
        winning_trades,
        ROUND(avg_profit_per_trade, 2) as avg_profit,
        ROUND(win_rate * 100, 1) as win_rate_pct
    FROM strategy_daily_stats
    WHERE date > date('now', '-7 days')
    ORDER BY date DESC, strategy_name
    LIMIT 20
""")
print(f"{'Estratégia':<20} {'Data':<12} {'Trades':<8} {'Wins':<6} {'Avg':<10} {'WR%':<6}")
print("-" * 80)
for row in c.fetchall():
    print(f"{row[0]:<20} {row[1]:<12} {row[2]:<8} {row[3]:<6} ${row[4]:<9.2f} {row[5]:<6.1f}")
print()

# 4. Verificar ranking semanal
print("=== 4. RANKING SEMANAL (ÚLTIMAS 4 SEMANAS) ===")
c.execute("""
    SELECT 
        strategy_name,
        week_start,
        total_trades,
        winning_trades,
        ROUND(total_profit, 2) as profit,
        ROUND(win_rate * 100, 1) as win_rate_pct,
        ranking_score
    FROM strategy_weekly_ranking
    WHERE week_start > date('now', '-28 days')
    ORDER BY week_start DESC, ranking_score DESC
    LIMIT 15
""")
print(f"{'Estratégia':<20} {'Semana':<12} {'Trades':<8} {'Wins':<6} {'Profit':<10} {'WR%':<6} {'Score':<6}")
print("-" * 80)
for row in c.fetchall():
    print(f"{row[0]:<20} {row[1]:<12} {row[2]:<8} {row[3]:<6} ${row[4]:<9.2f} {row[5]:<6.1f} {row[6]:<6.1f}")
print()

# 5. Verificar últimos 10 trades fechados
print("=== 5. ÚLTIMOS 10 TRADES FECHADOS ===")
c.execute("""
    SELECT 
        ticket,
        strategy_name,
        type,
        ROUND(profit, 2) as profit,
        close_time,
        ROUND(signal_confidence * 100, 1) as conf_pct
    FROM strategy_trades
    WHERE close_time IS NOT NULL
    ORDER BY close_time DESC
    LIMIT 10
""")
print(f"{'Ticket':<12} {'Estratégia':<20} {'Tipo':<6} {'Profit':<10} {'Fecha':<20} {'Conf%':<6}")
print("-" * 80)
for row in c.fetchall():
    tipo = "BUY" if row[2] == 0 else "SELL"
    emoji = "🟢" if row[3] > 0 else "🔴"
    print(f"{row[0]:<12} {row[1]:<20} {tipo:<6} {emoji} ${row[3]:<8.2f} {row[4]:<20} {row[5]:<6.1f}")
print()

# 6. Performance geral por estratégia
print("=== 6. PERFORMANCE GERAL POR ESTRATÉGIA ===")
c.execute("""
    SELECT 
        strategy_name,
        COUNT(*) as total,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        ROUND(AVG(profit), 2) as avg_profit,
        ROUND(SUM(profit), 2) as total_profit,
        ROUND(SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as win_rate
    FROM strategy_trades
    WHERE close_time IS NOT NULL AND profit IS NOT NULL
    GROUP BY strategy_name
    ORDER BY total_profit DESC
""")
print(f"{'Estratégia':<20} {'Total':<8} {'Wins':<6} {'Avg':<10} {'Total':<12} {'WR%':<6}")
print("-" * 80)
total_trades = 0
total_profit = 0
for row in c.fetchall():
    print(f"{row[0]:<20} {row[1]:<8} {row[2]:<6} ${row[3]:<9.2f} ${row[4]:<11.2f} {row[5]:<6.1f}%")
    total_trades += row[1]
    total_profit += row[4]
print("-" * 80)
print(f"{'TOTAL':<20} {total_trades:<8} {'':<6} {'':<10} ${total_profit:<11.2f}")
print()

# 7. Verificar arquivo de aprendizagem
print("=== 7. VERIFICAR ARQUIVO DE APRENDIZAGEM ===")
import os
import json

learner_file = 'data/strategy_learning.json'
if os.path.exists(learner_file):
    with open(learner_file, 'r') as f:
        data = json.load(f)
    
    print("Estratégias com dados de aprendizagem:")
    for strategy, info in data.items():
        print(f"\n{strategy}:")
        print(f"  - min_confidence: {info.get('min_confidence', 'N/A')}")
        print(f"  - total_trades_learned: {info.get('total_trades_learned', 0)}")
        print(f"  - last_adjustment: {info.get('last_adjustment', 'N/A')}")
        
        winning_conditions = info.get('winning_conditions', [])
        print(f"  - winning_conditions: {len(winning_conditions)} registradas")
else:
    print("❌ Arquivo strategy_learning.json não encontrado")

conn.close()

print()
print("=" * 80)
print("VERIFICAÇÃO CONCLUÍDA")
print("=" * 80)
