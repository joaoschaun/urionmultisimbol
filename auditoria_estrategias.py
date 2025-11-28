import sqlite3
import pandas as pd
from datetime import datetime, timedelta

print("\n" + "="*100)
print("🔍 AUDITORIA COMPLETA DAS ESTRATÉGIAS")
print("="*100 + "\n")

conn = sqlite3.connect('data/strategy_stats.db')

# 1. PERFORMANCE POR ESTRATÉGIA
print("📊 1. PERFORMANCE POR ESTRATÉGIA\n")
print(f"{'Estratégia':<20} {'Total':<8} {'Wins':<8} {'Losses':<8} {'Win%':<8} {'Profit':<15} {'Avg Win':<12} {'Avg Loss':<12} {'Profit Factor'}")
print("-" * 130)

query = """
SELECT 
    strategy_name,
    COUNT(*) as total,
    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
    SUM(profit) as total_profit,
    AVG(CASE WHEN profit > 0 THEN profit END) as avg_win,
    AVG(CASE WHEN profit < 0 THEN profit END) as avg_loss,
    SUM(CASE WHEN profit > 0 THEN profit ELSE 0 END) as total_wins,
    SUM(CASE WHEN profit < 0 THEN ABS(profit) ELSE 0 END) as total_losses
FROM strategy_trades
WHERE close_time IS NOT NULL
GROUP BY strategy_name
ORDER BY total_profit DESC
"""

df = pd.read_sql_query(query, conn)

for _, row in df.iterrows():
    win_pct = (row['wins'] / row['total'] * 100) if row['total'] > 0 else 0
    profit_factor = (row['total_wins'] / row['total_losses']) if row['total_losses'] > 0 else 0
    
    print(f"{row['strategy_name']:<20} {row['total']:<8} {row['wins']:<8} {row['losses']:<8} "
          f"{win_pct:<7.1f}% ${row['total_profit']:<14.2f} ${row['avg_win'] or 0:<11.2f} "
          f"${row['avg_loss'] or 0:<11.2f} {profit_factor:.2f}")

# 2. TRADES RECENTES (ÚLTIMAS 24H)
print("\n\n📈 2. TRADES RECENTES (ÚLTIMAS 24 HORAS)\n")
query_recent = """
SELECT strategy_name, ticket, profit, 
       datetime(open_time) as open_time,
       datetime(close_time) as close_time,
       CAST((julianday(close_time) - julianday(open_time)) * 24 * 60 AS INTEGER) as duration_min
FROM strategy_trades
WHERE close_time > datetime('now', '-24 hours')
ORDER BY close_time DESC
LIMIT 20
"""

df_recent = pd.read_sql_query(query_recent, conn)
if len(df_recent) > 0:
    print(f"{'Ticket':<12} {'Estratégia':<20} {'Duração':<12} {'Profit':<15} {'Aberto':<20} {'Fechado':<20}")
    print("-" * 100)
    for _, row in df_recent.iterrows():
        print(f"{row['ticket']:<12} {row['strategy_name']:<20} {row['duration_min']:<11}min "
              f"${row['profit']:<14.2f} {row['open_time']:<20} {row['close_time']:<20}")
else:
    print("⚠️ Nenhum trade nas últimas 24 horas")

# 3. ANÁLISE DE DURAÇÃO
print("\n\n⏱️ 3. ANÁLISE DE DURAÇÃO DOS TRADES\n")
query_duration = """
SELECT 
    strategy_name,
    AVG(CAST((julianday(close_time) - julianday(open_time)) * 24 * 60 AS INTEGER)) as avg_duration_min,
    MIN(CAST((julianday(close_time) - julianday(open_time)) * 24 * 60 AS INTEGER)) as min_duration_min,
    MAX(CAST((julianday(close_time) - julianday(open_time)) * 24 * 60 AS INTEGER)) as max_duration_min
FROM strategy_trades
WHERE close_time IS NOT NULL
GROUP BY strategy_name
"""

df_duration = pd.read_sql_query(query_duration, conn)
print(f"{'Estratégia':<20} {'Média':<15} {'Mínimo':<15} {'Máximo'}")
print("-" * 70)
for _, row in df_duration.iterrows():
    print(f"{row['strategy_name']:<20} {row['avg_duration_min']:<14.1f}min {row['min_duration_min']:<14.0f}min {row['max_duration_min']:.0f}min")

# 4. ANÁLISE DE STOP LOSS E TAKE PROFIT
print("\n\n🎯 4. ANÁLISE DE SL/TP (Como os trades fecham)\n")
query_exit = """
SELECT 
    strategy_name,
    COUNT(*) as total,
    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as hit_tp,
    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as hit_sl,
    AVG(ABS(open_price - sl)) as avg_sl_distance,
    AVG(ABS(tp - open_price)) as avg_tp_distance,
    AVG(ABS(open_price - sl)) / AVG(ABS(tp - open_price)) as risk_reward_ratio
FROM strategy_trades
WHERE close_time IS NOT NULL
GROUP BY strategy_name
"""

df_exit = pd.read_sql_query(query_exit, conn)
print(f"{'Estratégia':<20} {'Total':<8} {'Hit TP':<8} {'Hit SL':<8} {'SL Dist':<12} {'TP Dist':<12} {'RR Ratio'}")
print("-" * 90)
for _, row in df_exit.iterrows():
    print(f"{row['strategy_name']:<20} {row['total']:<8} {row['hit_tp']:<8} {row['hit_sl']:<8} "
          f"${row['avg_sl_distance']:<11.2f} ${row['avg_tp_distance']:<11.2f} 1:{row['risk_reward_ratio']:.2f}")

