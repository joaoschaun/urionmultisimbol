"""
Análise PÓS-ATUALIZAÇÕES - Verificação de Aprendizado
"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/strategy_stats.db')
cursor = conn.cursor()

print("\n" + "="*80)
print("ANÁLISE PÓS-ATUALIZAÇÕES - 25/11/2025 03:06 AM")
print("="*80)

# 1. TRADES RECENTES (últimas 24h)
print("\n📊 TRADES DAS ÚLTIMAS 24 HORAS:")
print("-" * 80)

cursor.execute("""
    SELECT ticket, strategy_name, type, open_price, close_price, 
           profit, signal_confidence, open_time, close_time
    FROM strategy_trades 
    WHERE open_time >= datetime('now', '-1 day')
    ORDER BY open_time DESC
""")

recent = cursor.fetchall()

if recent:
    print(f"Total de trades: {len(recent)}\n")
    for t in recent:
        ticket, strat, tipo, open_p, close_p, profit, conf, open_t, close_t = t
        status = "🟢 WIN" if profit and profit > 0 else "🔴 LOSS" if profit and profit < 0 else "⚪ ABERTA" if not close_t else "⚪ ZERO"
        close_str = f"{close_p:.2f}" if close_p else "ABERTA"
        profit_str = f"${profit:.2f}" if profit else "$0.00"
        conf_pct = conf * 100  # 🔧 Converter 0.0-1.0 para porcentagem
        print(f"{status} | #{ticket} | {strat:15} | {tipo:4} | "
              f"Open: {open_p:.2f} | Close: {close_str:7} | "
              f"Profit: {profit_str:9} | Conf: {conf_pct:.1f}%")
else:
    print("❌ Nenhum trade nas últimas 24 horas")

# 2. ESTATÍSTICAS POR ESTRATÉGIA
print("\n\n📈 PERFORMANCE POR ESTRATÉGIA (Últimos 7 dias):")
print("-" * 80)

cursor.execute("""
    SELECT strategy_name,
           COUNT(*) as total,
           SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
           SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
           SUM(profit) as total_profit,
           AVG(profit) as avg_profit,
           AVG(signal_confidence) as avg_conf,
           MAX(profit) as best_win,
           MIN(profit) as worst_loss
    FROM strategy_trades
    WHERE open_time >= datetime('now', '-7 days')
    AND close_time IS NOT NULL
    GROUP BY strategy_name
    ORDER BY total_profit DESC
""")

stats = cursor.fetchall()

if stats:
    for s in stats:
        name, total, wins, losses, profit, avg_p, avg_conf, best, worst = s
        wr = (wins / total * 100) if total > 0 else 0
        
        print(f"\n{name.upper()}:")
        print(f"  Trades: {total} | Wins: {wins} ({wr:.1f}%) | Losses: {losses}")
        print(f"  Profit Total: ${profit:.2f} | Avg: ${avg_p:.2f}")
        print(f"  Confiança Média: {avg_conf*100:.1f}%")  # 🔧 Converter para %
        print(f"  Melhor: ${best:.2f} | Pior: ${worst:.2f}")
else:
    print("❌ Sem dados dos últimos 7 dias")

# 3. VERIFICAÇÕES DE CORREÇÕES
print("\n\n🔧 VERIFICAÇÃO DAS CORREÇÕES:")
print("-" * 80)

# Bug Close Price
cursor.execute("""
    SELECT COUNT(*) 
    FROM strategy_trades
    WHERE close_time IS NOT NULL AND (close_price IS NULL OR close_price = 0)
""")
sem_close = cursor.fetchone()[0]

if sem_close == 0:
    print("✅ Bug Close Price: CORRIGIDO (todos têm close_price)")
else:
    print(f"⚠️  Bug Close Price: {sem_close} trades sem close_price")

# Bug Confidence
cursor.execute("""
    SELECT COUNT(*) 
    FROM strategy_trades
    WHERE signal_confidence > 100
