"""
Análise completa das operações pós-atualizações
Verifica se os módulos estão aprendendo corretamente
"""
import sqlite3
from datetime import datetime, timedelta
import json

def analyze_post_updates():
    conn = sqlite3.connect('data/strategy_stats.db')
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("ANÁLISE PÓS-ATUALIZAÇÕES - APRENDIZADO DOS MÓDULOS")
    print("="*80)
    
    # 1. TRADES RECENTES (últimas 24h)
    print("\n📊 TRADES DAS ÚLTIMAS 24 HORAS:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT ticket, strategy, action, open_price, close_price, 
               profit, confidence, open_time, close_time
        FROM strategy_trades 
        WHERE open_time >= datetime('now', '-1 day')
        ORDER BY open_time DESC
    """)
    
    recent_trades = cursor.fetchall()
    
    if recent_trades:
        for trade in recent_trades:
            ticket, strategy, action, open_p, close_p, profit, conf, open_t, close_t = trade
            status = "🟢 WIN" if profit and profit > 0 else "🔴 LOSS" if profit and profit < 0 else "⚪ BREAK-EVEN"
            print(f"{status} | Ticket: {ticket} | {strategy:15} | {action:4} | "
                  f"Entrada: {open_p:.2f} | Saída: {close_p if close_p else 'ABERTA'} | "
                  f"Profit: ${profit if profit else 0:.2f} | Conf: {conf:.1f}%")
    else:
        print("❌ Nenhum trade nas últimas 24 horas")
    
    # 2. ESTATÍSTICAS POR ESTRATÉGIA (pós-atualização)
    print("\n\n📈 PERFORMANCE POR ESTRATÉGIA (Trades Recentes):")
    print("-" * 80)
    
    cursor.execute("""
        SELECT strategy,
               COUNT(*) as total,
               SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
               SUM(profit) as total_profit,
               AVG(profit) as avg_profit,
               AVG(confidence) as avg_confidence,
               MAX(profit) as max_win,
               MIN(profit) as max_loss
        FROM strategy_trades
        WHERE open_time >= datetime('now', '-7 days')
        AND close_time IS NOT NULL
        GROUP BY strategy
        ORDER BY total_profit DESC
    """)
    
    strategies = cursor.fetchall()
    
    if strategies:
        for strat in strategies:
            name, total, wins, losses, profit, avg_p, avg_conf, max_w, max_l = strat
            winrate = (wins / total * 100) if total > 0 else 0
            
            print(f"\n{name.upper()}:")
            print(f"  Trades: {total} | Wins: {wins} ({winrate:.1f}%) | Losses: {losses}")
            print(f"  Profit Total: ${profit:.2f} | Avg: ${avg_p:.2f}")
            print(f"  Confiança Média: {avg_conf:.1f}%")
            print(f"  Melhor Win: ${max_w:.2f} | Pior Loss: ${max_l:.2f}")
    else:
        print("❌ Sem dados suficientes (últimos 7 dias)")
    
    # 3. VERIFICAR APRENDIZADO DO STRATEGY LEARNER
    print("\n\n🧠 ANÁLISE DO APRENDIZADO (ml_learning_data.json):")
    print("-" * 80)
    
    try:
        with open('data/ml_learning_data.json', 'r') as f:
            learning_data = json.load(f)
        
        for strategy, data in learning_data.items():
            print(f"\n{strategy.upper()}:")
            print(f"  Samples: {data.get('sample_count', 0)}")
            print(f"  Confiança Ótima: {data.get('optimal_confidence', 0):.2f}")
            print(f"  Win Rate: {data.get('win_rate', 0):.2%}")
            print(f"  Avg Profit: ${data.get('avg_profit', 0):.2f}")
            print(f"  Total Profit: ${data.get('total_profit', 0):.2f}")
            
            # Verificar se está aprendendo
            if data.get('sample_count', 0) >= 10:
                if data.get('win_rate', 0) > 0.4:
                    print(f"  ✅ Aprendizado: POSITIVO (Win Rate > 40%)")
                else:
                    print(f"  ⚠️  Aprendizado: AJUSTANDO (Win Rate < 40%)")
            else:
                print(f"  📚 Aprendizado: COLETANDO DADOS (precisa mais samples)")
    
    except FileNotFoundError:
        print("❌ Arquivo ml_learning_data.json não encontrado")
    
    # 4. VERIFICAR CORREÇÕES DE BUGS
    print("\n\n🔧 VERIFICAÇÃO DAS CORREÇÕES:")
    print("-" * 80)
    
    # Bug 1: Close Price
    cursor.execute("""
        SELECT COUNT(*) as sem_close_price
        FROM strategy_trades
        WHERE close_time IS NOT NULL AND (close_price IS NULL OR close_price = 0)
    """)
    sem_close = cursor.fetchone()[0]
    
    if sem_close == 0:
        print("✅ Bug Close Price: CORRIGIDO (todos os trades fechados têm close_price)")
    else:
        print(f"⚠️  Bug Close Price: {sem_close} trades sem close_price")
    
    # Bug 2: Confidence (não deve ter valores > 100)
    cursor.execute("""
        SELECT COUNT(*) as conf_errada
        FROM strategy_trades
        WHERE confidence > 100
    """)
    conf_errada = cursor.fetchone()[0]
    
    if conf_errada == 0:
        print("✅ Bug Confidence: CORRIGIDO (nenhum valor > 100%)")
    else:
        print(f"⚠️  Bug Confidence: {conf_errada} trades com confidence > 100%")
    
    # Bug 3: SL/TP (verificar se estão na proporção correta)
    print("\n✅ Bug SL/TP: Verificar nos trades ativos (config: SL=$50, TP=$150)")
    
    # 5. COMPARAÇÃO ANTES vs DEPOIS
    print("\n\n📊 COMPARAÇÃO HISTÓRICO vs PÓS-CORREÇÕES:")
    print("-" * 80)
    
    # Histórico (antes de 24/11/2025)
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
    
    # Pós-correções (após 24/11/2025 19:00)
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
    pos_correcao = cursor.fetchone()
    
    if historico and historico[0] > 0:
        h_total, h_wins, h_avg, h_profit = historico
        h_winrate = (h_wins / h_total * 100) if h_total > 0 else 0
        
        print("\nHISTÓRICO (antes das correções):")
        print(f"  Trades: {h_total} | Win Rate: {h_winrate:.1f}%")
        print(f"  Profit Médio: ${h_avg:.2f} | Profit Total: ${h_profit:.2f}")
    
    if pos_correcao and pos_correcao[0] > 0:
        p_total, p_wins, p_avg, p_profit = pos_correcao
        p_winrate = (p_wins / p_total * 100) if p_total > 0 else 0
        
        print("\nPÓS-CORREÇÕES (após 24/11/2025 19:00):")
        print(f"  Trades: {p_total} | Win Rate: {p_winrate:.1f}%")
        print(f"  Profit Médio: ${p_avg:.2f} | Profit Total: ${p_profit:.2f}")
        
        if historico and historico[0] > 0:
            melhoria_wr = p_winrate - h_winrate
            melhoria_profit = p_avg - h_avg
            
            print(f"\n{'🚀 MELHORIA' if melhoria_wr > 0 else '📉 PIORA'}:")
            print(f"  Win Rate: {melhoria_wr:+.1f} pontos percentuais")
            print(f"  Profit Médio: ${melhoria_profit:+.2f}")
    else:
        print("\nPÓS-CORREÇÕES: Aguardando mais trades para análise comparativa")
    
    # 6. POSIÇÕES ABERTAS ATUALMENTE
    print("\n\n💼 POSIÇÕES ABERTAS NO MOMENTO:")
    print("-" * 80)
    
    cursor.execute("""
        SELECT ticket, strategy, action, open_price, confidence, open_time
        FROM strategy_trades
        WHERE close_time IS NULL
        ORDER BY open_time DESC
    """)
    
    open_positions = cursor.fetchall()
    
    if open_positions:
        for pos in open_positions:
            ticket, strategy, action, price, conf, time = pos
            print(f"🔵 Ticket: {ticket} | {strategy:15} | {action:4} | "
                  f"Entrada: {price:.2f} | Conf: {conf:.1f}% | Tempo: {time}")
    else:
        print("✅ Nenhuma posição aberta no momento")
    
    print("\n" + "="*80)
    
    conn.close()

if __name__ == "__main__":
    analyze_post_updates()
