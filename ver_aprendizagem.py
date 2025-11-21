"""
Script para visualizar o que o bot está aprendendo
"""

import json
from pathlib import Path
from datetime import datetime
from loguru import logger

logger.remove()
logger.add(lambda msg: print(msg, end=''), colorize=True, format="<green>{message}</green>")


def main():
    """Mostra o progresso de aprendizagem do bot"""
    
    learning_file = Path("data/learning_data.json")
    
    if not learning_file.exists():
        print("\n❌ Nenhum dado de aprendizagem encontrado ainda.")
        print("   O bot precisa fechar alguns trades primeiro.\n")
        return
    
    # Carregar dados
    with open(learning_file, 'r') as f:
        data = json.load(f)
    
    if not data:
        print("\n❌ Arquivo de aprendizagem vazio.\n")
        return
    
    print("\n" + "="*80)
    print("🤖 SISTEMA DE APRENDIZAGEM - PROGRESSO")
    print("="*80 + "\n")
    
    # Ordenar por total de trades
    strategies = sorted(
        data.items(),
        key=lambda x: x[1].get('total_trades', 0),
        reverse=True
    )
    
    for strategy_name, strategy_data in strategies:
        total = strategy_data.get('total_trades', 0)
        wins = strategy_data.get('wins', 0)
        losses = strategy_data.get('losses', 0)
        min_conf = strategy_data.get('min_confidence', 0.5)
        last_adj = strategy_data.get('last_adjustment')
        
        if total == 0:
            continue
        
        win_rate = (wins / total * 100) if total > 0 else 0
        
        # Emoji baseado em win rate
        if win_rate >= 70:
            emoji = "🟢"
            status = "EXCELENTE"
        elif win_rate >= 60:
            emoji = "🟡"
            status = "BOM"
        elif win_rate >= 50:
            emoji = "🟠"
            status = "REGULAR"
        else:
            emoji = "🔴"
            status = "PRECISA MELHORAR"
        
        print(f"{emoji} {strategy_name.upper()}")
        print(f"   Status: {status}")
        print(f"   Total de Trades: {total}")
        print(f"   Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.1f}%")
        print(f"   Confiança Mínima Ajustada: {min_conf:.2f}")
        
        if last_adj:
            try:
                adj_date = datetime.fromisoformat(last_adj)
                print(f"   Último Ajuste: {adj_date.strftime('%d/%m/%Y %H:%M')}")
            except:
                pass
        
        # Mostrar melhores condições aprendidas
        best_conditions = strategy_data.get('best_conditions', [])
        if best_conditions:
            print(f"   Condições de Sucesso Aprendidas: {len(best_conditions)}")
            
            # Mostrar top 3
            top_3 = sorted(best_conditions, key=lambda x: x['profit'], reverse=True)[:3]
            for i, cond in enumerate(top_3, 1):
                print(f"      #{i}: Lucro ${cond['profit']:.2f} | Conf: {cond['confidence']:.2f}")
        
        print()
    
    print("="*80)
    print("\n💡 COMO FUNCIONA:")
    print("   • Win Rate ≥70%: Bot diminui confiança mínima (opera mais)")
    print("   • Win Rate <50%: Bot aumenta confiança mínima (mais seletivo)")
    print("   • Ajustes automáticos a cada 20 trades")
    print("   • Aprende melhores condições de mercado para cada estratégia")
    print("\n")


if __name__ == "__main__":
    main()
