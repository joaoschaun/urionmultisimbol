#!/usr/bin/env python3
"""Análise crítica da performance do bot"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

def analisar_performance():
    db_path = Path("data/strategy_stats.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("🔍 ANÁLISE CRÍTICA DE PERFORMANCE DO BOT")
    print("="*80)
    
    # 1. Performance geral
    cursor.execute("""
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
            SUM(profit) as total_profit,
            AVG(profit) as avg_profit,
            MAX(profit) as max_win,
            MIN(profit) as max_loss
        FROM strategy_trades 
        WHERE close_time IS NOT NULL
    """)
    
    row = cursor.fetchone()
    if row and row[0] > 0:
        total, wins, losses, profit, avg, max_win, max_loss = row
        wr = (wins / total * 100) if total > 0 else 0
        
        print(f"\n📊 PERFORMANCE GERAL:")
        print(f"   Total de Trades: {total}")
        print(f"   Wins: {wins} | Losses: {losses}")
        print(f"   Win Rate: {wr:.1f}%")
        print(f"   Profit Total: ${profit:.2f}")
        print(f"   Profit Médio: ${avg:.2f}")
        print(f"   Maior Ganho: ${max_win:.2f}")
        print(f"   Maior Perda: ${max_loss:.2f}")
        
        # ALERTA: Win rate abaixo de 50%
        if wr < 50:
            print(f"\n   ⚠️  ALERTA CRÍTICO: Win Rate {wr:.1f}% está ABAIXO de 50%!")
        
        # ALERTA: Profit negativo
        if profit < 0:
            print(f"\n   🔴 ALERTA CRÍTICO: Bot está com prejuízo de ${profit:.2f}!")
    
    # 2. Performance por estratégia
    print(f"\n📈 PERFORMANCE POR ESTRATÉGIA:")
    print(f"{'Estratégia':<20} | {'Trades':>6} | {'Wins':>4} | {'WR':>6} | {'Profit':>10}")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            strategy_name,
            COUNT(*) as trades,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(profit) as total_profit
        FROM strategy_trades 
        WHERE close_time IS NOT NULL 
        GROUP BY strategy_name
        ORDER BY total_profit DESC
    """)
    
    for row in cursor.fetchall():
        name, trades, wins, profit = row
        wr = (wins / trades * 100) if trades > 0 else 0
        emoji = "🟢" if wr >= 60 else "🟡" if wr >= 50 else "🔴"
        print(f"{emoji} {name:<18} | {trades:>6} | {wins:>4} | {wr:>5.1f}% | ${profit:>9.2f}")
    
    # 3. Últimos 20 trades
    print(f"\n📋 ÚLTIMOS 20 TRADES:")
    print(f"{'Ticket':<12} | {'Estratégia':<18} | {'Tipo':<4} | {'Profit':>8} | {'Conf':>5} | {'Hora'}")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            ticket, strategy_name, type, profit, signal_confidence,
            close_time
        FROM strategy_trades 
        WHERE close_time IS NOT NULL 
        ORDER BY close_time DESC 
        LIMIT 20
    """)
    
    for row in cursor.fetchall():
        ticket, strat, tipo, profit, conf, close = row
        emoji = "🟢" if profit > 0 else "🔴"
        tipo_str = "BUY" if tipo == 0 else "SELL"
        print(f"{emoji} {ticket:<10} | {strat:<18} | {tipo_str:<4} | ${profit:>7.2f} | {conf:>4.0%} | {close}")
    
    # 4. Análise de risco
    print(f"\n⚠️  ANÁLISE DE RISCOS:")
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM strategy_trades 
        WHERE close_time IS NOT NULL 
        AND profit < -50
    """)
    big_losses = cursor.fetchone()[0]
    
    if big_losses > 0:
        print(f"   🔴 CRÍTICO: {big_losses} trades com perda > $50!")
    
    cursor.execute("""
        SELECT AVG(volume) 
        FROM strategy_trades 
        WHERE close_time IS NOT NULL
    """)
    avg_volume = cursor.fetchone()[0]
    if avg_volume:
        print(f"   Volume médio: {avg_volume:.2f} lotes")
    else:
        print(f"   Volume médio: N/A (sem trades fechados)")
    
    # 5. Trades nas últimas 24h
    cursor.execute("""
        SELECT 
            COUNT(*) as trades_24h,
            SUM(profit) as profit_24h
        FROM strategy_trades 
        WHERE close_time >= datetime('now', '-1 day')
    """)
    
    row = cursor.fetchone()
    if row:
        trades_24h, profit_24h = row
        print(f"\n📅 ÚLTIMAS 24 HORAS:")
        print(f"   Trades: {trades_24h}")
        print(f"   Profit: ${profit_24h:.2f}" if profit_24h else "   Profit: $0.00")
    
    conn.close()
    
    print("\n" + "="*80)
    print("🔧 RECOMENDAÇÕES:")
    print("   1. Verificar lógica de entrada das estratégias")
    print("   2. Revisar gestão de risco (SL/TP)")
    print("   3. Analisar se sinais estão invertidos (BUY/SELL)")
    print("   4. Validar indicadores técnicos")
    print("="*80 + "\n")

if __name__ == "__main__":
    analisar_performance()