# 5. ANÁLISE DE CONFIANÇA DOS SINAIS
print("\n\n💪 5. ANÁLISE DE CONFIANÇA DOS SINAIS\n")
query_confidence = """
SELECT 
    strategy_name,
    AVG(signal_confidence) * 100 as avg_confidence,
    MIN(signal_confidence) * 100 as min_confidence,
    MAX(signal_confidence) * 100 as max_confidence,
    AVG(CASE WHEN profit > 0 THEN signal_confidence ELSE NULL END) * 100 as avg_conf_wins,
    AVG(CASE WHEN profit < 0 THEN signal_confidence ELSE NULL END) * 100 as avg_conf_losses
FROM strategy_trades
WHERE close_time IS NOT NULL AND signal_confidence IS NOT NULL
GROUP BY strategy_name
"""

df_conf = pd.read_sql_query(query_confidence, conn)
print(f"{'Estratégia':<20} {'Conf Média':<12} {'Conf Min':<12} {'Conf Max':<12} {'Conf Wins':<12} {'Conf Losses'}")
print("-" * 90)
for _, row in df_conf.iterrows():
    print(f"{row['strategy_name']:<20} {row['avg_confidence']:<11.1f}% {row['min_confidence']:<11.1f}% "
          f"{row['max_confidence']:<11.1f}% {row['avg_conf_wins'] or 0:<11.1f}% {row['avg_conf_losses'] or 0:.1f}%")

# 6. SEQUÊNCIAS DE WINS/LOSSES
print("\n\n🎲 6. MAIOR SEQUÊNCIA DE WINS/LOSSES POR ESTRATÉGIA\n")

query_all = """
SELECT strategy_name, profit, close_time
FROM strategy_trades
WHERE close_time IS NOT NULL
ORDER BY strategy_name, close_time
"""

df_all = pd.read_sql_query(query_all, conn)

print(f"{'Estratégia':<20} {'Maior Seq Wins':<18} {'Maior Seq Losses':<18} {'Seq Atual'}")
print("-" * 80)

for strategy in df_all['strategy_name'].unique():
    df_strat = df_all[df_all['strategy_name'] == strategy]
    
    # Calcular sequências
    max_win_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0
    current_streak = 0
    last_was_win = None
    
    for profit in df_strat['profit']:
        is_win = profit > 0
        
        if is_win:
            current_win_streak += 1
            current_loss_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
        else:
            current_loss_streak += 1
            current_win_streak = 0
            max_loss_streak = max(max_loss_streak, current_loss_streak)
        
        if last_was_win is None:
            last_was_win = is_win
            current_streak = 1
        elif last_was_win == is_win:
            current_streak += 1
        else:
            current_streak = 1
            last_was_win = is_win
    
    current_type = "wins" if last_was_win else "losses"
    print(f"{strategy:<20} {max_win_streak:<18} {max_loss_streak:<18} {current_streak} {current_type}")

# 7. RESUMO GERAL E RECOMENDAÇÕES
print("\n\n" + "="*100)
print("📋 7. RESUMO E RECOMENDAÇÕES")
print("="*100 + "\n")

total_trades = df['total'].sum()
total_profit = df['total_profit'].sum()
total_wins = df['wins'].sum()
total_losses = df['losses'].sum()
overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

print(f"Total de Trades: {total_trades}")
print(f"Win Rate Geral: {overall_win_rate:.1f}%")
print(f"Profit Total: ${total_profit:.2f}")
print(f"\n🚨 PROBLEMAS CRÍTICOS IDENTIFICADOS:\n")

# Identificar estratégias problemáticas
for _, row in df.iterrows():
    win_pct = (row['wins'] / row['total'] * 100) if row['total'] > 0 else 0
    profit_factor = (row['total_wins'] / row['total_losses']) if row['total_losses'] > 0 else 0
    
    problems = []
    
    if win_pct < 10:
        problems.append(f"❌ Win rate MUITO BAIXO ({win_pct:.1f}%)")
    
    if profit_factor < 0.5:
        problems.append(f"❌ Profit Factor péssimo ({profit_factor:.2f})")
    
    if row['total_profit'] < -100:
        problems.append(f"❌ Prejuízo alto (${row['total_profit']:.2f})")
    
    if row['avg_win'] and row['avg_loss'] and abs(row['avg_loss']) > row['avg_win'] * 2:
        problems.append(f"❌ Losses médios ({row['avg_loss']:.2f}) >> Wins médios ({row['avg_win']:.2f})")
    
    if problems:
        print(f"\n🔴 {row['strategy_name']}:")
        for problem in problems:
            print(f"   {problem}")
        print(f"   📊 Trades: {row['total']} | Wins: {row['wins']} | Losses: {row['losses']}")
        print(f"   💰 Profit: ${row['total_profit']:.2f}")

print("\n\n✅ RECOMENDAÇÕES:\n")
print("1. 🛑 PAUSAR IMEDIATAMENTE estratégias com win rate < 10%")
print("2. 🔧 REVISAR parâmetros de SL/TP (risk/reward ratio)")
print("3. 📊 AUMENTAR confiança mínima para entrada (> 70%)")
print("4. ⏱️ ANALISAR timeframes - podem estar inadequados")
print("5. 🎯 BACKTESTING com dados históricos antes de reativar")
print("6. 💡 CONSIDERAR usar apenas estratégias com profit factor > 1.0")

conn.close()

print("\n" + "="*100)
print("FIM DA AUDITORIA")
print("="*100 + "\n")
