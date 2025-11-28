"""
Teste do Sistema de Aprendizado
Verifica se o Learner está funcionando corretamente
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ml.strategy_learner import StrategyLearner
from loguru import logger
import json

print("=" * 80)
print("🧠 TESTE DO SISTEMA DE APRENDIZADO (STRATEGY LEARNER)")
print("=" * 80)

learner = StrategyLearner()

# Lista de estratégias
strategies = ['trend_following', 'mean_reversion', 'breakout', 'scalping', 'range_trading', 'news_trading']

print("\n1️⃣ ANÁLISE DE PERFORMANCE (últimos 7 dias)")
print("-" * 80)

results = {}
for strat in strategies:
    perf = learner.analyze_strategy_performance(strat, days=7)
    results[strat] = perf
    
    if perf.get('total_trades', 0) > 0:
        print(f"\n📊 {strat.upper()}")
        print(f"   Trades: {perf['total_trades']}")
        print(f"   Wins: {perf.get('winning_trades', 0)}")
        print(f"   Losses: {perf.get('losing_trades', 0)}")
        print(f"   Win Rate: {perf.get('win_rate', 0)*100:.1f}%")
        print(f"   Total Profit: ${perf.get('total_profit', 0):.2f}")
        print(f"   Total Loss: ${perf.get('total_loss', 0):.2f}")
        print(f"   Net Profit: ${perf.get('net_profit', 0):.2f}")
        print(f"   Profit Factor: {perf.get('profit_factor', 0):.2f}")
        print(f"   Avg Confidence: {perf.get('avg_confidence', 0)*100:.1f}%")
        print(f"   Recomendação: {perf.get('recommendation', 'N/A')}")
    else:
        print(f"\n📊 {strat.upper()}: Sem trades nos últimos 7 dias")

# Ranking
print("\n\n2️⃣ RANKING DE ESTRATÉGIAS (por performance)")
print("-" * 80)

# Ordenar por net_profit
ranked = sorted(
    [(name, perf) for name, perf in results.items() if perf.get('total_trades', 0) > 0],
    key=lambda x: x[1].get('net_profit', 0),
    reverse=True
)

for i, (name, perf) in enumerate(ranked, 1):
    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}º"
    profit = perf.get('net_profit', 0)
    wr = perf.get('win_rate', 0) * 100
    trades = perf.get('total_trades', 0)
    print(f"{emoji} {name}: ${profit:.2f} ({wr:.1f}% WR, {trades} trades)")

# Testar ajustes recomendados
print("\n\n3️⃣ AJUSTES RECOMENDADOS PELO LEARNER")
print("-" * 80)

for strat in strategies:
    if results[strat].get('total_trades', 0) >= 10:
        adjustments = learner.get_recommended_adjustments(strat)
        
        if adjustments:
            print(f"\n🔧 {strat.upper()}:")
            for key, value in adjustments.items():
                if isinstance(value, float):
                    print(f"   - {key}: {value:.2%}" if value < 1 else f"   - {key}: {value:.0f}")
                else:
                    print(f"   - {key}: {value}")

# Verificar dados salvos
print("\n\n4️⃣ DADOS DE APRENDIZAGEM SALVOS")
print("-" * 80)

if learner.learning_data:
    print(f"Estratégias com dados de aprendizagem: {len(learner.learning_data)}")
    print("\nResumo:")
    for name, data in learner.learning_data.items():
        print(f"\n📚 {name}:")
        print(f"   - Last update: {data.get('last_update', 'N/A')}")
        print(f"   - Total trades aprendidos: {data.get('total_trades_learned', 0)}")
        print(f"   - Min confidence atual: {data.get('current_min_confidence', 0):.2%}")
        print(f"   - Cycle seconds atual: {data.get('current_cycle_seconds', 0)}")
else:
    print("⚠️ Nenhum dado de aprendizagem salvo ainda")

# Testar aprendizado com trade simulado
print("\n\n5️⃣ TESTE DE APRENDIZADO COM TRADE SIMULADO")
print("-" * 80)

test_trade = {
    'profit': 50.00,
    'signal_confidence': 0.75,
    'market_conditions': 'uptrend_strong',
    'volume': 0.01,
    'duration_minutes': 45.0
}

print(f"Simulando trade de teste: ${test_trade['profit']:.2f} (confiança: {test_trade['signal_confidence']:.0%})")

try:
    learner.learn_from_trade('test_strategy', test_trade)
    print("✅ Learner processou trade de teste com sucesso")
    
    # Verificar se salvou
    if 'test_strategy' in learner.learning_data:
        print("✅ Dados salvos corretamente")
    else:
        print("❌ Dados não foram salvos")
except Exception as e:
    print(f"❌ Erro ao processar: {e}")

print("\n" + "=" * 80)
print("🎯 RESUMO:")
print(f"   - Estratégias testadas: {len(strategies)}")
print(f"   - Estratégias com dados: {len([r for r in results.values() if r.get('total_trades', 0) > 0])}")
print(f"   - Total de trades analisados: {sum(r.get('total_trades', 0) for r in results.values())}")
print(f"   - Sistema de aprendizado: {'✅ Funcionando' if learner.learning_data else '⚠️ Sem dados'}")
print("=" * 80)
