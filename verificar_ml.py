"""
Script para verificar sistema de aprendizagem
"""
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, 'src')
from ml.strategy_learner import StrategyLearner
from database.strategy_stats import StrategyStatsDB

def main():
    print("\n" + "="*80)
    print("🤖 VERIFICAÇÃO DO SISTEMA DE APRENDIZAGEM - URION BOT")
    print("="*80 + "\n")
    
    # 1. Verificar arquivos
    print("📁 ARQUIVOS:")
    print("-" * 80)
    
    db_path = Path("data/strategy_stats.db")
    learning_path = Path("data/learning_data.json")
    
    print(f"Database: {'✅ Existe' if db_path.exists() else '❌ Não existe'}")
    if db_path.exists():
        print(f"  Tamanho: {db_path.stat().st_size:,} bytes")
    
    print(f"Learning Data: {'✅ Existe' if learning_path.exists() else '❌ Não existe'}")
    if learning_path.exists():
        print(f"  Tamanho: {learning_path.stat().st_size:,} bytes")
    
    # 2. Verificar database
    print("\n📊 DATABASE:")
    print("-" * 80)
    
    conn = sqlite3.connect('data/strategy_stats.db')
    c = conn.cursor()
    
    # Total de trades
    c.execute("SELECT COUNT(*) FROM strategy_trades")
    total_trades = c.fetchone()[0]
    print(f"Total de trades registrados: {total_trades}")
    
    # Trades fechados
    c.execute("SELECT COUNT(*) FROM strategy_trades WHERE status='closed'")
    closed_trades = c.fetchone()[0]
    print(f"Trades fechados: {closed_trades}")
    
    # Trades com lucro
    c.execute("SELECT COUNT(*) FROM strategy_trades WHERE profit > 0")
    winning_trades = c.fetchone()[0]
    print(f"Trades com lucro: {winning_trades}")
    
    # Win rate geral
    if closed_trades > 0:
        win_rate = (winning_trades / closed_trades) * 100
        print(f"Win Rate geral: {win_rate:.1f}%")
    
    # Trades por estratégia
    print("\n📈 TRADES POR ESTRATÉGIA:")
    c.execute("""
        SELECT 
            strategy_name,
            COUNT(*) as total,
            SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN profit <= 0 THEN 1 ELSE 0 END) as losses,
            ROUND(AVG(CASE WHEN profit IS NOT NULL THEN profit ELSE 0 END), 2) as avg_profit
        FROM strategy_trades
        WHERE status = 'closed'
        GROUP BY strategy_name
        ORDER BY total DESC
    """)
    
    for row in c.fetchall():
        strat, total, wins, losses, avg_profit = row
        wr = (wins / total * 100) if total > 0 else 0
        print(f"  {strat:20s} | Trades: {total:3d} | Wins: {wins:3d} | Losses: {losses:3d} | WR: {wr:5.1f}% | Avg: ${avg_profit:.2f}")
    
    conn.close()
    
    # 3. Verificar sistema de aprendizagem
    print("\n🧠 SISTEMA DE APRENDIZAGEM:")
    print("-" * 80)
    
    try:
        learner = StrategyLearner()
        
        if not learner.learning_data:
            print("⚠️  Sistema ainda não tem dados de aprendizagem")
            print("   O bot precisa fechar alguns trades primeiro")
        else:
            print(f"✅ {len(learner.learning_data)} estratégias monitoradas\n")
            
            for strategy_name, data in learner.learning_data.items():
                total = data.get('total_trades', 0)
                wins = data.get('wins', 0)
                losses = data.get('losses', 0)
                confidence = data.get('min_confidence', 0.0)
                last_adj = data.get('last_adjustment', 'Nunca')
                
                wr = (wins / total * 100) if total > 0 else 0
                
                print(f"📊 {strategy_name.upper()}")
                print(f"   Trades: {total} | Wins: {wins} | Losses: {losses} | WR: {wr:.1f}%")
                print(f"   Confiança mínima: {confidence:.2f}")
                print(f"   Último ajuste: {last_adj}")
                print(f"   Padrões aprendidos: {len(data.get('best_conditions', []))}")
                print()
        
        # 4. Performance recente
        print("\n🎯 PERFORMANCE RECENTE (7 dias):")
        print("-" * 80)
        
        for strategy_name in learner.learning_data.keys():
            perf = learner.analyze_strategy_performance(strategy_name, days=7)
            
            if perf['total_trades'] > 0:
                trend_emoji = {
                    'improving': '📈',
                    'declining': '📉',
                    'stable': '➡️'
                }
                
                print(f"{strategy_name:20s} | "
                      f"Trades: {perf['total_trades']:3d} | "
                      f"WR: {perf['win_rate']*100:5.1f}% | "
                      f"PF: {perf['profit_factor']:5.2f} | "
                      f"Tendência: {trend_emoji.get(perf['recent_trend'], '?')} {perf['recent_trend']}")
        
        # 5. Ranking
        print("\n🏆 RANKING DE ESTRATÉGIAS:")
        print("-" * 80)
        
        ranking = learner.get_strategy_ranking(days=7)
        
        if ranking:
            medals = ['🥇', '🥈', '🥉']
            for i, strat in enumerate(ranking):
                medal = medals[i] if i < 3 else f"{i+1}."
                print(f"{medal} {strat['strategy']:20s} | Score: {strat['score']:.3f}")
        else:
            print("⚠️  Sem dados suficientes para ranking")
    
    except Exception as e:
        print(f"❌ Erro ao verificar sistema: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("✅ VERIFICAÇÃO COMPLETA!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
