"""
Análise de Assertividade das Estratégias
Verifica performance de cada estratégia e sugere melhorias
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database.strategy_stats import StrategyStatsDB
from datetime import datetime, timedelta
from loguru import logger


def analyze_strategy_performance():
    """Analisa performance de todas as estratégias"""
    
    print("\n" + "="*80)
    print(" ANÁLISE DE ASSERTIVIDADE DAS ESTRATÉGIAS - URION BOT")
    print("="*80 + "\n")
    
    stats = StrategyStatsDB()
    
    strategies = [
        'trend_following',
        'mean_reversion', 
        'breakout',
        'news_trading',
        'scalping',
        'range_trading'
    ]
    
    all_results = {}
    
    # Análise por estratégia
    for strategy in strategies:
        print(f"\n{'─'*80}")
        print(f"📊 {strategy.upper().replace('_', ' ')}")
        print(f"{'─'*80}")
        
        # Performance geral
        result = stats.get_strategy_stats(strategy, days=30)  # Últimos 30 dias
        
        if result and result.get('total_trades', 0) > 0:
            all_results[strategy] = result
            
            total = result['total_trades']
            wins = result['winning_trades']
            losses = result['losing_trades']
            win_rate = result['win_rate']
            profit_factor = result['profit_factor']
            net_profit = result['net_profit']
            avg_win = result['avg_win']
            avg_loss = result['avg_loss']
            
            print(f"\n📈 ESTATÍSTICAS GERAIS:")
            print(f"   • Total de Trades: {total}")
            print(f"   • Trades Vencedores: {wins} ({win_rate:.1f}%)")
            print(f"   • Trades Perdedores: {losses} ({100-win_rate:.1f}%)")
            print(f"   • Win Rate: {win_rate:.1f}%")
            
            print(f"\n💰 LUCRATIVIDADE:")
            print(f"   • Lucro Líquido: ${net_profit:.2f}")
            print(f"   • Média de Ganho: ${avg_win:.2f}")
            print(f"   • Média de Perda: ${avg_loss:.2f}")
            print(f"   • Profit Factor: {profit_factor:.2f}")
            print(f"   • Risk/Reward Médio: 1:{abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "   • Risk/Reward: N/A")
            
            # Classificação
            if win_rate >= 70:
                status = "🟢 EXCELENTE"
            elif win_rate >= 60:
                status = "🟡 BOM"
            elif win_rate >= 50:
                status = "🟠 REGULAR"
            else:
                status = "🔴 PRECISA MELHORAR"
            
            print(f"\n📊 STATUS: {status}")
            
            # Últimos 7 dias
            recent = stats.get_strategy_stats(strategy, days=7)
            if recent and recent.get('total_trades', 0) > 0:
                print(f"\n📅 ÚLTIMOS 7 DIAS:")
                print(f"   • Trades: {recent['total_trades']}")
                print(f"   • Win Rate: {recent['win_rate']:.1f}%")
                print(f"   • Lucro: ${recent['net_profit']:.2f}")
            
        else:
            print(f"\n⚠️  Nenhum trade registrado ainda")
            all_results[strategy] = None
    
    # Ranking geral
    print(f"\n\n{'='*80}")
    print(" 🏆 RANKING DE ESTRATÉGIAS")
    print(f"{'='*80}\n")
    
    # Filtrar estratégias com dados
    ranked = [(name, data) for name, data in all_results.items() if data is not None]
    
    if ranked:
        # Ordenar por win rate
        ranked.sort(key=lambda x: x[1]['win_rate'], reverse=True)
        
        print("📊 Por Win Rate:")
        for i, (name, data) in enumerate(ranked, 1):
            symbol = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            print(f"   {symbol} {name.replace('_', ' ').title()}: {data['win_rate']:.1f}%")
        
        # Ordenar por profit factor
        ranked.sort(key=lambda x: x[1]['profit_factor'], reverse=True)
        
        print("\n💰 Por Profit Factor:")
        for i, (name, data) in enumerate(ranked, 1):
            symbol = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            print(f"   {symbol} {name.replace('_', ' ').title()}: {data['profit_factor']:.2f}")
        
        # Ordenar por lucro total
        ranked.sort(key=lambda x: x[1]['total_profit'], reverse=True)
        
        print("\n💵 Por Lucro Total:")
        for i, (name, data) in enumerate(ranked, 1):
            symbol = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            profit = data['net_profit']
            color = "verde" if profit > 0 else "vermelho"
            print(f"   {symbol} {name.replace('_', ' ').title()}: ${profit:.2f}")
    else:
        print("⚠️  Nenhuma estratégia possui dados suficientes ainda")
    
    # Recomendações
    print(f"\n\n{'='*80}")
    print(" 💡 RECOMENDAÇÕES PARA MELHORAR ASSERTIVIDADE")
    print(f"{'='*80}\n")
    
    print("🎯 MELHORIAS GERAIS:")
    print("\n1. AJUSTE DE PARÂMETROS:")
    print("   • Aumentar min_confidence para estratégias com win_rate < 50%")
    print("   • Reduzir timeframe para estratégias com muitos sinais falsos")
    print("   • Ajustar indicadores técnicos (RSI, MACD, Bollinger)")
    
    print("\n2. FILTROS ADICIONAIS:")
    print("   • Validar tendência em múltiplos timeframes")
    print("   • Confirmar volume (evitar sinais em baixa liquidez)")
    print("   • Evitar trading em horários de baixa volatilidade")
    print("   • Adicionar filtro de spread (não operar com spread alto)")
    
    print("\n3. GESTÃO DE RISCO:")
    print("   • Implementar trailing stop mais agressivo")
    print("   • Mover para break-even mais cedo")
    print("   • Usar partial close em 50% do lucro esperado")
    print("   • Limitar máximo de trades simultâneos por estratégia")
    
    print("\n4. OTIMIZAÇÕES POR ESTRATÉGIA:")
    
    for strategy, data in all_results.items():
        if data is None:
            continue
            
        win_rate = data['win_rate']
        profit_factor = data['profit_factor']
        
        print(f"\n   📌 {strategy.replace('_', ' ').upper()}:")
        
        if win_rate < 50:
            print(f"      ⚠️  Win Rate baixo ({win_rate:.1f}%)")
            print(f"         → Aumentar threshold de confiança")
            print(f"         → Adicionar mais filtros de confirmação")
            print(f"         → Revisar condições de entrada")
        
        if profit_factor < 1.5:
            print(f"      ⚠️  Profit Factor baixo ({profit_factor:.2f})")
            print(f"         → Melhorar relação Risk/Reward")
            print(f"         → Ajustar níveis de Stop Loss")
            print(f"         → Otimizar Take Profit")
        
        if data['avg_loss'] > abs(data['avg_win']):
            print(f"      ⚠️  Perdas maiores que ganhos")
            print(f"         → Apertar Stop Loss")
            print(f"         → Deixar Take Profit correr mais")
        
        if win_rate >= 60 and profit_factor >= 2.0:
            print(f"      ✅ Estratégia está performando bem!")
            print(f"         → Considerar aumentar volume")
            print(f"         → Manter parâmetros atuais")
    
    print("\n5. ANÁLISE TÉCNICA APRIMORADA:")
    print("   • Adicionar indicador ATR (Average True Range)")
    print("   • Usar Ichimoku Cloud para tendência")
    print("   • Implementar padrões de candlestick")
    print("   • Adicionar análise de suporte/resistência")
    
    print("\n6. MACHINE LEARNING:")
    print("   • Treinar modelo com histórico de trades")
    print("   • Prever probabilidade de sucesso antes de entrar")
    print("   • Ajustar parâmetros automaticamente baseado em performance")
    print("   • Identificar padrões de mercado")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    try:
        analyze_strategy_performance()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
