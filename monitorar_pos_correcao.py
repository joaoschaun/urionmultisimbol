import sqlite3
from datetime import datetime, timedelta

print("\n" + "="*100)
print("📊 MONITORAMENTO PÓS-CORREÇÃO - Validar se SL/TP e Confidence estão corretos")
print("="*100 + "\n")

conn = sqlite3.connect('data/strategy_stats.db')
c = conn.cursor()

# 1. Verificar últimos 10 trades (após correção)
print("1️⃣ ÚLTIMOS 10 TRADES (Verificar SL/TP corrigidos):\n")

c.execute("""
    SELECT 
        ticket,
        strategy_name,
        type,
        open_price,
        sl,
        tp,
        ROUND(ABS(open_price - sl), 2) as sl_dist,
        ROUND(ABS(tp - open_price), 2) as tp_dist,
        ROUND(ABS(tp - open_price) / ABS(open_price - sl), 2) as rr_ratio,
        datetime(open_time) as opened,
        signal_confidence
    FROM strategy_trades
    ORDER BY open_time DESC
    LIMIT 10
""")

print(f"{'Ticket':<12} {'Strat':<18} {'Type':<6} {'Price':<8} {'SL Dist':<10} "
      f"{'TP Dist':<10} {'R:R':<8} {'Conf':<8} {'Opened'}")
print("-" * 120)

recent_trades = c.fetchall()
for row in recent_trades:
    conf_pct = f"{row[10]*100:.1f}%" if row[10] else "N/A"
    rr = f"1:{row[8]:.1f}" if row[8] else "N/A"
    print(f"{row[0]:<12} {row[1]:<18} {row[2]:<6} ${row[3]:<7.2f} "
          f"${row[6]:<9.2f} ${row[7]:<9.2f} {rr:<8} {conf_pct:<8} {row[9]}")

# 2. Validar se correções foram aplicadas
print("\n\n2️⃣ VALIDAÇÃO DAS CORREÇÕES:\n")

# Verificar confidence (deve estar 0.0-1.0)
c.execute("""
    SELECT 
        MIN(signal_confidence) as min_conf,
        MAX(signal_confidence) as max_conf,
        AVG(signal_confidence) as avg_conf
    FROM strategy_trades
    WHERE open_time > datetime('now', '-1 hour')
    AND signal_confidence IS NOT NULL
""")

conf_row = c.fetchone()
if conf_row and conf_row[0]:
    print(f"✅ Confidence (última hora):")
    print(f"   Min: {conf_row[0]:.4f} ({conf_row[0]*100:.2f}%)")
    print(f"   Max: {conf_row[1]:.4f} ({conf_row[1]*100:.2f}%)")
    print(f"   Avg: {conf_row[2]:.4f} ({conf_row[2]*100:.2f}%)")
    
    if conf_row[1] > 1.0:
        print(f"   ❌ PROBLEMA! Confidence > 1.0 (bug não corrigido)")
    else:
        print(f"   ✅ OK! Confidence entre 0.0-1.0")
else:
    print("⚠️ Nenhum trade na última hora com confidence")

print()

# Verificar SL/TP (deve ter R:R ~1:3)
c.execute("""
    SELECT 
        AVG(ABS(open_price - sl)) as avg_sl,
        AVG(ABS(tp - open_price)) as avg_tp,
        AVG(ABS(tp - open_price) / ABS(open_price - sl)) as avg_rr
    FROM strategy_trades
    WHERE open_time > datetime('now', '-1 hour')
    AND sl IS NOT NULL AND tp IS NOT NULL
""")

sltp_row = c.fetchone()
if sltp_row and sltp_row[0]:
    print(f"✅ SL/TP (última hora):")
    print(f"   Avg SL Distance: ${sltp_row[0]:.2f}")
    print(f"   Avg TP Distance: ${sltp_row[1]:.2f}")
    print(f"   Avg R:R Ratio: 1:{sltp_row[2]:.2f}")
    
    if sltp_row[0] < 30:
        print(f"   ⚠️ SL muito apertado (< $30) - pode bater fácil")
    elif sltp_row[0] > 70:
        print(f"   ⚠️ SL muito largo (> $70) - perda grande por trade")
    else:
        print(f"   ✅ SL adequado ($30-$70)")
    
    if sltp_row[2] < 2.0:
        print(f"   ❌ R:R muito baixo (< 2.0) - precisa win rate alto demais")
    elif sltp_row[2] > 4.0:
        print(f"   ⚠️ R:R muito alto (> 4.0) - TP pode ser difícil de atingir")
    else:
        print(f"   ✅ R:R adequado (2.0-4.0)")
