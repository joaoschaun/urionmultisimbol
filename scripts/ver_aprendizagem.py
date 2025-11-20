"""
Script para visualizar status de aprendizagem do bot
Mostra o que o sistema aprendeu e como está ajustando as estratégias
"""

import sys
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from ml.strategy_learner import StrategyLearner
from loguru import logger


def main():
    """Exibe status completo de aprendizagem"""
    
    print("\n" + "=" * 80)
    print("🤖 URION BOT - STATUS DE APRENDIZAGEM (MACHINE LEARNING)")
    print("=" * 80)
    
    learner = StrategyLearner()
    
    # Status de cada estratégia
    print("\n📚 APRENDIZAGEM POR ESTRATÉGIA:")
    print("-" * 80)
    
    if not learner.learning_data:
        print("\n⚠️  Nenhum dado de aprendizagem ainda.")
        print("   O bot precisa executar trades para começar a aprender.\n")
        return
    
    for strategy_name, data in learner.learning_data.items():
        total = data['total_trades']
        wins = data['wins']
        losses = data['losses']
        win_rate = wins / total if total > 0 else 0
        confidence = data['min_confidence']
        last_adj = data.get('last_adjustment', 'Nunca')
        
        print(f"\n{strategy_name.upper()}")
        print(f"  📊 Trades: {total} | Ganhos: {wins} | Perdas: {losses}")
        print(f"  ✅ Win Rate: {win_rate:.1%}")
        print(f"  🎯 Confiança Atual: {confidence:.2f}")
        print(f"  🔄 Último Ajuste: {last_adj}")
        
        if len(data.get('best_conditions', [])) > 0:
            print(f"  💡 Melhores Condições: {len(data['best_conditions'])} padrões salvos")
    
    # Análise de performance recente (últimos 7 dias)
    print("\n\n📈 ANÁLISE DE PERFORMANCE (Últimos 7 dias):")
    print("-" * 80)
    
    for strategy_name in learner.learning_data.keys():
        performance = learner.analyze_strategy_performance(strategy_name, days=7)
        
        if performance['total_trades'] > 0:
            trend_emoji = {
                'improving': '📈',
                'declining': '📉',
                'stable': '➡️'
            }
            
            print(f"\n{strategy_name}:")
            print(f"  Trades: {performance['total_trades']}")
            print(f"  Win Rate: {performance['win_rate']:.1%}")
            print(f"  Profit Factor: {performance['profit_factor']:.2f}")
            print(f"  Tendência: {trend_emoji.get(performance['recent_trend'], '?')} {performance['recent_trend']}")
            
            if performance['best_confidence_range']:
                min_c, max_c = performance['best_confidence_range']
                print(f"  🎯 Melhor Faixa de Confiança: {min_c:.2f} - {max_c:.2f}")
    
    # Ranking de estratégias
    print("\n\n🏆 RANKING DE ESTRATÉGIAS:")
    print("-" * 80)
    
    ranking = learner.get_strategy_ranking(days=7)
    
    if ranking:
        medals = ['🥇', '🥈', '🥉']
        for i, strat in enumerate(ranking):
            medal = medals[i] if i < 3 else f"{i+1}."
            print(
                f"{medal} {strat['strategy']:20s} | "
                f"Score: {strat['score']:.3f} | "
                f"WR: {strat['win_rate']:.1%} | "
                f"PF: {strat['profit_factor']:.2f} | "
                f"Trades: {strat['total_trades']}"
            )
    else:
        print("\n⚠️  Sem dados suficientes para ranking ainda.")
    
    # Sugestões de ajuste
    print("\n\n💡 SUGESTÕES DE AJUSTE:")
    print("-" * 80)
    
    has_suggestions = False
    for strategy_name in learner.learning_data.keys():
        suggestion = learner.suggest_confidence_adjustment(strategy_name)
        
        if suggestion:
            has_suggestions = True
            current = learner.learning_data[strategy_name]['min_confidence']
            direction = "⬇️ Diminuir" if suggestion < current else "⬆️ Aumentar"
            print(f"\n{strategy_name}:")
            print(f"  {direction} confiança de {current:.2f} → {suggestion:.2f}")
    
    if not has_suggestions:
        print("\n✅ Todas as estratégias estão com parâmetros adequados.")
    
    print("\n" + "=" * 80)
    print("\n💡 COMO FUNCIONA:")
    print("  • O bot aprende automaticamente com cada trade executado")
    print("  • A cada 20 trades, ajusta parâmetros automaticamente")
    print("  • Se Win Rate > 70%: diminui threshold para operar mais")
    print("  • Se Win Rate < 50%: aumenta threshold para ser mais seletivo")
    print("  • Identifica melhores condições de mercado para cada estratégia")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
