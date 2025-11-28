"""
Teste do Market Condition Analyzer
"""
import sys
sys.path.append('src')

import MetaTrader5 as mt5
from analysis.market_condition_analyzer import MarketConditionAnalyzer

# Conectar MT5
if not mt5.initialize():
    print("❌ Erro ao inicializar MT5")
    exit()

print("✅ MT5 conectado")
print("="*80)

# Criar analyzer
analyzer = MarketConditionAnalyzer("XAUUSD")

# Analisar mercado
analysis = analyzer.analyze()

if analysis:
    print(f"\n📊 ANÁLISE DE MERCADO - XAUUSD")
    print("="*80)
    print(f"Condição Detectada: {analysis.condition.value.upper()}")
    print(f"Força da Condição: {analysis.strength:.2%}")
    print(f"Confiança: {analysis.confidence:.2%}")
    print(f"\n📈 Indicadores:")
    print(f"  Volatilidade: {analysis.volatility:.2%}")
    print(f"  Volume Relativo: {analysis.volume:.2f}x")
    print(f"  Força Tendência: {analysis.trend_strength:+.2%}")
    
    print(f"\n✅ Estratégias RECOMENDADAS:")
    for strat in analysis.recommended_strategies:
        print(f"  • {strat}")
    
    print(f"\n❌ Estratégias a EVITAR:")
    for strat in analysis.avoid_strategies:
        print(f"  • {strat}")
    
    # Obter prioridades
    print(f"\n🎯 PRIORIDADES DAS ESTRATÉGIAS:")
    priorities = analyzer.get_strategy_priority(analysis)
    for strategy, priority in sorted(priorities.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(priority * 20)
        print(f"  {strategy:20} [{bar:<20}] {priority:.1%}")
else:
    print("❌ Não foi possível analisar o mercado")

mt5.shutdown()
print("\n" + "="*80)