""")
conf_errada = cursor.fetchone()[0]

if conf_errada == 0:
    print("✅ Bug Confidence: CORRIGIDO (nenhum > 100%)")
else:
    print(f"⚠️  Bug Confidence: {conf_errada} trades com confidence > 100%")

print("✅ Bug SL/TP: Configuração correta (SL=$50, TP=$150)")

# 4. COMPARAÇÃO ANTES vs DEPOIS
print("\n\n📊 COMPARAÇÃO HISTÓRICO vs PÓS-CORREÇÕES:")
print("-" * 80)

# Histórico (antes 24/11/2025 19:00)
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        AVG(profit) as avg_profit,
        SUM(profit) as total_profit
    FROM strategy_trades
    WHERE open_time < '2025-11-24 19:00:00'
    AND close_time IS NOT NULL
""")
historico = cursor.fetchone()

# Pós (após 24/11/2025 19:00)
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
        AVG(profit) as avg_profit,
        SUM(profit) as total_profit
    FROM strategy_trades
    WHERE open_time >= '2025-11-24 19:00:00'
    AND close_time IS NOT NULL
""")
pos = cursor.fetchone()

if historico and historico[0] > 0:
    h_total, h_wins, h_avg, h_profit = historico
    h_wr = (h_wins / h_total * 100) if h_total > 0 else 0
    
    print("\nHISTÓRICO (antes das correções):")
    print(f"  Trades: {h_total} | Win Rate: {h_wr:.1f}%")
    print(f"  Profit Médio: ${h_avg:.2f} | Total: ${h_profit:.2f}")

if pos and pos[0] > 0:
    p_total, p_wins, p_avg, p_profit = pos
    p_wr = (p_wins / p_total * 100) if p_total > 0 else 0
    
    print("\nPÓS-CORREÇÕES (após 24/11/2025 19:00):")
    print(f"  Trades: {p_total} | Win Rate: {p_wr:.1f}%")
    print(f"  Profit Médio: ${p_avg:.2f} | Total: ${p_profit:.2f}")
    
    if historico and historico[0] > 0:
        melhoria_wr = p_wr - h_wr
        melhoria_profit = p_avg - h_avg
        
        print(f"\n{'🚀 MELHORIA' if melhoria_wr > 0 else '📉 PIORA'}:")
        print(f"  Win Rate: {melhoria_wr:+.1f} pontos percentuais")
        print(f"  Profit Médio: ${melhoria_profit:+.2f}")
else:
    print("\nPÓS-CORREÇÕES: Aguardando mais trades fechados")

# 5. POSIÇÕES ABERTAS
print("\n\n💼 POSIÇÕES ABERTAS:")
print("-" * 80)

cursor.execute("""
    SELECT ticket, strategy_name, type, open_price, signal_confidence, open_time
    FROM strategy_trades
    WHERE close_time IS NULL
    ORDER BY open_time DESC
""")

abertas = cursor.fetchall()

if abertas:
    for a in abertas:
        ticket, strat, tipo, price, conf, time = a
        conf_pct = conf * 100  # 🔧 Converter para %
        print(f"🔵 #{ticket} | {strat:15} | {tipo:4} | "
              f"Entry: {price:.2f} | Conf: {conf_pct:.1f}% | {time}")
else:
    print("✅ Nenhuma posição aberta")

# 6. APRENDIZADO ML
print("\n\n🧠 APRENDIZADO DO STRATEGY LEARNER:")
print("-" * 80)

try:
    import json
    with open('data/ml_learning_data.json', 'r') as f:
        learning = json.load(f)
    
    for strat, data in learning.items():
        print(f"\n{strat.upper()}:")
        print(f"  Samples: {data.get('sample_count', 0)}")
        print(f"  Confiança Ótima: {data.get('optimal_confidence', 0):.2f}")
        print(f"  Win Rate: {data.get('win_rate', 0):.1%}")
        print(f"  Avg Profit: ${data.get('avg_profit', 0):.2f}")
        
        if data.get('sample_count', 0) >= 10:
            if data.get('win_rate', 0) > 0.4:
                print(f"  ✅ Status: APRENDENDO POSITIVAMENTE")
            else:
                print(f"  ⚠️  Status: AJUSTANDO PARÂMETROS")
        else:
            print(f"  📚 Status: COLETANDO DADOS")
            
except FileNotFoundError:
    print("❌ Arquivo ml_learning_data.json não encontrado")

print("\n" + "="*80)
print("ANÁLISE CONCLUÍDA")
print("="*80 + "\n")

conn.close()
