"""
Script para aplicar melhorias de assertividade
Ajusta thresholds de confiança e adiciona filtros
"""
import yaml
from pathlib import Path
import shutil
from datetime import datetime


def backup_config():
    """Faz backup do config atual"""
    config_path = Path("config/config.yaml")
    backup_path = Path(f"config/config.yaml.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    shutil.copy(config_path, backup_path)
    print(f"✅ Backup criado: {backup_path}")
    
    return str(backup_path)


def apply_improvements():
    """Aplica melhorias de assertividade"""
    
    print("\n" + "="*80)
    print(" 🚀 APLICANDO MELHORIAS DE ASSERTIVIDADE")
    print("="*80 + "\n")
    
    # Backup
    backup_path = backup_config()
    
    # Carregar config
    config_path = Path("config/config.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print("\n📊 AJUSTES DE CONFIDENCE THRESHOLD:\n")
    
    # Ajustar thresholds
    improvements = {
        'trend_following': {'old': 0.65, 'new': 0.70},
        'mean_reversion': {'old': 0.70, 'new': 0.75},
        'breakout': {'old': 0.75, 'new': 0.80},
        'news_trading': {'old': 0.80, 'new': 0.85},
        'scalping': {'old': 0.60, 'new': 0.70},
        'range_trading': {'old': 0.50, 'new': 0.65},  # CRÍTICO!
    }
    
    for strategy, values in improvements.items():
        if strategy in config['strategies']:
            old_val = config['strategies'][strategy]['min_confidence']
            new_val = values['new']
            
            config['strategies'][strategy]['min_confidence'] = new_val
            
            symbol = "🔴" if old_val < 0.60 else "🟡" if old_val < 0.70 else "🟢"
            print(f"   {symbol} {strategy.replace('_', ' ').title()}: {old_val:.0%} → {new_val:.0%}")
    
    # Adicionar novos filtros (se não existirem)
    print("\n📋 ADICIONANDO FILTROS DE QUALIDADE:\n")
    
    filters_added = []
    
    for strategy in improvements.keys():
        if strategy in config['strategies']:
            
            # Filtro de spread
            if 'max_spread_pips' not in config['strategies'][strategy]:
                config['strategies'][strategy]['max_spread_pips'] = 2.0
                filters_added.append(f"   ✅ {strategy}: max_spread_pips = 2.0")
            
            # Filtro de volume
            if 'volume_confirmation' not in config['strategies'][strategy]:
                config['strategies'][strategy]['volume_confirmation'] = True
                filters_added.append(f"   ✅ {strategy}: volume_confirmation = True")
            
            # Anti-overtrading para Scalping
            if strategy == 'scalping':
                if 'max_trades_per_hour' not in config['strategies'][strategy]:
                    config['strategies'][strategy]['max_trades_per_hour'] = 2
                    filters_added.append(f"   ✅ {strategy}: max_trades_per_hour = 2")
    
    for msg in filters_added:
        print(msg)
    
    # Salvar config atualizado
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print("\n✅ Configuração atualizada com sucesso!")
    print(f"📄 Backup salvo em: {backup_path}")
    
    print("\n" + "="*80)
    print(" 📊 RESUMO DAS MELHORIAS")
    print("="*80 + "\n")
    
    print("🎯 ASSERTIVIDADE ESPERADA (após melhorias):\n")
    print("   Strategy            | Old      | New      | Expected Win Rate")
    print("   " + "-"*70)
    print("   TrendFollowing      | 65%      | 70%      | 65-75%")
    print("   MeanReversion       | 70%      | 75%      | 60-70%")
    print("   Breakout            | 75%      | 80%      | 55-65%")
    print("   NewsTrading         | 80%      | 85%      | 50-60%")
    print("   Scalping            | 60%      | 70%      | 60-70%")
    print("   RangeTrading        | 50% ⚠️   | 65%      | 65-75%")
    print("\n   🎯 META GLOBAL: 60-65% de assertividade geral")
    
    print("\n📋 FILTROS ADICIONADOS:\n")
    print("   ✅ Max Spread: 2.0 pips")
    print("   ✅ Volume Confirmation: Ativado")
    print("   ✅ Anti-Overtrading (Scalping): 2 trades/hora")
    
    print("\n🚀 PRÓXIMOS PASSOS:\n")
    print("   1. Reiniciar o bot para aplicar mudanças")
    print("   2. Monitorar assertividade após 50 trades")
    print("   3. Ajustar novamente se necessário")
    print("   4. Revisar docs/ANALISE_ASSERTIVIDADE.md")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    try:
        apply_improvements()
    except Exception as e:
        print(f"\n❌ Erro ao aplicar melhorias: {e}")
        import traceback
        traceback.print_exc()