else:
    print("⚠️ Nenhum trade na última hora com SL/TP")

# 3. Performance desde correção
print("\n\n3️⃣ PERFORMANCE PÓS-CORREÇÃO (Últimas 2 horas):\n")

c.execute("""
    SELECT 
        strategy_name,
        COUNT(*) as total,
        SUM(CASE WHEN close_time IS NOT NULL AND profit > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN close_time IS NOT NULL AND profit < 0 THEN 1 ELSE 0 END) as losses,
        SUM(CASE WHEN close_time IS NOT NULL THEN profit ELSE 0 END) as total_profit,
        AVG(CASE WHEN close_time IS NOT NULL AND profit > 0 THEN profit END) as avg_win,
        AVG(CASE WHEN close_time IS NOT NULL AND profit < 0 THEN profit END) as avg_loss
    FROM strategy_trades
    WHERE open_time > datetime('now', '-2 hours')
    GROUP BY strategy_name
""")

print(f"{'Estratégia':<20} {'Abertos':<10} {'Wins':<8} {'Losses':<8} "
      f"{'Profit':<12} {'Avg Win':<12} {'Avg Loss'}")
print("-" * 100)

perf_rows = c.fetchall()
if perf_rows:
    for row in perf_rows:
        wins = row[2] or 0
        losses = row[3] or 0
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        print(f"{row[0]:<20} {row[1]:<10} {wins:<8} {losses:<8} "
              f"${row[4] or 0:<11.2f} ${row[5] or 0:<11.2f} ${row[6] or 0:<11.2f}")
        
        if (wins + losses) > 0:
            print(f"                     Win Rate: {win_rate:.1f}%")
else:
    print("⚠️ Nenhum trade nas últimas 2 horas")

# 4. Trades em aberto
print("\n\n4️⃣ TRADES EM ABERTO AGORA:\n")

c.execute("""
    SELECT 
        ticket,
        strategy_name,
        type,
        open_price,
        sl,
        tp,
        datetime(open_time) as opened,
        ROUND((julianday('now') - julianday(open_time)) * 24 * 60, 0) as minutes_open
    FROM strategy_trades
    WHERE close_time IS NULL
    ORDER BY open_time DESC
""")

open_trades = c.fetchall()
if open_trades:
    print(f"{'Ticket':<12} {'Estratégia':<18} {'Type':<6} {'Price':<10} "
          f"{'SL':<10} {'TP':<10} {'Aberto há':<12} {'Tempo'}")
    print("-" * 100)
    
    for row in open_trades:
        minutes = int(row[7])
        time_str = f"{minutes//60}h{minutes%60}min" if minutes >= 60 else f"{minutes}min"
        print(f"{row[0]:<12} {row[1]:<18} {row[2]:<6} ${row[3]:<9.2f} "
              f"${row[4]:<9.2f} ${row[5]:<9.2f} {row[6]:<12} {time_str}")
    
    print(f"\n📊 Total de posições abertas: {len(open_trades)}")
else:
    print("✅ Nenhuma posição aberta no momento")

conn.close()

print("\n" + "="*100)
print("💡 RECOMENDAÇÕES:")
print("="*100 + "\n")
print("✅ Execute este script a cada hora para monitorar:")
print("   1. Se confidence está 0.0-1.0 (não 7500%)")
print("   2. Se SL está ~$50 e TP ~$150 (R:R 1:3)")
print("   3. Se win rate está melhorando (target: > 40%)")
print("   4. Se trades não ficam abertos > 6 horas")
print("\n🚨 Se win rate continuar < 20% após 50 trades, PAUSAR novamente!")
print("="*100 + "\n")
