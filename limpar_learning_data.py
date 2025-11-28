"""
Script para LIMPAR dados de aprendizado ERRADOS
e RESETAR o learning_data.json para começar do zero
"""

import json
from pathlib import Path
from datetime import datetime

def limpar_learning_data():
    """Limpa learning_data.json e cria backup"""
    
    learning_file = Path("data/learning_data.json")
    
    if not learning_file.exists():
        print("⚠️ Arquivo learning_data.json não existe")
        return
    
    # Fazer backup
    backup_file = Path(f"data/learning_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    try:
        # Ler dados atuais
        with open(learning_file, 'r') as f:
            old_data = json.load(f)
        
        # Salvar backup
        with open(backup_file, 'w') as f:
            json.dump(old_data, f, indent=2)
        
        print(f"✅ Backup criado: {backup_file}")
        print(f"\nDados antigos:")
        for strategy, data in old_data.items():
            if strategy != 'test_strategy':
                print(f"  {strategy}:")
                print(f"    Total trades: {data['total_trades']}")
                print(f"    Wins: {data['wins']}")
                print(f"    Losses: {data['losses']}")
                print(f"    Win Rate: {data['wins']/data['total_trades']*100:.1f}%")
                print(f"    Min Confidence: {data['min_confidence']}")
        
        # Criar dados limpos (apenas estrutura, sem histórico)
        clean_data = {}
        
        # Salvar dados limpos
        with open(learning_file, 'w') as f:
            json.dump(clean_data, f, indent=2)
        
        print(f"\n✅ learning_data.json LIMPO!")
        print(f"✅ O bot vai começar aprendizado do ZERO com dados CORRETOS")
        print(f"\n📝 Backup dos dados antigos está em: {backup_file}")
        
    except Exception as e:
        print(f"❌ Erro ao limpar learning_data: {e}")

if __name__ == "__main__":
    print("=" * 80)
    print("🗑️  LIMPEZA DE DADOS DE APRENDIZADO ERRADOS")
    print("=" * 80)
    print("\nEste script vai:")
    print("1. Fazer backup dos dados atuais")
    print("2. LIMPAR o learning_data.json")
    print("3. Bot vai começar aprendizado do ZERO")
    print("\n⚠️  ATENÇÃO: Os dados antigos foram baseados em leitura ERRADA de profit!")
    print("⚠️  Precisamos limpar para não ensinar o bot com dados incorretos.\n")
    
    limpar_learning_data()
