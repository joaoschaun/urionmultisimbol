"""
Análise detalhada do Win Rate por estratégia
"""

import sqlite3
from datetime import datetime, timedelta

def analisar_winrate():
    """Analisa win rate geral e por estratégia"""
    
    conn = sqlite3.connect('data/strategy_stats.db')
    cursor = conn.cursor()
    
    print("\n" + "="*100)
    print(" "*35 + "ANÁLISE DE WIN RATE")
    print("="*100 + "\n")
    
    # 1. Win Rate Geral
    cursor.execute("""
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN profit = 0 THEN 1 ELSE 0 END) as breakeven,
            SUM(profit) as total_profit,
            AVG(profit) as avg_profit,
            AVG(CASE WHEN profit > 0 THEN profit END) as avg_win,
            AVG(CASE WHEN profit < 0 THEN profit END) as avg_loss,
            MAX(profit) as max_win,
            MIN(profit) as min_loss
        FROM strategy_trades
        WHERE status = 'closed'
    """)
    
    geral = cursor.fetchone()
    
    if geral[0] > 0:
        total, wins, losses, breakeven, total_profit, avg_profit, avg_win, avg_loss, max_win, min_loss = geral
        win_rate = (wins / total) * 100
        loss_rate = (losses / total) * 100
        
        # Profit Factor
        total_wins = avg_win * wins if avg_win else 0
        total_losses = abs(avg_loss * losses) if avg_loss else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # R:R Real
        rr_ratio = abs(avg_win / avg_loss) if avg_loss and avg_loss != 0 else 0
        
        print("📊 ESTATÍSTICAS GERAIS:")
        print("-" * 100)
        print(f"Total de Trades:      {total}")
        print(f"Wins (lucro):         {wins} ({win_rate:.1f}%)")
        print(f"Losses (prejuízo):    {losses} ({loss_rate:.1f}%)")
        print(f"Breakeven:            {breakeven}")
        print(f"\nProfit Total:         ${total_profit:.2f}")
        print(f"Profit Médio/Trade:   ${avg_profit:.2f}")
        print(f"\nWin Médio:            ${avg_win:.2f}" if avg_win else "\nWin Médio:            $0.00")
        print(f"Loss Médio:           ${avg_loss:.2f}" if avg_loss else "Loss Médio:           $0.00")
        print(f"\nMaior Ganho:          ${max_win:.2f}")
        print(f"Maior Perda:          ${min_loss:.2f}")
        print(f"\nProfit Factor:        {profit_factor:.2f}")
        print(f"R:R Real:             1:{rr_ratio:.2f}")
        print()
    
    # 2. Win Rate por Estratégia
    cursor.execute("""
        SELECT 
            strategy_name,
            COUNT(*) as total,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
            SUM(profit) as total_profit,
            AVG(profit) as avg_profit,
            AVG(CASE WHEN profit > 0 THEN profit END) as avg_win,
            AVG(CASE WHEN profit < 0 THEN profit END) as avg_loss,
            MAX(profit) as max_win,
            MIN(profit) as min_loss
        FROM strategy_trades
        WHERE status = 'closed'
        GROUP BY strategy_name
        ORDER BY total DESC
    """)
    
    estrategias = cursor.fetchall()
    
    print("="*100)
    print("📈 WIN RATE POR ESTRATÉGIA:")
    print("="*100)
    print(f"{'Estratégia':<18} {'Trades':<8} {'Wins':<8} {'Loss':<8} {'WinRate':<10} {'Profit':<12} {'Avg/Trade':<12} {'PF':<8}")
    print("-" * 100)
    
    for est in estrategias:
        nome, total, wins, losses, total_profit, avg_profit, avg_win, avg_loss, max_win, min_loss = est
        win_rate = (wins / total * 100) if total > 0 else 0
        
        # Profit Factor
        total_wins_value = avg_win * wins if avg_win else 0
        total_losses_value = abs(avg_loss * losses) if avg_loss else 1
        pf = total_wins_value / total_losses_value if total_losses_value > 0 else 0
        
        # Emoji de status
        if win_rate >= 50 and pf >= 1.5:
            emoji = "🟢"
        elif win_rate >= 40 or pf >= 1.2:
            emoji = "🟡"
        else:
            emoji = "🔴"
        
        print(f"{emoji} {nome:<16} {total:<8} {wins:<8} {losses:<8} {win_rate:<9.1f}% ${total_profit:<11.2f} ${avg_profit:<11.2f} {pf:<7.2f}")
    
    # 3. Análise Temporal (últimas 24h vs histórico completo)
    print("\n" + "="*100)
    print("⏰ COMPARAÇÃO TEMPORAL:")
    print("="*100)
    
    # Últimas 24 horas
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(profit) as total_profit
        FROM strategy_trades
        WHERE status = 'closed'
          AND close_time >= datetime('now', '-1 day')
    """)
    
    last_24h = cursor.fetchone()
    
    if last_24h[0] > 0:
        total_24h, wins_24h, profit_24h = last_24h
        wr_24h = (wins_24h / total_24h * 100) if total_24h > 0 else 0
        print(f"\n📅 Últimas 24 horas:")
        print(f"   Trades: {total_24h} | Win Rate: {wr_24h:.1f}% | Profit: ${profit_24h:.2f}")
    else:
        print(f"\n📅 Últimas 24 horas: Nenhum trade fechado")
    
    # Últimos 7 dias
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(profit) as total_profit
        FROM strategy_trades
        WHERE status = 'closed'
          AND close_time >= datetime('now', '-7 days')
    """)
    
    last_7d = cursor.fetchone()
    
    if last_7d[0] > 0:
        total_7d, wins_7d, profit_7d = last_7d
        wr_7d = (wins_7d / total_7d * 100) if total_7d > 0 else 0
        print(f"\n📅 Últimos 7 dias:")
        print(f"   Trades: {total_7d} | Win Rate: {wr_7d:.1f}% | Profit: ${profit_7d:.2f}")
    
    # 4. Série de Wins/Losses
    cursor.execute("""
        SELECT profit
        FROM strategy_trades
        WHERE status = 'closed'
        ORDER BY close_time DESC
        LIMIT 30
    """)
    
    ultimos_30 = cursor.fetchall()
    
    if ultimos_30:
        print("\n" + "="*100)
        print("📉 ÚLTIMOS 30 TRADES:")
        print("="*100)
        
        sequence = ""
        wins_seq = 0
        losses_seq = 0
        current_streak = 0
        current_type = None
        max_win_streak = 0
        max_loss_streak = 0
        
        for i, (profit,) in enumerate(ultimos_30):
            if profit > 0:
                sequence += "🟢"
                if current_type == 'win':
                    current_streak += 1
                else:
                    current_streak = 1
                    current_type = 'win'
                max_win_streak = max(max_win_streak, current_streak)
            elif profit < 0:
                sequence += "🔴"
                if current_type == 'loss':
                    current_streak += 1
                else:
                    current_streak = 1
                    current_type = 'loss'
                max_loss_streak = max(max_loss_streak, current_streak)
            else:
                sequence += "⚪"
                current_streak = 0
                current_type = None
            
            if (i + 1) % 10 == 0:
                sequence += " "
        
        print(f"\n{sequence}")
        print(f"\n   🟢 = Win | 🔴 = Loss | ⚪ = Breakeven")
        print(f"\n   Maior sequência de WINS:    {max_win_streak}")
        print(f"   Maior sequência de LOSSES:  {max_loss_streak}")
    
    # 5. Recomendações
    print("\n" + "="*100)
    print("💡 RECOMENDAÇÕES:")
    print("="*100)
    
    if win_rate < 40:
        print("\n⚠️  WIN RATE CRÍTICO (<40%):")
        print("   • Considere aumentar min_confidence para 80-85%")
        print("   • Revise os SL/TP - podem estar muito apertados")
        print("   • Pause estratégias com WR < 30%")
    elif win_rate < 50:
        print("\n🟡 WIN RATE MODERADO (40-50%):")
        print("   • Otimize os parâmetros de cada estratégia")
        print("   • Monitore o Profit Factor (ideal > 1.5)")
        print("   • Considere ajustar trailing stops")
    else:
        print("\n✅ WIN RATE SAUDÁVEL (>50%):")
        print("   • Continue monitorando a performance")
        print("   • Considere aumentar o volume gradualmente")
        print("   • Mantenha a disciplina nos parâmetros")
    
    if profit_factor < 1.0:
        print("\n🚨 PROFIT FACTOR NEGATIVO:")
        print("   • Losses médios > Wins médios")
        print("   • URGENTE: Revise completamente as estratégias")
        print("   • Considere pausar o bot até ajustar")
    elif profit_factor < 1.5:
        print("\n⚠️  PROFIT FACTOR BAIXO (<1.5):")
        print("   • Aumente o TP ou reduza o SL")
        print("   • Melhore a seletividade dos sinais")
    
    print("\n" + "="*100 + "\n")
    
    conn.close()

if __name__ == "__main__":
    analisar_winrate()
